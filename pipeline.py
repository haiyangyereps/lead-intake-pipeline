"""Lead intake with validation, idempotency, reviewable errors and a durable outbox."""
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import time
import os
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, payload_hash TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rejections(id INTEGER PRIMARY KEY, event_id TEXT, reason TEXT, created REAL);
CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY, lead_id INTEGER UNIQUE, state TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0, next_attempt REAL DEFAULT 0, error TEXT);
'''

def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db

def validate(payload):
    name, email = payload.get('name'), payload.get('email')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
        raise ValueError('name must contain 1–160 characters')
    if not isinstance(email, str):
        raise ValueError('email must be a string')
    email = email.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", email):
        raise ValueError('invalid email format')
    return name.strip(), email

def ingest(db, payload, event_id):
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 200:
        raise ValueError('event ID required, maximum 200 characters')
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with db:
        # Serialize deduplication and result persistence in the same transaction.
        db.execute('BEGIN IMMEDIATE')
        previous = db.execute('SELECT * FROM events WHERE event_id=?', (event_id,)).fetchone()
        if previous:
            if previous['payload_hash'] != digest:
                raise ValueError('event ID reused with a different payload')
            return {**json.loads(previous['result']), 'replayed': True}
        try:
            name, email = validate(payload)
        except ValueError as exc:
            result = {'status': 'rejected', 'reason': str(exc)}
            db.execute('INSERT INTO rejections(event_id,reason,created) VALUES(?,?,?)', (event_id,str(exc),time.time()))
        else:
            cursor = db.execute('INSERT OR IGNORE INTO leads(email,name) VALUES(?,?)', (email,name))
            lead_id = db.execute('SELECT id FROM leads WHERE email=?',(email,)).fetchone()['id']
            result = {'status': 'accepted' if cursor.rowcount else 'duplicate', 'lead_id':lead_id}
            if cursor.rowcount:
                db.execute('INSERT INTO outbox(lead_id) VALUES(?)',(lead_id,))
        db.execute('INSERT INTO events VALUES(?,?,?)',(event_id,digest,json.dumps(result)))
        return result

def drain(db, destination, now=None, max_attempts=3):
    """Idempotent local CRM adapter; other integrations must implement their own key."""
    now = time.time() if now is None else now
    results=[]
    with db:
        for item in db.execute("SELECT o.*,l.email,l.name FROM outbox o JOIN leads l ON l.id=o.lead_id WHERE state='pending' AND next_attempt<=?",(now,)).fetchall():
            try:
                with sqlite3.connect(destination) as crm:
                    crm.execute('CREATE TABLE IF NOT EXISTS contacts(source_id INTEGER PRIMARY KEY,email TEXT,name TEXT)')
                    crm.execute('INSERT OR IGNORE INTO contacts VALUES(?,?,?)',(item['lead_id'],item['email'],item['name']))
            except (sqlite3.Error,OSError) as exc:
                attempts=item['attempts']+1
                state='dead' if attempts>=max_attempts else 'pending'
                db.execute('UPDATE outbox SET state=?,attempts=?,next_attempt=?,error=? WHERE id=?',(state,attempts,now+2**attempts,type(exc).__name__,item['id']))
                results.append({'id':item['id'],'status':state,'attempts':attempts})
            else:
                db.execute("UPDATE outbox SET state='delivered',attempts=attempts+1,error=NULL WHERE id=?",(item['id'],))
                results.append({'id':item['id'],'status':'delivered'})
    return results

def stats(db):
    return {table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('leads','events','rejections')} | {'outbox':[dict(x) for x in db.execute('SELECT state,count(*) AS count FROM outbox GROUP BY state')]}

def serve(database,port):
    token=os.environ.get('INTAKE_TOKEN','')
    if len(token)<24: raise ValueError('Set INTAKE_TOKEN to a random token of at least 24 characters')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # Do not log contacts or auth headers.
        def do_POST(self):
            if self.path!='/leads': self.reply(404,{'error':'not found'});return
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token): self.reply(401,{'error':'unauthorized'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384: self.reply(413,{'error':'invalid body size'});return
                payload=json.loads(self.rfile.read(length))
                db=connect(database)
                try: result=ingest(db,payload,self.headers.get('Idempotency-Key',''))
                finally: db.close()
                self.reply(422 if result['status']=='rejected' else 200,result)
            except (ValueError,UnicodeDecodeError) as exc:self.reply(400,{'error':str(exc)})
        def reply(self,code,data):
            body=json.dumps(data).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    HTTPServer(('127.0.0.1',port),Handler).serve_forever()

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default='leads.db');s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('import');a.add_argument('csv')
    a=s.add_parser('drain');a.add_argument('--crm',required=True)
    s.add_parser('status')
    a=s.add_parser('serve');a.add_argument('--port',type=int,default=8080)
    a=s.add_parser('errors');a.add_argument('--output',required=True)
    a=p.parse_args()
    if a.command=='serve':serve(a.db,a.port);return
    db=connect(a.db)
    try:
        if a.command=='import':
            raw=Path(a.csv).read_bytes();batch=hashlib.sha256(raw).hexdigest();results=[]
            with open(a.csv,newline='',encoding='utf-8-sig') as f:
                reader=csv.DictReader(f)
                if not {'name','email'}<=set(reader.fieldnames or []):raise ValueError('CSV requires name,email')
                for i,row in enumerate(reader,2):results.append({'row':i,**ingest(db,row,f'{batch}:{i}')})
            print(json.dumps(results,indent=2))
        elif a.command=='drain':print(json.dumps(drain(db,a.crm),indent=2))
        elif a.command=='status':print(json.dumps(stats(db),indent=2))
        else:
            with open(a.output,'w',newline='') as f:
                w=csv.writer(f);w.writerow(['event_id','reason']);w.writerows(db.execute('SELECT event_id,reason FROM rejections'))
    finally:db.close()
if __name__=='__main__':main()
