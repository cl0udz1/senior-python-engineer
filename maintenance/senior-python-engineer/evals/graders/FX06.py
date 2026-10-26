import unittest
import solution as s
class MigrationTests(unittest.TestCase):
    def test_old_write_after_backfill(self):
        row={'status':'pending','status_v2':'pending'};row['status']='paid'
        self.assertEqual(s.read_status(row,'mixed'),'paid')
    def test_new_write_keeps_old_reader_compatible(self):
        row={'status':'pending','status_v2':'pending'};s.new_write(row,'failed')
        self.assertEqual(row,{'status':'failed','status_v2':'failed'})
    def test_finalize_refuses_active_writers_and_reconciles(self):
        row={'status':'paid','status_v2':'pending'}
        with self.assertRaises(ValueError):s.finalize(row,old_writers_active=True)
        self.assertEqual(row['status_v2'],'pending')
        s.finalize(row,old_writers_active=False);self.assertEqual(s.read_status(row,'new_only'),'paid')
    def test_incomplete_and_unknown_phase_are_errors(self):
        with self.assertRaises(ValueError):s.read_status({'status':'paid','status_v2':None},'new_only')
        with self.assertRaises(ValueError):s.read_status({'status':'paid'},'typo')
if __name__=='__main__':unittest.main()
