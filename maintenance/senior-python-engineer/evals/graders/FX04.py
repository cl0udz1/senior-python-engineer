import copy,unittest
import solution as s
class Store:
    def __init__(self):self.rows={};self.fail_paid=False
    def get(self,key):return copy.deepcopy(self.rows.get(key))
    def save(self,key,value):
        if value['status']=='paid' and self.fail_paid:self.fail_paid=False;raise OSError('crash before save')
        self.rows[key]=copy.deepcopy(value)
class Provider:
    def __init__(self,store,timeout=False):self.store=store;self.accepted={};self.calls=0;self.timeout=timeout
    def charge(self,key,cents):
        self.calls+=1
        assert any(r['key']==key and r['cents']==cents for r in self.store.rows.values()),'intent must precede charge'
        if key in self.accepted:
            assert self.accepted[key][0]==cents;return self.accepted[key][1]
        receipt='receipt-'+str(len(self.accepted)+1);self.accepted[key]=(cents,receipt)
        if self.timeout:self.timeout=False;raise TimeoutError('accepted then response lost')
        return receipt
class PaymentTests(unittest.TestCase):
    def test_timeout_then_redelivery_one_acceptance(self):
        store=Store();provider=Provider(store,True)
        first=s.checkout('a',1200,store,provider);self.assertEqual(first['status'],'pending')
        paid=s.checkout('a',1200,store,provider);self.assertEqual(paid['status'],'paid')
        self.assertEqual(len(provider.accepted),1)
        calls=provider.calls;self.assertEqual(s.checkout('a',1200,store,provider),paid);self.assertEqual(provider.calls,calls)
    def test_crash_after_acceptance_recovers(self):
        store=Store();store.fail_paid=True;provider=Provider(store)
        with self.assertRaises(OSError):s.checkout('b',99,store,provider)
        paid=s.checkout('b',99,store,provider)
        self.assertEqual(paid['status'],'paid');self.assertEqual(len(provider.accepted),1)
    def test_amount_mismatch_does_not_call_provider(self):
        store=Store();provider=Provider(store,True);s.checkout('c',100,store,provider)
        calls=provider.calls
        with self.assertRaises(ValueError):s.checkout('c',200,store,provider)
        self.assertEqual(provider.calls,calls)
    def test_distinct_orders_have_distinct_identity(self):
        store=Store();provider=Provider(store)
        s.checkout('one',42,store,provider);s.checkout('two',42,store,provider)
        self.assertEqual(len(provider.accepted),2)
if __name__=='__main__':unittest.main()
