import tempfile,unittest
from pathlib import Path
from operations import connect,capture,update,dashboard
class OperationsTests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.db=connect(Path(self.t.name)/'leads.db')
 def tearDown(self):self.db.close();self.t.cleanup()
 def lead(self):return capture(self.db,{'name':'Demo','email':'demo@example.com','source':'web','value':'1200','consent':True,'urgency':True},'e1',now=0)['lead_id']
 def test_followup_priority_and_attribution(self):
  key=self.lead();r=dashboard(self.db,now=86401);self.assertEqual(r['summary']['overdue'],1);self.assertEqual(r['leads'][0]['score'],80)
  capture(self.db,{'name':'Changed','email':'demo@example.com','source':'different'},'e2',now=0)
  self.assertEqual(dashboard(self.db)['by_source']['web']['leads'],1)
 def test_stage_rules_and_version_conflicts(self):
  key=self.lead()
  with self.assertRaises(ValueError):update(self.db,key,1,'actor',{'stage':'won'})
  update(self.db,key,1,'actor',{'stage':'contacted'},now=10)
  with self.assertRaises(ValueError):update(self.db,key,1,'other',{'owner':'other'})
  self.assertEqual(self.db.execute('SELECT count(*) FROM activities').fetchone()[0],2)
 def test_won_value_and_note(self):
  key=self.lead()
  for version,stage in enumerate(('contacted','qualified','proposal'),1):update(self.db,key,version,'actor',{'stage':stage})
  with self.assertRaises(ValueError):update(self.db,key,4,'actor',{'stage':'won'})
  update(self.db,key,4,'actor',{'stage':'won','note':'Demo signed order'})
  s=dashboard(self.db)['summary'];self.assertEqual(s['won_value_cents'],120000);self.assertEqual(s['open'],0)
 def test_invalid_updates_rollback(self):
  key=self.lead()
  for changes in ({'value':'NaN'},{'due':float('nan')},{'owner':''},{'stage':'contacted','note':3}):
   with self.assertRaises((ValueError,TypeError)):update(self.db,key,1,'actor',changes)
  self.assertEqual(dashboard(self.db)['leads'][0]['version'],1)
 def test_capture_replay_repairs_profile_gap(self):
  key=self.lead();self.db.execute('DELETE FROM opportunities');self.db.commit()
  capture(self.db,{'name':'Demo','email':'demo@example.com','source':'web','value':'1200','consent':True,'urgency':True},'e1',now=0)
  self.assertEqual(len(dashboard(self.db)['leads']),1)
if __name__=='__main__':unittest.main()
