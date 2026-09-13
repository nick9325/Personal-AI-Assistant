# Database MCP

Controlled SQLite access for the local assistant. The server exposes schema inspection and parameterized CRUD operations; it intentionally does not expose arbitrary SQL execution.

Set `DATABASE_PATH` to choose the SQLite file and run with `MCP_TRANSPORT=streamable-http` on port `8006`.
