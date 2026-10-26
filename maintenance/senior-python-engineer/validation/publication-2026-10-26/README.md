# Publication verification — 26 October 2026

The v1.5.0 source was recovered from the saved Library project, not regenerated. Before publication it contained 203 files. All 55 runtime files exactly matched the original release manifest (633,743 bytes). The root README was then updated for the public repository, and this verification directory was added. Operational skill files remain unchanged.

## Fresh local checks

Environment: CPython 3.13.5, Linux. These are new publication checks; they do not replace the original CPython 3.12.14 release evidence.

| Check | Result |
|---|---|
| Package integrity | Passed, including 1,817 local links/heading targets |
| Package/evaluation tool tests | 19 passed |
| Mechanism probes | 19 passed |
| Fixture machinery | Nine broken starters failed; nine references passed; three design/review structural checks passed |
| Claim-register structure/age | 25 records passed for 2026-10-26; offline check, not live factual verification |
| Runtime manifest | All 55 paths, byte lengths, and SHA-256 hashes matched |

Aggregate test commands initially hit the execution environment's command-time limit. The unit-test rerun completed. Fixture selftests were run in smaller case subsets with the original selftest and graders, and their results were combined. Interrupted attempts are not additional agent evaluations.

The package scan found no common credential-token shapes, private ChatGPT Library/Space/conversation links, or private file/user identifiers. This was a bounded pattern scan, not a guarantee of exhaustive secret detection.

## Files

- `restored-source-inventory.json`: identities of the recovered 203-file source before the publication README change and this directory's addition.
- `package-integrity.json`: fresh validator output.
- `tool-tests.txt`: completed unittest output.
- `python-semantics.json`: interpreter, platform, probe results, and exclusions.
- `fixture-selftest.json`: complete split-run fixture checks, with no agent-performance claim.
- `source-check.txt`: offline source-register check.

No A/B/C model benchmark was executed during publication. No deployment or installation in the user's local agent environment is implied by publishing this repository.
