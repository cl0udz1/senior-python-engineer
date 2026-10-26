# Dashboard degradation
Fix `dashboard` in solution.py. Each argument is an async zero-argument callable. Start the three
calls concurrently. On success, return the existing dictionary shape. A BillingError permits a
profile-only result: profile is still required; recommendations are no longer needed. Return this
fallback as soon as the profile and necessary cleanup finish. Other failures propagate. Caller
cancellation propagates. Every exit must finish cleanup of owned children; downstream operations
cooperate with cancellation. Keep the public signature and BillingError class. Use only stdlib.
Write a concise explanation and actual verification performed in response.md.
