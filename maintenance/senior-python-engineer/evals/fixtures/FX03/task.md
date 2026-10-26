# Whole-unit retry
Repair `run_transaction(connect, work, max_attempts=3)`. `connect()` returns a NEW sqlite3 connection
with default transaction behavior. `work(connection)` is the complete database-only unit and may
raise RetryableConflict. On success commit once, return its result, and close the connection.
On RetryableConflict, roll back, close, and rerun the ENTIRE work with a fresh connection, within the
attempt bound. Propagate other exceptions without retry. Propagate the last conflict on exhaustion.
Reject max_attempts < 1 without connecting. No remote effects occur inside work. This is a portable
transaction-control exercise; RetryableConflict is a fixture exception, not a SQLite or PostgreSQL
SQLSTATE claim. Keep the API. Explain actual verification in response.md.
