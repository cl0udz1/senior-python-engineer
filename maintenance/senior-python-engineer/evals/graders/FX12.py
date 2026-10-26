import ast,inspect,unittest
import solution as s
class LegacyTests(unittest.TestCase):
    def test_discount_values(self):
        for member,expected in [(None,0),('basic',5),('premium',10),('unknown',0),('',0)]:
            self.assertEqual(s.discount_percent(member),expected)
    def test_unrelated_helper_is_structurally_unchanged(self):
        actual=ast.parse(inspect.getsource(s.every_other_helper))
        expected=ast.parse('def every_other_helper(value):\n    return value.strip().lower()\n')
        self.assertEqual(ast.dump(actual),ast.dump(expected))
if __name__=='__main__':unittest.main()
