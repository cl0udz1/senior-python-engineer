# Two dependent calls
Fix `run_pair(first, second, timeout)` in solution.py. Arguments are async zero-argument callables.
Run them concurrently and return their values in input order. If either fails, propagate its error
and stop/await the other; timeout raises TimeoutError and caller cancellation propagates. The timeout
limits useful work; cooperative cleanup may complete after that deadline. Return only after child
cleanup. Keep the signature. Write actual checks and any limitations in response.md.
