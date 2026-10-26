# Typing

## Contents

- [The model](#the-model)
- [Core constructs](#core-constructs)
- [Narrowing](#narrowing)
- [Structural vs nominal](#structural-vs-nominal)
- [Where typing pays vs where it doesn't](#where-typing-pays-vs-where-it-doesnt)
- [Checkers and strictness](#checkers-and-strictness)
- [Anti-pattern: type machinery harder than the runtime](#anti-pattern-type-machinery-harder-than-the-runtime)
- [Annotations vs runtime validation (I1)](#annotations-vs-runtime-validation-i1)
- [Deferred annotations (Python 3.14+) LANGUAGE](#deferred-annotations-python-314-language)
- [Library authoring notes](#library-authoring-notes)

Operational reference for gradual typing. Version-sensitive facts live only in
[modern-python-baseline.md](modern-python-baseline.md); the typing spec is a living specification
[STANDARD], so verify constructs against the current spec, not blog posts. Invariants referenced as
I1–I16 from [python-invariants.md](../core/python-invariants.md).

## The model

- Python has a **gradual** type system [STANDARD]: typed and untyped code interoperate; `Any` is
  compatible with everything; type checkers infer where annotations are absent. "Gradual" is the design,
  not an unfinished state of strictness.
- **Annotations are not runtime validation (I1)** [STANDARD]. `def f(x: int)` does not reject `f("a")`
  at runtime; annotations are metadata consumed by static checkers, IDEs, documentation, and separate
  runtime-validation libraries (see the mapping table below). Enforcement at trust boundaries needs
  explicit runtime validators ([security.md](security.md)).
- The typing spec is a **living spec** maintained outside the PEP process; typing PEPs (e.g. PEP 695
  type-parameter syntax, PEP 742 `TypeIs`) are folded into it. When a PEP and a blog post disagree,
  the spec wins.
- Types are static claims about runtime behavior. When the two diverge, the runtime is reality: fix the
  annotation or the code, never "satisfy the checker" with a cast that hides a real bug.

## Core constructs

| Construct | What it buys | Cost / caution |
|---|---|---|
| `TypeVar` / generics | Reusable typed containers and functions | Inference gets brittle with many constrained params |
| PEP 695 syntax (`def f[T](…)`, `type X[T] = …`, `class Box[T]:`) | Compact scoped type parameters. Variance is **inferred from use** and may be invariant, covariant, or contravariant [STANDARD] | `TypeVarTuple` and `ParamSpec` stay invariant. Requires a recent baseline ([baseline](modern-python-baseline.md)) |
| `ParamSpec` / `Concatenate` | Preserves wrapped-callable signatures (decorators, callbacks) | Comprehension cost is high — use where signatures actually propagate |
| `TypedDict` | Exact dict shapes with required/optional keys | Static-only; dicts still validate at runtime only if you add a validator (I1) |
| `Literal["a","b"]` | Closed value sets; exhaustiveness via `assert_never` | Every new allowed value is a type change |
| `LiteralString` (PEP 675) | Static claim that a string was composed only from literals, so untrusted data cannot be interpolated into it | Not a runtime check, and not a check that a literal is a safe value (a literal URL can still be an unsafe destination). Pair with parameter binding for SQL |
| `Never` | Bottom type: no values. Added in Python 3.11 | Same type-system meaning as `NoReturn`. Prefer `Never` for unreachable values (`assert_never`). `NoReturn` remains valid for functions that never return. Not PEP 654 (that PEP is `ExceptionGroup`) |
| `Annotated[T, meta]` | Attaches metadata (constraints, docs, units) for consumers | Semantics of metadata belong to the consuming tool, not to checkers |
| `Self` | Correct fluent/subclass return types | Don't confuse with `TypeVar("Self")` shims in older code |
| `NewType` | Distinct-from-`int`/`str` ids (UserId vs OrderId) | Zero-ish runtime cost, **no runtime validation**; erased for consumers expecting the base type |
| `@overload` | Multiple precise input→output signatures | Implementation signature is not checked against callers; drift risk |
| `Protocol` | Structural subtyping: fits by shape, no inheritance | Runtime `isinstance` on `@runtime_checkable` checks names only, not signatures |
| `TypeGuard` (PEP 647) | Custom `isinstance`-style narrowing in the positive branch | Does not narrow the negative branch |
| `TypeIs` (PEP 742) | Narrows **both** branches (positive and negative) | Its positive and negative claims must be sound; a checker cannot prove the predicate's runtime behavior |

## Narrowing

- Checkers narrow on `isinstance`, `issubclass`, `is None`, `==`/`in` against `Literal`s, `assert`, and
  user predicates typed `TypeGuard`/`TypeIs` [STANDARD].
- Narrowing is flow-sensitive and fragile across function boundaries: values passed to another function
  and returned are re-widened unless the signature says otherwise. Encode the invariant in the signature
  (`TypeIs`, `overload`, `Literal`) rather than in call-site comments.
- `assert_never(x)` (where `x: Never`) after an exhaustive `Literal`/`Union` match turns "forgot a case"
  into a static type-checker error; keep the runtime fallback honest (raises `AssertionError` at runtime).

## Structural vs nominal

- `Protocol` = structural: any object with the right shape satisfies it, no inheritance required.
  Use for library boundaries where you don't control the implementations (iterables, "anything with
  `.read()`").
- `ABC` = nominal: explicit registration/inheritance, can carry implementation and abstract methods.
  Use when the base class enforces a template method or the identity of the hierarchy matters.
- Decision criteria in [Decision Model §2](../core/decision-model.md); both are better than building
  parallel class hierarchies purely for typing.

## Where typing pays vs where it doesn't

| Pays (invest here) | Pays less (keep it light) |
|---|---|
| Public library APIs — users' checkers become your contract | Transient locals inside one function |
| Shared domain models across modules/services | Throwaway scripts and one-shot analysis |
| Refactoring-sensitive code (large, changing, multi-team) | Boilerplate data plumbing with no invariants |
| Complex call contracts (callbacks, decorators, generics) | Type gymnastics that need a diagram to parse |
| Cross-boundary payloads (TypedDict/Pydantic at I/O edges) | Re-annotating everything on day one of a migration |

- The return on typing is defect prevention per unit of annotation complexity. If a signature takes more
  thought to read than the body, simplify the contract first; use `Any` only when the dynamic boundary
  is intentional and its lost checks are acceptable.

## Checkers and strictness

- **mypy** and **Pyright** are both mature [ECOSYSTEM] and both adoptable gradually. Real differences:
  inference aggressiveness, error taxonomy, config semantics, plugin ecosystems, and speed on large
  codebases. Choosing one is a team-tooling decision; what matters operationally is **one checker pinned
  in CI** with recorded config by default. A second checker can add value when its distinct checks
  justify the configuration and disagreement cost.
  [HEURISTIC]: pick the one the repo already runs; on greenfield, run both once on a spike and keep the
  one whose failure modes your team understands.
- **Strictness is team policy, not a Python property** [STANDARD]. Adopt incrementally: per-module
  `disallow_untyped_defs`, explicit `Any` budgets, `warn_unused_ignores` on. `--strict` everywhere on a
  large legacy codebase produces ignore-comment noise instead of safety.
- `# type: ignore` discipline: every ignore names the problem it suppresses or is reviewed like a TODO.
  Bare ignores accumulate until the type claim is fiction.

## Anti-pattern: type machinery harder than the runtime

- Warning sign: generics with 4+ type parameters, `TypeVar` bounds referencing each other, protocols
  whose satisfaction can only be proven by the checker. If a maintainer must model the checker to
  understand the function, the type has become a second program — and an untested one.
- `typing.cast` does nothing at runtime. A cast that asserts what code should guarantee is a swallowed
  test. Prefer `assert isinstance(...)` where the check is cheap and the claim matters (narrowing with
  evidence), or fix the signature.
- `Any` is a documented escape hatch, not a sin — but each one states a reason (boundary with untyped
  third party, deliberate dynamism) so the gradual boundary is intentional, not accidental.

## Annotations vs runtime validation (I1)

Which representation to use when data crosses a boundary:

| Shape need | Static tool | Runtime behavior | Use when |
|---|---|---|---|
| Dict-shaped payload | `TypedDict` | Nothing at runtime unless paired with a validator | Config/API payloads consumed as dicts |
| Record with fields/defaults | `dataclass` | Coercion-free construction; no validation | Internal records already trusted (I1 satisfied elsewhere) |
| Validated boundary model | Pydantic model | Validation on construction; coercion depends on model settings | Network/storage/user input when constructing the model is the boundary |
| Validated boundary model | attrs with explicit validators/converters | Configured validators/converters run on construction; annotations alone do not validate | Custom validation policy on object construction |
| Validated boundary model | msgspec typed decoder / `convert` | Validates on typed decoding/conversion; ordinary `Struct(...)` construction does not type-check fields | Serialized messages or decoded Python data at a boundary |
| Behavior-bearing domain object | Class + methods + invariants in `__post_init__`/factory | Enforces invariants on creation | Core domain rules that must hold everywhere |

- `dataclasses` are not domain models by default (banned slogan: "dataclasses are domain models") — they
  are structured records; the domain model is what enforces invariants and names behavior.
- Validation library choice is [FRAMEWORK]/[ECOSYSTEM]; the invariant is *where* validation happens:
  once, at the boundary, producing a typed shape downstream code can trust.
- `typing.get_type_hints`, Pydantic model building, and `annotationlib.get_annotations` run annotation
  code at runtime — if that runs at import of a hot module, it is import-time work (I3). Evaluating
  annotations can execute arbitrary code; do not evaluate annotations taken from untrusted objects.

## Deferred annotations (Python 3.14+) [LANGUAGE]

PEP 649 and PEP 749, implemented in 3.14: annotations are no longer evaluated when the function, class,
or module is defined. They are evaluated when introspected, unless the file uses
`from __future__ import annotations`, which still stores them as strings. PEP 749 keeps that
behavior at least until Python 3.13's end of life. Deprecation starts no sooner than the first
release after that, and removal is later still. 3.14 does not change the future import. Forward
references no longer need quotes on 3.14 without it.

- Most annotated code keeps working. Code that **reads** annotations may not: do not assume
  `__annotations__` is an already-evaluated dict of live objects, and do not read class annotations off
  an instance.
- Introspect with `annotationlib.get_annotations` on 3.14+ (`Format.VALUE`, `Format.FORWARDREF`, or
  `Format.STRING`). On 3.10–3.13, `inspect.get_annotations` is the documented helper.
  `typing_extensions` backports part of the 3.14 API for cross-version code.
- Deferred evaluation does not make annotations runtime validation (I1). A library that validates at a
  boundary still has to run a validator.

## Library authoring notes

- Public function signatures are API: over-annotate them even when internals stay light
  ([packaging.md](packaging.md) for distribution; [typing.md](typing.md) is this file).
- Ship `py.typed` when the package claims typed support [STANDARD]; dropping it is a silent contract
  break for downstream checkers.
- Prefer `collections.abc.Callable`/`Iterable`/`Mapping` over `typing.Callable` etc. (legacy aliases
  [LEGACY] — keep them working, don't add new uses in new code).
