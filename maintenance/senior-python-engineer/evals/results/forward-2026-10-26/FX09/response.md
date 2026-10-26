# Inventory CSV importer design

## Constraints and assumptions

`project.txt` requires Python 3.11+ and standard library only; `solution.py` contains only a seed declaration. This proposal preserves that direction.

Assume one authoritative inventory source and a SQLite database on the application host, with staff running the CLI there. CSV is UTF-8, with exactly `sku,quantity` headers. SKUs are nonempty, case-sensitive identifiers; quantities are decimal integers from 0 through 2,147,483,647. Counts replace existing values, new SKUs are created, and omitted SKUs remain unchanged. This is a partial stock update, not a delta or complete replacement.

Each delivery has an immutable, increasing integer batch revision supplied by the source/operator. Retries reuse it; corrections receive a newer revision. Filenames do not establish identity. These business assumptions require agreement before implementation.

## Structure and ownership

Use `argparse`, `csv`, `hashlib`, and `sqlite3`. A thin CLI calls one synchronous `import_inventory` use-case function, supported by parsing/validation and SQL helpers. The use case owns its input snapshot, validated records, connection, and transaction, and explicitly closes resources. Helpers never commit. Return a structured result or typed application error; the CLI owns formatting and exit codes.

For two maintainers and at most 20,000 rows, this keeps ownership understandable. A future HTTP adapter calls the same function and maps its results; business rules stay shared. Direct SQL fits the small schema and standard-library constraint. Additional frameworks, repositories, workers, and concurrency machinery have no identified requirement.

## Validation and actionable errors

Read the input once into a bounded byte snapshot, then hash and parse those same bytes. Propose a 20 MiB file limit, 128-character SKUs, bounded CSV fields, and the stated 20,000-row ceiling. Validate the complete file before opening a write transaction: encoding, CSV syntax, exact unique headers, field counts, required values, integer range, and duplicate SKUs. Reject duplicate SKUs rather than choosing a winner. Reject empty imports.

Any invalid row rejects the whole import. Report filename, CSV record number and physical line where available, column, error code, bounded offending value, and correction guidance. Aggregate independent row errors, displaying the first 100 plus total count; stop when structural corruption prevents reliable parsing. Example: `record 42, quantity: expected a nonnegative integer; received '2.5'`. State that nothing was applied.

## Transaction and replay boundary

Maintain `inventory(sku PRIMARY KEY, quantity CHECK (...))` and `imports(revision PRIMARY KEY, sha256, schema_version, row_count, committed_at)`, with required columns explicitly `NOT NULL`. Keep replay records for the lifetime of the inventory.

After validation, use an owned connection with explicit transaction control compatible with Python 3.11 (`isolation_level=None`) and `BEGIN IMMEDIATE`:

1. Look up the revision under the write lock. Matching digest and schema version returns the recorded result without modifying inventory; differing content is a conflict.
2. For an unseen revision, reject one older than the latest committed revision. This prevents delayed snapshots overwriting newer counts.
3. Apply parameterized upserts and insert the successful import record in the same transaction. Commit once; acknowledge success only afterward.

No row-level commits or skipped failures. Errors or interruption before commit roll back the entire transaction; readers cannot see an uncommitted partial import. Multi-query readers use a read transaction for a consistent snapshot. A bounded busy timeout yields an actionable “database busy; retry this revision” error. Concurrent identical imports serialize and deduplicate. If commit outcome is uncertain or the acknowledgement is lost, retry the same revision and bytes to reconcile through the ledger; do not claim failure means unapplied.

## Proposed verification

Using standard-library `unittest` and temporary SQLite databases, test malformed headers/rows, duplicates, encoding, limits, and diagnostic locations. Verify full rollback with a failure after several writes; exact replay after later imports; changed-content conflicts; stale revisions; two competing connections; and process termination before/after commit. Confirm inventory and ledger agree after reopening. Measure a representative 20,000-row import and lock duration before changing the design. Exercise CLI exit codes and summaries.

These checks are proposed only. No application code or tests were executed, and no source files were changed.
