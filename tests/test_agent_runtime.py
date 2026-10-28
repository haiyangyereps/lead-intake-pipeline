import unittest,tempfile,json
from pathlib import Path
from agent_runtime import Journal,FixtureProvider,run_agent,tool
class RuntimeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.j=Journal(str(Path(self.tmp.name)/'test.db'))
  self.tools=[tool('propose','Queue suggestion',{'text':{'type':'string'}})]
  self.handlers={'propose':lambda a,r:self.j.propose(r,a)}
 def tearDown(self):self.j.db.close();self.tmp.cleanup()
 def run_steps(self,steps,turns=6):return run_agent(FixtureProvider(steps),self.j,'test',self.tools,self.handlers,'test',mode='scripted_fixture',max_turns=turns)
 def test_unknown_tool_denied(self):
  r=self.run_steps([('send_money',{}),'done']);self.assertIn('not allowed',r['events'][0]['result']);self.assertFalse(r['proposals'])
 def test_extra_fields_denied(self):
  r=self.run_steps([('propose',{'text':'ok','execute':True}),'done']);self.assertFalse(r['proposals']);self.assertIn('allowed fields',r['events'][0]['result'])
 def test_human_review_and_duplicate(self):
  r=self.run_steps([('propose',{'text':'ok'}),('propose',{'text':'ok'}),'done']);self.assertEqual(len(r['proposals']),1)
  p=r['proposals'][0];self.assertEqual(p['state'],'pending')
  self.assertFalse(self.j.review(p['id'],'reviewer','approved')['external_action_executed'])
  with self.assertRaises(ValueError):self.j.review(p['id'],'reviewer','approved')
 def test_model_cannot_approve(self):
  r=self.run_steps([('approve',{'reviewer':'model'}),'done']);self.assertIn('not allowed',r['events'][0]['result'])
 def test_budget(self):
  with self.assertRaises(ValueError):self.run_steps([('propose',{'text':'a'})],turns=1)
  self.assertEqual(self.j.db.execute('SELECT status FROM runs').fetchone()[0],'failed')
 def test_blank_text(self):
  r=self.run_steps([('propose',{'text':' '}),'done']);self.assertFalse(r['proposals'])
 def test_provider_failure_recorded(self):
  class Broken:
   def complete(self,*a):raise RuntimeError('provider unavailable')
  with self.assertRaises(RuntimeError):run_agent(Broken(),self.j,'test',self.tools,self.handlers,'test')
  self.assertEqual(self.j.db.execute('SELECT status FROM runs').fetchone()[0],'failed')
 def test_remote_http_rejected(self):
  from unittest.mock import patch
  from agent_runtime import Provider
  with patch.dict('os.environ',{'AI_BASE_URL':'http://123/7/14.82','AI_MODEL':'test','AI_API_KEY':'test-placeholder'}):
   with self.assertRaises(ValueError):Provider()
 def test_embedded_credentials_rejected(self):
  from unittest.mock import patch
  from agent_runtime import Provider
  with patch.dict('os.environ',{'AI_BASE_URL':'https://user:password@example.com/v1','AI_MODEL':'test','AI_API_KEY':'test-placeholder'}):
   with self.assertRaises(ValueError):Provider()
 def test_config_quotes_and_comments(self):
  from agent_runtime import load_config
  from unittest.mock import patch
  import os
  f=Path(self.tmp.name)/'env';f.write_text('# local config\nAI_MODEL="example-model"\n')
  with patch.dict(os.environ,{},clear=True):
   load_config(f);self.assertEqual(os.environ['AI_MODEL'],'example-model')
 def test_config_does_not_execute_shell(self):
  from agent_runtime import load_config
  from unittest.mock import patch
  import os
  f=Path(self.tmp.name)/'env';f.write_text('AI_MODEL=$(echo unsafe)\n')
  with patch.dict(os.environ,{},clear=True):
   load_config(f);self.assertEqual(os.environ['AI_MODEL'],'$(echo unsafe)')
 def test_http_exception_matches_exact_origin(self):
  from unittest.mock import patch
  from agent_runtime import Provider
  with patch.dict('os.environ',{'AI_BASE_URL':'http://example.com:8317/v1','AI_ALLOW_HTTP_ORIGIN':'http://example.com:8317','AI_MODEL':'test','AI_API_KEY':'test-placeholder'}):
   self.assertEqual(Provider().base,'http://example.com:8317/v1')
 def test_http_exception_does_not_authorize_other_origin(self):
  from unittest.mock import patch
  from agent_runtime import Provider
  with patch.dict('os.environ',{'AI_BASE_URL':'http://other.example.com:8317/v1','AI_ALLOW_HTTP_ORIGIN':'http://example.com:8317','AI_MODEL':'test','AI_API_KEY':'test-placeholder'}):
   with self.assertRaises(ValueError):Provider()
if __name__=='__main__':unittest.main()
