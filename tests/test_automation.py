import tempfile
import unittest
from pathlib import Path
from projects.automation import guest, leads, sales

ROOT = Path(__file__).resolve().parents[1]
class AutomationTests(unittest.TestCase):
    def test_guest_approval_and_escalation(self):
        self.assertEqual(guest('parking?', {'parking':'Driveway'})['status'], 'needs_approval')
        self.assertEqual(guest('refund parking', {'parking':'Driveway'})['status'], 'escalate')
        self.assertEqual(guest('pool?', {'parking':'Driveway'})['status'], 'escalate')
    def test_leads_repeated_import(self):
        with tempfile.TemporaryDirectory() as d:
            database = str(Path(d)/'leads.db')
            self.assertEqual(leads(ROOT/'examples/leads.csv', database), {'accepted':2,'rejected':1,'duplicates':1})
            self.assertEqual(leads(ROOT/'examples/leads.csv', database)['accepted'], 0)
    def test_sales_refunds(self):
        result = sales(ROOT/'examples/sales.csv')
        self.assertIn('Net sales: 480.00', result)
        self.assertIn('| 2026-10-02 | 280.00 |', result)
    def test_bad_amount(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'bad.csv'; p.write_text('date,amount\n2026-10-01,NaN\n')
            with self.assertRaises(ValueError): sales(p)
if __name__ == '__main__': unittest.main()
