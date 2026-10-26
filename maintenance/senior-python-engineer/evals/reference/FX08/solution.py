from pathlib import PureWindowsPath
def build_command(executable,args,platform):
    if platform=='win32' and PureWindowsPath(executable).suffix.lower() in {'.bat','.cmd'}:
        raise ValueError('batch scripts are outside this native-executable contract')
    return [executable,*args],{'shell':False}
