# Native process arguments
Repair build_command(executable, args, platform). It returns (argv, subprocess_kwargs) for a trusted
native executable and untrusted argument strings. Preserve every argument exactly; shell syntax in
an argument is data. The call site uses subprocess.run(argv, **kwargs). On Windows, .bat/.cmd paths
(including mixed-case extensions) are explicitly outside this function's contract: raise ValueError.
Native .exe paths remain supported. Do not execute the requested application here. Keep the API,
use only stdlib, and record actual verification and platform limits in response.md.
