import tempfile,unittest
from pathlib import Path
from agent import configure
from agent_runtime import Journal
class DomainTests(unittest.TestCase):
 def test_unknown_lead_denied(self):
  with tempfile.TemporaryDirectory() as d:
   j=Journal(str(Path(d)/'j.db'));_,h,_=configure(str(Path(d)/'leads.db'),j)
   with self.assertRaises(ValueError):h['propose_follow_up']({'lead_id':999,'recommendation':'Contact now'},'r')
   self.assertEqual(j.db.execute('SELECT COUNT(*) FROM proposals').fetchone()[0],0)
 def test_read_redacts_names_and_emails(self):
  with tempfile.TemporaryDirectory() as d:
   j=Journal(str(Path(d)/'j.db'));_,h,_=configure(str(Path(d)/'leads.db'),j)
   for row in h['list_open_leads']({},'r'):
    self.assertNotIn('email',row);self.assertNotIn('name',row)
