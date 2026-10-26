def build_command(executable,args,platform):
    return ' '.join([executable,*args]),{'shell':True}
