import json,os,socket,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.error
from pathlib import Path
class ConsoleTests(unittest.TestCase):
 def test_capture_update_authorization_and_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
   token='test-token-with-24-characters-123'
   p=subprocess.Popen([sys.executable,'app.py','--db',str(Path(d)/'db.sqlite'),'--port',str(port)],env={**os.environ,'INTAKE_TOKEN':token},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   def call(path,body=None,auth=True,origin=None):
    headers={'Authorization':'Bearer '+token if auth else 'wrong','Idempotency-Key':'console-event','Content-Type':'application/json'}
    if origin:headers['Origin']=origin
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    with urllib.request.urlopen(req,timeout=2) as response:return json.load(response)
   try:
    for _ in range(60):
     try:
      with socket.create_connection(('127.0.0.1',port),timeout=.1):break
     except OSError:time.sleep(.05)
    with self.assertRaises(urllib.error.HTTPError) as e:call('/api/dashboard',auth=False)
    self.assertEqual(e.exception.code,401)
    with self.assertRaises(urllib.error.HTTPError) as e:call('/api/leads',{'name':'A','email':'a@example.com'},origin='https://other.example')
    self.assertEqual(e.exception.code,403)
    r=call('/api/leads',{'name':'A','email':'a@example.com','value':'100'});key=r['lead_id']
    r=call(f'/api/leads/{key}',{'version':1,'actor':'tester','changes':{'stage':'contacted','owner':'sales'}});self.assertEqual(r['version'],2)
    with self.assertRaises(urllib.error.HTTPError) as e:call(f'/api/leads/{key}',{'version':1,'actor':'tester','changes':{'owner':'other'}})
    self.assertEqual(e.exception.code,400)
    r=call('/api/dashboard');self.assertEqual(r['leads'][0]['stage'],'contacted');self.assertEqual(len(call(f'/api/leads/{key}/activities')),2)
   finally:p.terminate();p.wait(timeout=5)
if __name__=='__main__':unittest.main()
