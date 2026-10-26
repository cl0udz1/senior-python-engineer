# Architecture-only inventory import
Design an inventory CSV importer for two maintainers and 20 staff. Daily files have at most 20,000
rows. Use the existing synchronous Python/SQLite direction; command line first and possibly HTTP
later. The import must be replay-safe, reject malformed rows without leaving half an import visible,
and report actionable errors. Give a concise design in response.md (at most 700 words), including
assumptions, transaction/replay boundary, and proposed verification. Do not implement, scaffold,
install dependencies, change source files, or run application code. Reading the supplied files is OK.
