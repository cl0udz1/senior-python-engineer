import sqlite3,tempfile,unittest
from pathlib import Path
import solution as s
class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'db.sqlite';self.connections=[]
        with sqlite3.connect(self.path) as conn:conn.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, value TEXT)')
    def connect(self):
        conn=sqlite3.connect(self.path);self.connections.append(conn);return conn
    def assert_closed(self):
        for conn in self.connections:
            with self.assertRaises(sqlite3.ProgrammingError):conn.execute('SELECT 1')
    def test_conflict_rolls_back_full_work_and_uses_fresh_connection(self):
        calls=[]
        def work(conn):
            calls.append(conn);conn.execute("INSERT INTO events VALUES (1,'ok')")
            if len(calls)==1:raise s.RetryableConflict('simulated conflict')
            return 17
        self.assertEqual(s.run_transaction(self.connect,work),17)
        self.assertEqual(len(calls),2);self.assertIsNot(calls[0],calls[1]);self.assert_closed()
        with sqlite3.connect(self.path) as conn:self.assertEqual(conn.execute('SELECT * FROM events').fetchall(),[(1,'ok')])
    def test_nonretryable_error_rolls_back_and_closes(self):
        def work(conn):
            conn.execute("INSERT INTO events VALUES (1,'no')");raise ValueError('invalid')
        with self.assertRaises(ValueError):s.run_transaction(self.connect,work)
        self.assertEqual(len(self.connections),1);self.assert_closed()
        with sqlite3.connect(self.path) as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
    def test_exhaustion_and_invalid_bound(self):
        def work(conn):raise s.RetryableConflict('still conflicting')
        with self.assertRaises(s.RetryableConflict):s.run_transaction(self.connect,work,2)
        self.assertEqual(len(self.connections),2);self.assert_closed()
        with self.assertRaises(ValueError):s.run_transaction(self.connect,work,0)
        self.assertEqual(len(self.connections),2)
if __name__=='__main__':unittest.main()
