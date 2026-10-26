# Language Semantics

## Contents

- [Names, objects, identity, type, value](#names-objects-identity-type-value)
- [Scopes and closures](#scopes-and-closures)
- [Descriptors, properties, decorators, bound methods](#descriptors-properties-decorators-bound-methods)
- [Dunder methods and data-model protocols](#dunder-methods-and-data-model-protocols)
- [Iteration, generators, iterators](#iteration-generators-iterators)
- [Context managers](#context-managers)
- [MRO and cooperative multiple inheritance](#mro-and-cooperative-multiple-inheritance)
- [Import semantics](#import-semantics)
- [Garbage collection: language guarantee vs CPython behavior](#garbage-collection-language-guarantee-vs-cpython-behavior)
- [What "Pythonic" means](#what-pythonic-means)

Operational reference for Python's data model and execution semantics. Version-sensitive facts live only
in [modern-python-baseline.md](modern-python-baseline.md). Invariants are referenced as I1–I16 from
[python-invariants.md](../core/python-invariants.md); layer tags per [SKILL.md](../SKILL.md#knowledge-classification).

## Names, objects, identity, type, value

- A name is a binding to an object, not a typed storage slot [LANGUAGE]. Assignment binds; it does not
  copy. `a = b` makes both names reference the same object.
- Every object has **identity** (`is`), **type** (`type(x)`), and **value** (`==` via `__eq__`) [LANGUAGE].
  Mutability is a property of the object's type, not of the name.
- `is` tests identity and never lies; `==` invokes overridable equality semantics and can return non-bool
  or raise. Use `is` for `None` and explicit sentinels; use `==` for value comparison. `x is y` implies
  `x == y` only because default equality falls back to identity — do not assume it for custom types.
- Defining `__eq__` sets `__hash__` to `None` unless you also define `__hash__` [LANGUAGE]. A type used in
  sets/dicts needs a hash consistent with its equality. Unhashable = usable as dict value, not key.
- Aliasing + mutation is the root of most "impossible" state bugs: two owners of one mutable object
  ([invariant I4](../core/python-invariants.md)). Copying: `copy.copy` is shallow (nested mutables still
  shared); `copy.deepcopy` is recursive and can be expensive or fail on un-copyable objects.
- Mutable default arguments are created once at function definition; use `None` + create-per-call. The
  documented exceptions are in [Anti-Patterns](../catalogs/anti-patterns.md).
- Augmented assignment (`x += y`) tries `__iadd__` and assigns its result back to the target. The
  method may mutate and return `self`, return another object, or return `NotImplemented` to request
  the ordinary addition fallback [LANGUAGE]. Its presence alone does not prove in-place mutation.
  See the [data model](https://docs.python.org/3.14/reference/datamodel.html#object.__iadd__).

## Scopes and closures

- Name resolution order: local → enclosing function → global → builtins [LANGUAGE]. Class bodies are
  **not** enclosing scopes: a nested function inside a method sees the method's variables, not the class
  body's (access class state via `self`, the class object, or descriptors).
- Closures capture the *variable*, not a value snapshot (late binding). A closure over a loop variable
  sees the final value; bind per-iteration (default argument or `functools.partial`) when behavior matters.
- `global`/`nonlocal` declare which scope a rebinding targets. `del name` unbinds; it does not destroy
  the object (see garbage collection below).
- Shared closure state is shared mutable state: same ownership rules as any other shared object (I4).

## Descriptors, properties, decorators, bound methods

- The descriptor protocol (`__get__`, `__set__`, `__delete__`, `__set_name__`) is the mechanism behind
  properties, methods, `classmethod`, `staticmethod`, and `__slots__` [LANGUAGE].
- Defining `__set__` **or** `__delete__` makes a descriptor a data descriptor [LANGUAGE]. During
  ordinary instance reads, a data descriptor **with `__get__`** takes precedence over the instance
  dictionary; non-data descriptors and other class attributes follow it. Without `__get__`, it does
  not override an instance dictionary value on read. Custom `__getattribute__` can change lookup. See the
  [descriptor rules](https://docs.python.org/3.14/reference/datamodel.html#invoking-descriptors).
- Functions are non-data descriptors: `f.__get__(obj)` yields a **bound method** — this is where `self`
  comes from. Passing `Class.method` unbound is the same function object.
- `property` is a data descriptor: `@x.setter` / `@x.deleter` register variants. Properties may run
  arbitrary code on access — cheap-looking attribute access can hide work (relevant to performance
  review, not just style).
- Decorators apply when the decorated definition executes [LANGUAGE]. A module-level definition
  normally executes during import; a nested definition can execute later on each enclosing call.
  Keep module-level decorators cheap and side-effect-controlled (I3). Stacked decorators apply
  bottom-up. See [function definitions](https://docs.python.org/3.14/reference/compound_stmts.html#function-definitions).
- `functools.wraps` preserves `__name__`, `__doc__`, and sets `__wrapped__`. Decorators that replace a
  signature must preserve it (`__signature__`) or tooling and callers will be misled; typing consequences
  in [typing.md](typing.md).

## Dunder methods and data-model protocols

- Operators map to dunders (`__add__`/`__radd__`, `__lt__`, `__eq__`…); Python calls the reflected method
  when the left operand's type doesn't support the operation or returns `NotImplemented` [LANGUAGE].
- Container protocol: `__len__`, `__getitem__`, `__contains__`, `__iter__`; truthiness is `__bool__`, then
  `__len__` [LANGUAGE]. Prefer `collections.abc` (Iterable/Sequence/Mapping…) over ad-hoc shapes —
  these are the structural protocols the language actually operates on.
- Attribute hooks: `__getattr__` runs only when normal lookup *fails*; `__getattribute__` runs always and
  is easy to get wrong (recursion). `__slots__` trades dynamic attributes for memory/attribute guarantees.
- String forms: `__repr__` is unambiguous/debug-oriented, `__str__` is human-oriented. Logs and errors
  should carry `__repr__`-quality output ([observability.md](observability.md)).
- Callable objects (`__call__`) and context-manager protocol (`__enter__`/`__exit__`, async variants) are
  ordinary data-model protocols, not special framework features.
- Dunder methods are the runtime contract; typing protocols describe them statically
  ([typing.md](typing.md)). Don't build parallel "interface" abstractions for what the data model already
  expresses.

## Iteration, generators, iterators

- Iteration protocol: `iter(x)` obtains an iterator (`__iter__` → object with `__next__`); `for` consumes
  the protocol, not lists [LANGUAGE]. `StopIteration` ends iteration; a generator raising `StopIteration`
  inside itself is converted to `RuntimeError` (PEP 479) [LANGUAGE].
- Iterators are single-pass and stateful; iterables may be re-iterable. A function that stores an iterator
  instead of the iterable silently starves later consumers — pass the iterable, iterate locally.
- Generators are lazy frames: they defer work until consumed and hold resources (files, locks, sessions)
  open across yields. A generator that owns a resource must be explicitly closed or consumed inside a
  `with`/`finally` (I2) — GC timing is not a release mechanism [LANGUAGE, see GC below].
- `yield from` delegates; `send`/`throw`/`close` drive a generator bidirectionally; `close()` throws
  `GeneratorExit` at the yield point. Generators must not suppress `GeneratorExit`.
- `contextlib.contextmanager` turns a generator into a one-shot context manager; the `yield` is the body
  boundary, and exceptions in the body are raised at the `yield` — handle them or they propagate after
  cleanup.

## Context managers

- `with` calls `__enter__` on entry and `__exit__(exc_type, exc, tb)` on exit; `__exit__` returning true
  suppresses the exception [LANGUAGE]. Suppression is rarely what you want (I13: failure must stay
  visible) — reserve it for documented boundaries that record and translate.
- `contextlib.ExitStack` / `AsyncExitStack` manage dynamic numbers of resources with LIFO cleanup order.
  `async with` is the same model with `__aenter__`/`__aexit__`.
- Context managers are the primary tool for explicit lifecycle (I2): files, sockets, transactions,
  locks, subprocesses, sessions. Cleanup in `finally` is the manual equivalent; `__del__` is neither.

## MRO and cooperative multiple inheritance

- C3 linearization gives every class a deterministic, monotonic method resolution order [LANGUAGE];
  `Class.__mro__` shows it. `super()` follows the MRO, not "the parent class" — it is cooperative, not
  hierarchical.
- Cooperative multiple inheritance works only when every participant uses `super().__init__(*args, **kwargs)`
  consistently. A mixin that swallows arguments breaks the chain silently. Diamond shapes are fine;
  three-level custom hierarchies are not made understandable by a deterministic MRO.
- Prefer composition when the goal is reuse rather than substitutable subtyping
  ([Decision Model §2](../core/decision-model.md)). Mixins earn their place when small, named after their
  one concern, and stateless where practical. For substitutability, use the canonical contract in
  [Composition vs inheritance](architecture.md#composition-vs-inheritance): no stronger preconditions,
  no weaker postconditions, and preservation of relevant invariants and history constraints.

## Import semantics

- Ordinary imports initialize a module and cache it by module name in `sys.modules` [LANGUAGE].
  Subsequent imports normally reuse it. Reloading, retrying a failed import, or loading the same source
  under a different name can execute initialization again. Python 3.15 explicit lazy imports can defer
  initialization; inspect the actual import path when diagnosing effects. Imports are application
  initialization (I3), not textual inclusion. See the [import system](https://docs.python.org/3.14/reference/import.html)
  and version-specific [baseline](modern-python-baseline.md#version-scoped-capabilities).
- `import pkg.mod` binds `pkg` (and binds `pkg.mod` as an attribute); `from pkg import mod` rebinds a
  local name to the module object. `from x import *` follows `__all__` (or non-underscore names) and is
  disallowed in most repo styles for exactly this ambiguity.
- Circular imports are a design symptom: either bidirectional domain dependencies or too much work at
  import time. Diagnose by asking *what executes during import*; fix dependency direction or extract a
  shared contract module ([Decision Model §3](../core/decision-model.md)). A narrowly scoped late import
  inside a function is a pragmatic escape, not a pattern to spread.
- Import-time effects compound: `spawn`-based multiprocessing re-imports modules in each worker; WSGI/ASGI
  servers import the app in every worker. Side effects at import multiply across workers and break
  test isolation.
- The `if __name__ == "__main__":` guard is the entry-point boundary for scripts; modules imported by
  others must not run work.

## Garbage collection: language guarantee vs CPython behavior

- [LANGUAGE] Python does **not** guarantee deterministic collection. When (or whether) an object is
  collected is implementation-defined; `__del__` timing is unspecified. Relying on GC to close files,
  commit transactions, or release locks is a defect (I2).
- [CPYTHON] CPython uses reference counting plus a cyclic garbage collector: most objects die promptly
  when their refcount reaches zero, cycles are collected later by the `gc` module. "It closed on time in
  my test" is refcount coincidence, not a contract — it breaks in cycles, frames, tracebacks, and at
  interpreter shutdown ordering.
- `__del__` hazards [CPYTHON]: resurrection during finalization, runs at unpredictable times, and
  shutdown-time ordering is unreliable. Use context managers; use `weakref.finalize` for
  registration-style cleanup, understanding it still fires at collection time, not at your chosen point.
- Weak references (`weakref.ref`, `WeakValueDictionary`, `WeakKeyDictionary`) express **non-owning**
  relationships: caches, registries, observers that must not extend an object's life. They do not
  replace explicit ownership (I2); some built-in types (list, dict, int, str…) are not weak-referenceable.

## What "Pythonic" means

- "Pythonic" = readable and predictable use of Python's object model (I16) — explicit boundaries, data
  model protocols used as intended, code whose behavior can be predicted from reading it. It does not
  mean clever compression, dense comprehensions doing real work, or metaprogramming that hides control
  flow.
- PEP 20 (The Zen of Python) and PEP 8 are informational [STANDARD] — guidance, not the spec. PEP 20
  itself balances purity ("explicit is better than implicit") against practicality ("practicality beats
  purity"); it is not a checklist. The actual spec is the reference documentation's data model.
- Repository style outranks personal preference ([tooling.md](tooling.md)). When readability and brevity
  conflict, readability wins: it is the maintenance interface of the code.
