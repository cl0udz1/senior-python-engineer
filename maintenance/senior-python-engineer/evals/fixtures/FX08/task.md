# Windows boundary in a native-only launcher
The launcher must reject Windows batch-script paths before returning a command, because this API
promises native-executable argument handling only. Repair build_command(executable,args,platform).
For platform='win32', reject .bat and .cmd in any letter case; preserve valid native paths and all
argument strings. For other platforms keep native argument-vector execution. The return shape is
(argv, kwargs) consumed by subprocess.run. Document actual checks and what you could not test in
response.md. No new dependencies or automatic shell-based fallback.
