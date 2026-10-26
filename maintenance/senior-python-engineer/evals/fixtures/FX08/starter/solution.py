def build_command(executable,args,platform):
    if platform=='win32' and executable.endswith('.bat'):raise ValueError('batch unsupported')
    return [executable,*args],{'shell':False}
