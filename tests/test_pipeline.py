import unittest,tempfile,sqlite3,threading,os,json,urllib.request,urllib.error
from pathlib import Path
from pipeline import connect,ingest,drain,serve
class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=connect(self.root/'test.db')
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def test_replay_conflict_and_normalized_duplicate(self):
  p={'name':'Alice','email':' ALICE@example.com '}
  self.assertEqual(ingest(self.db,p,'a')['status'],'accepted')
  self.assertTrue(ingest(self.db,p,'a')['replayed'])
  self.assertEqual(ingest(self.db,{'name':'A','email':'alice@example.com'},'b')['status'],'duplicate')
  with self.assertRaises(ValueError):ingest(self.db,{'name':'Changed'},'a')
  self.assertEqual(self.db.execute('SELECT count(*) FROM outbox').fetchone()[0],1)
 def test_rejection_replay(self):
  p={'name':'Alice','email':'bad@'}
  self.assertEqual(ingest(self.db,p,'a')['status'],'rejected');ingest(self.db,p,'a')
  self.assertEqual(self.db.execute('SELECT count(*) FROM rejections').fetchone()[0],1)
 def test_delivery_is_repeatable(self):
  ingest(self.db,{'name':'Alice','email':'a@example.com'},'a')
  self.assertEqual(drain(self.db,self.root/'crm.db')[0]['status'],'delivered')
  self.assertEqual(drain(self.db,self.root/'crm.db'),[])
  with sqlite3.connect(self.root/'crm.db') as crm:self.assertEqual(crm.execute('SELECT count(*) FROM contacts').fetchone()[0],1)
 def test_retry_backoff_and_dead_letter(self):
  ingest(self.db,{'name':'Alice','email':'a@example.com'},'a')
  bad=self.root/'missing'/'crm.db'
  self.assertEqual(drain(self.db,bad,now=0)[0]['attempts'],1)
  self.assertEqual(drain(self.db,bad,now=1),[])
  drain(self.db,bad,now=2)
  self.assertEqual(drain(self.db,bad,now=6)[0]['status'],'dead')
 def test_adapter_recovery_after_remote_commit(self):
  ingest(self.db,{'name':'Alice','email':'a@example.com'},'a');dest=self.root/'crm.db';drain(self.db,dest)
  self.db.execute("UPDATE outbox SET state='pending'");self.db.commit();drain(self.db,dest)
  with sqlite3.connect(dest) as crm:self.assertEqual(crm.execute('SELECT count(*) FROM contacts').fetchone()[0],1)
if __name__=='__main__':unittest.main()

class HTTPTests(unittest.TestCase):
 def test_authenticated_http_and_replay(self):
  import subprocess,sys,socket,time
  with tempfile.TemporaryDirectory() as d:
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   token='demo-only-token-1234567890123456'
   process=subprocess.Popen([sys.executable,'pipeline.py','--db',str(Path(d)/'http.db'),'serve','--port',str(port)],env={**os.environ,'INTAKE_TOKEN':token},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   def request(auth,body=b'{"name":"Alice","email":"a@example.com"}',key='http-event'):
    req=urllib.request.Request(f'http://127.0.0.1:{port}/leads',data=body,headers={'Authorization':auth,'Idempotency-Key':key,'Content-Type':'application/json'})
    return urllib.request.urlopen(req,timeout=2)
   try:
    for _ in range(60):
     try:
      with socket.create_connection(('127.0.0.1',port),timeout=.1):break
     except OSError:time.sleep(.05)
    with self.assertRaises(urllib.error.HTTPError) as error:request('wrong')
    self.assertEqual(error.exception.code,401)
    with request('Bearer '+token) as response:self.assertEqual(json.load(response)['status'],'accepted')
    with request('Bearer '+token) as response:self.assertTrue(json.load(response)['replayed'])
    with self.assertRaises(urllib.error.HTTPError) as error:request('Bearer '+token,b'not-json','bad')
    self.assertEqual(error.exception.code,400)
   finally:process.terminate();process.wait(timeout=5)
