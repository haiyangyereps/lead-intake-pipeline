"""Sales follow-up operations on top of the durable intake pipeline."""
import argparse,json,time
from decimal import Decimal,InvalidOperation
from pathlib import Path
from pipeline import connect as base_connect,ingest

TRANSITIONS={'new':{'contacted','lost'},'contacted':{'qualified','lost'},'qualified':{'proposal','lost'},'proposal':{'won','lost'},'won':set(),'lost':{'new'}}

def connect(path):
 db=base_connect(path)
 db.executescript('''CREATE TABLE IF NOT EXISTS opportunities(lead_id INTEGER PRIMARY KEY,source TEXT NOT NULL,owner TEXT NOT NULL,stage TEXT NOT NULL DEFAULT 'new',value_cents INTEGER NOT NULL DEFAULT 0,consent INTEGER NOT NULL DEFAULT 0,urgency INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL,due REAL NOT NULL,version INTEGER NOT NULL DEFAULT 1);
 CREATE TABLE IF NOT EXISTS activities(id INTEGER PRIMARY KEY,lead_id INTEGER NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,note TEXT NOT NULL,created REAL NOT NULL);''')
 return db

def money(value):
 try:
  n=Decimal(str(value))
  if not n.is_finite() or n<0 or n>100000000 or n!=n.quantize(Decimal('.01')):raise ValueError('value must be non-negative, at most 100 million, with at most 2 decimals')
  return int(n*100)
 except InvalidOperation:raise ValueError('invalid monetary value')

def activity(db,key,actor,action,note,now):
 if not isinstance(actor,str) or not 1<=len(actor.strip())<=100:raise ValueError('named actor required')
 if not isinstance(note,str) or len(note)>2000:raise ValueError('note maximum 2000 characters')
 db.execute('INSERT INTO activities(lead_id,actor,action,note,created) VALUES(?,?,?,?,?)',(key,actor.strip(),action,note,now))

def capture(db,payload,event_id,now=None):
 now=time.time() if now is None else now
 source=payload.get('source','website');owner=payload.get('owner','unassigned');consent=payload.get('consent',False);urgency=payload.get('urgency',False)
 if any(not isinstance(s,str) or not 1<=len(s.strip())<=100 for s in (source,owner)):raise ValueError('source and owner require 1–100 characters')
 if type(consent) is not bool or type(urgency) is not bool:raise ValueError('consent and urgency must be booleans')
 value=money(payload.get('value',0))
 result=ingest(db,payload,event_id)
 if result['status']=='rejected':return result
 with db:
  db.execute('BEGIN IMMEDIATE')
  cursor=db.execute('INSERT OR IGNORE INTO opportunities(lead_id,source,owner,value_cents,consent,urgency,created,due) VALUES(?,?,?,?,?,?,?,?)',(result['lead_id'],source.strip(),owner.strip(),value,int(consent),int(urgency),now,now+86400))
  if cursor.rowcount:activity(db,result['lead_id'],'intake','created','Initial follow-up due in 24 hours',now)
 return result

def update(db,key,version,actor,changes,now=None):
 now=time.time() if now is None else now
 if not isinstance(changes,dict):raise ValueError('changes must be an object')
 if set(changes)-{'stage','owner','value','due','note'}:raise ValueError('unsupported fields')
 if 'note' in changes and (not isinstance(changes['note'],str) or len(changes['note'])>2000):raise ValueError('note must be text, maximum 2000 characters')
 with db:
  db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM opportunities WHERE lead_id=?',(key,)).fetchone()
  if not row:raise ValueError('unknown opportunity')
  if row['version']!=version:raise ValueError('stale version: reload before saving')
  stage=changes.get('stage',row['stage']);owner=changes.get('owner',row['owner']);due=changes.get('due',row['due'])
  if stage!=row['stage'] and stage not in TRANSITIONS[row['stage']]:raise ValueError('invalid stage transition')
  if not isinstance(owner,str) or not 1<=len(owner.strip())<=100:raise ValueError('owner required')
  if not isinstance(due,(int,float)) or not 0<=due<=253402300799:raise ValueError('invalid due timestamp')
  if stage=='won' and row['stage']!='won' and not changes.get('note','').strip():raise ValueError('record evidence of the won outcome in note')
  cents=money(changes['value']) if 'value' in changes else row['value_cents']
  db.execute('UPDATE opportunities SET stage=?,owner=?,value_cents=?,due=?,version=version+1 WHERE lead_id=?',(stage,owner.strip(),cents,due,key))
  activity(db,key,actor,'update',json.dumps({'changes':changes,'from_stage':row['stage']},ensure_ascii=False),now)
 return {'lead_id':key,'version':version+1}

def dashboard(db,now=None):
 now=time.time() if now is None else now
 rows=[dict(r) for r in db.execute('SELECT l.id,l.name,l.email,o.* FROM opportunities o JOIN leads l ON l.id=o.lead_id')]
 for r in rows:
  r['score']=int(bool(r['consent']))*20+int(bool(r['urgency']))*30+(30 if r['value_cents']>=100000 else 10 if r['value_cents'] else 0)+(20 if r['owner']!='unassigned' else 0)
  r['overdue']=r['stage'] not in ('won','lost') and r['due']<now
  r['value']=f"{r['value_cents']/100:.2f}"
 groups={}
 for r in rows:
  g=groups.setdefault(r['source'],{'leads':0,'won':0,'won_value_cents':0});g['leads']+=1
  if r['stage']=='won':g['won']+=1;g['won_value_cents']+=r['value_cents']
 return {'currency':'USD','summary':{'leads':len(rows),'open':sum(r['stage'] not in ('won','lost') for r in rows),'overdue':sum(r['overdue'] for r in rows),'unassigned':sum(r['owner']=='unassigned' for r in rows),'open_value_cents':sum(r['value_cents'] for r in rows if r['stage'] not in ('won','lost')),'won_value_cents':sum(r['value_cents'] for r in rows if r['stage']=='won')},'by_source':groups,'leads':sorted(rows,key=lambda r:(not r['overdue'],-r['score'],r['due']))}

def seed(db):
 for i,p in enumerate([{'name':'Alice Demo','email':'alice@example.com','source':'website','value':'2400','urgency':True,'consent':True},{'name':'Bob Demo','email':'bob@example.com','source':'referral','owner':'demo-sales','value':'800','consent':True},{'name':'Casey Demo','email':'casey@example.com','source':'website','value':'100'}]):capture(db,p,'demo-'+str(i),now=time.time()-172800)

def main():
 p=argparse.ArgumentParser();p.add_argument('--db',default='leads.db');p.add_argument('command',choices=['seed','dashboard']);a=p.parse_args();db=connect(a.db)
 try:
  if a.command=='seed':seed(db)
  print(json.dumps(dashboard(db),indent=2))
 finally:db.close()
if __name__=='__main__':main()
