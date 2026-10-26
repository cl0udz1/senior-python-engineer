import json,subprocess,sys,unittest
import solution as s
class CommandTests(unittest.TestCase):
    def test_native_arguments_round_trip(self):
        args=['spaced word','x; echo injected','$(echo injected)','quote"x','', 'one&two']
        argv,kwargs=s.build_command(sys.executable,['-c','import json,sys; print(json.dumps(sys.argv[1:]))',*args],sys.platform)
        self.assertIsInstance(argv,(list,tuple));self.assertIs(kwargs.get('shell'),False)
        result=subprocess.run(argv,**kwargs,capture_output=True,text=True,timeout=3,check=True)
        self.assertEqual(json.loads(result.stdout),args)
    def test_windows_batch_is_rejected(self):
        for name in ['tool.cmd','tool.BAT',r'C:\tools\Run.CmD']:
            with self.assertRaises(ValueError):s.build_command(name,['untrusted&arg'],'win32')
    def test_native_windows_path_is_preserved(self):
        name=r'C:\Program Files\native.cmd.exe';argv,kwargs=s.build_command(name,['x&y'],'win32')
        self.assertEqual(list(argv),[name,'x&y']);self.assertIs(kwargs.get('shell'),False)
if __name__=='__main__':unittest.main()
