import asyncio,unittest
import solution as s
class PairTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        tasks=[t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        for t in tasks:t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    async def test_early_error_drains_sibling(self):
        closed=asyncio.Event()
        async def first(): await asyncio.sleep(0); raise LookupError('failed')
        async def second():
            try: await asyncio.Event().wait()
            finally: await asyncio.sleep(0); closed.set()
        with self.assertRaises(LookupError): await s.run_pair(first,second,1)
        self.assertTrue(closed.is_set())
    async def test_timeout_drains(self):
        closed=[]
        async def child():
            try: await asyncio.Event().wait()
            finally: closed.append(True)
        with self.assertRaises(TimeoutError): await s.run_pair(child,child,0.01)
        self.assertEqual(len(closed),2)
    async def test_cancel_drains(self):
        closed=[]; started=asyncio.Event(); count=0
        async def child():
            nonlocal count
            try:
                count+=1
                if count==2:started.set()
                await asyncio.Event().wait()
            finally:closed.append(True)
        task=asyncio.create_task(s.run_pair(child,child,1))
        await asyncio.wait_for(started.wait(),0.5);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(len(closed),2)
    async def test_order_and_concurrency(self):
        started=[]; ready=asyncio.Event()
        def child(value):
            async def call():
                started.append(value)
                if len(started)==2: ready.set()
                await ready.wait();return value
            return call
        self.assertEqual(list(await s.run_pair(child(8),child(3),0.5)),[8,3])
if __name__=='__main__':unittest.main()
