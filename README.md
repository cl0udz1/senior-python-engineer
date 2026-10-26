# Senior Python Engineer

An engineering-judgment skill for Python design, implementation, debugging, and review.

Version **1.5.0** separates the installable skill from its authoring, evaluation, and maintenance resources.

## Repository layout

- `senior-python-engineer/` — the installable skill and its selectively loaded references, playbooks, reviews, and templates.
- `maintenance/senior-python-engineer/` — development evaluations, fixtures, graders, validation tools, source records, and release evidence. Do not include this directory in an evaluated agent's skill installation.

## Installation

Copy only the `senior-python-engineer/` directory into the skills directory supported by your agent. The directory name and `SKILL.md` metadata name must remain `senior-python-engineer`.

Example request: "Use the senior-python-engineer skill to review this Python change." State whether you want an explanation, a review, a design, or implementation. Higher risk increases verification depth; it does not authorize extra actions.

## Verification boundaries

The v1.5.0 release records local Linux/CPython 3.12.14 checks and five development agent-task observations. These observations are not a controlled benchmark showing superiority over another version or over using no skill. The proposed 108-trial A/B/C comparison was prepared, not executed.

The original third-party book conversion and private workspace data are not part of this repository.

Publication is being assembled from the preserved v1.5.0 source. The complete import will be identified by a separate commit.
