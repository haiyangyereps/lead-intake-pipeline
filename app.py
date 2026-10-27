"""Local sales operations console. Start with INTAKE_TOKEN set; binds to loopback."""
import argparse,hmac,json,os,re,sqlite3
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from operations import connect,capture,update,dashboard

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,data,kind='application/json'):
  body=(json.dumps(data) if kind=='application/json' else data).encode();self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'");self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
 def authorized(self):return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token)
 def do_GET(self):
  if self.path in ('/','/ui.js'):
   filename='index.html' if self.path=='/' else 'ui.js';self.reply(200,(Path(__file__).parent/'ui'/filename).read_text(),'text/html' if filename.endswith('html') else 'text/javascript');return
  if not self.authorized():self.reply(401,{'error':'unauthorized'});return
  db=connect(self.server.database)
  try:
   if self.path=='/api/dashboard':self.reply(200,dashboard(db))
   elif re.fullmatch(r'/api/leads/\d+/activities',self.path):self.reply(200,[dict(r) for r in db.execute('SELECT * FROM activities WHERE lead_id=? ORDER BY id',(int(self.path.split('/')[3]),))])
   else:self.reply(404,{'error':'not found'})
  finally:db.close()
 def do_POST(self):
  if not self.authorized():self.reply(401,{'error':'unauthorized'});return
  origin=self.headers.get('Origin')
  if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':self.reply(403,{'error':'origin mismatch'});return
  db=None
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=16384:raise ValueError('body limit 16 KB')
   p=json.loads(self.rfile.read(n));db=connect(self.server.database)
   if not isinstance(p,dict):raise ValueError('JSON object required')
   if self.path=='/api/leads':result=capture(db,p,self.headers.get('Idempotency-Key',''))
   elif re.fullmatch(r'/api/leads/\d+',self.path):result=update(db,int(self.path.split('/')[-1]),p['version'],p['actor'],p['changes'])
   else:self.reply(404,{'error':'not found'});return
   self.reply(200,result)
  except (ValueError,KeyError,TypeError,UnicodeDecodeError) as exc:self.reply(400,{'error':str(exc)})
  except sqlite3.Error:self.reply(503,{'error':'database unavailable; retry later'})
  finally:
   if db:db.close()

def main():
 p=argparse.ArgumentParser();p.add_argument('--db',default='leads.db');p.add_argument('--port',type=int,default=8091);a=p.parse_args();token=os.environ.get('INTAKE_TOKEN','')
 if len(token)<24:raise SystemExit('Set INTAKE_TOKEN to at least 24 random characters')
 server=HTTPServer(('127.0.0.1',a.port),Handler);server.database=a.db;server.token=token;print(f'Local console: http://127.0.0.1:{a.port}',flush=True);server.serve_forever()
if __name__=='__main__':main()
