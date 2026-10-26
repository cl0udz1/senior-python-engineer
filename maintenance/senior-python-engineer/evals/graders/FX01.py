import asyncio
import unittest
import solution as s

class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self):
        current=asyncio.current_task()
        pending=[t for t in asyncio.all_tasks() if t is not current and not t.done()]
        for task in pending: task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)

    async def test_billing_failure_preserves_profile_and_drains_optional(self):
        ready=asyncio.Event(); closed=asyncio.Event(); profiled=asyncio.Event()
        async def profile():
            await ready.wait(); await asyncio.sleep(0); profiled.set(); return {'id':7}
        async def billing():
            await asyncio.sleep(0); ready.set(); raise s.BillingError('unavailable')
        async def recommendations():
            try: await asyncio.Event().wait()
            finally: closed.set()
        result=await asyncio.wait_for(s.dashboard(profile,billing,recommendations),0.5)
        self.assertEqual(result,{'profile':{'id':7},'billing':None,'recommendations':[]})
        self.assertTrue(profiled.is_set()); self.assertTrue(closed.is_set(),'optional cleanup not awaited')

    async def test_success_is_concurrent(self):
        started=set(); all_started=asyncio.Event()
        def child(name):
            async def call():
                started.add(name)
                if len(started)==3: all_started.set()
                await all_started.wait(); return name
            return call
        result=await asyncio.wait_for(s.dashboard(*(child(x) for x in ['p','b','r'])),0.5)
        self.assertEqual(result,{'profile':'p','billing':'b','recommendations':'r'})

    async def test_profile_failure_propagates_and_stops_others(self):
        closed=set(); ready=asyncio.Event()
        async def profile():
            await ready.wait(); raise LookupError('missing')
        def other(name):
            async def call():
                try:
                    closed.add(name+'-started')
                    if len(closed)==2: ready.set()
                    await asyncio.Event().wait()
                finally: closed.add(name+'-closed')
            return call
        with self.assertRaises(LookupError):
            await asyncio.wait_for(s.dashboard(profile,other('b'),other('r')),0.5)
        self.assertIn('b-closed',closed); self.assertIn('r-closed',closed)

    async def test_other_error_propagates_after_cleanup(self):
        closed=asyncio.Event()
        async def profile():
            try: await asyncio.Event().wait()
            finally: closed.set()
        async def billing(): await asyncio.sleep(0); return 'ok'
        async def recommendations(): await asyncio.sleep(0); raise ValueError('bad')
        with self.assertRaises(ValueError):
            await asyncio.wait_for(s.dashboard(profile,billing,recommendations),0.5)
        self.assertTrue(closed.is_set())

    async def test_caller_cancellation_drains_all_children(self):
        started=set(); closed=set(); ready=asyncio.Event()
        def child(name):
            async def call():
                try:
                    started.add(name)
                    if len(started)==3: ready.set()
                    await asyncio.Event().wait()
                finally:
                    await asyncio.sleep(0); closed.add(name)
            return call
        task=asyncio.create_task(s.dashboard(*(child(x) for x in 'pbr')))
        await asyncio.wait_for(ready.wait(),0.5); task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(closed,set('pbr'))

if __name__=='__main__': unittest.main()
