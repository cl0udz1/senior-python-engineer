# Review: `solution.py`

## Findings

**No significant issue found.** The implementation satisfies the stated contract for inputs that are `None` or strings:

- `solution.py:2` returns `0` for `None`.
- `solution.py:3` returns `5` for `'basic'` and `10` for `'premium'`.
- The default passed to `dict.get` on `solution.py:3` returns `0` for every other string. Matching is exact, consistent with the named membership values in the contract.

No code change or redesign is warranted by this review.

## Verification performed

Executed a focused standard-library check with `python -B -`, loading `solution.py` through `runpy.run_path` and asserting these results:

| Input | Expected and observed result |
|---|---:|
| `None` | 0 |
| `'basic'` | 5 |
| `'premium'` | 10 |
| `''` | 0 |
| `'unknown'` | 0 |
| `'Basic'` | 0 |
| `'PREMIUM'` | 0 |
| `' basic '` | 0 |
| `'会员'` | 0 |

All nine checks passed; the process exited with status `0`. These were focused checks, not a broader project test suite.

## Scope and limits

Reviewed the complete three-line helper against `TASK.md` using a proportionate correctness review. Behavior for other input types is outside the supplied contract. No code or configuration was edited, and no dependencies were installed.

## Skill resources consulted

- `SKILL.md`: review mode, scope, and proportionate verification.
- `reviews/code-review.md`: review contract and code-review procedure.
- `core/python-invariants.md`: I1, I16, and the guidance on using invariants in reviews.
