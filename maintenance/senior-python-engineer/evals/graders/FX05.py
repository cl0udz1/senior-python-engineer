import unittest
import solution as s
class LookupTests(unittest.TestCase):
    def test_all_hashable_keys_and_present_none(self):
        values={'':None,0:'zero',('a',2):17,'x':False}
        lookup=s.FastLookup(values)
        for key,value in values.items():self.assertIs(lookup.get(key,object()),value)
    def test_missing_returns_default_identity(self):
        lookup=s.FastLookup({'a':1});marker=object()
        self.assertIs(lookup.get('missing',marker),marker);self.assertIsNone(lookup.get('missing'))
    def test_matches_base_behavior(self):
        base=s.Lookup({'a':2});fast=s.FastLookup({'a':2})
        for key in ['a','',None,0,('a',)]:self.assertEqual(base.get(key,'fallback'),fast.get(key,'fallback'))
if __name__=='__main__':unittest.main()
