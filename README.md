# Personal AI Assistant

A local agentic assistant built with LangGraph and modular MCP servers. The graph can discover and orchestrate weather, email, personal memory, filesystem, and controlled SQLite capabilities while preserving conversation state by thread.

## Architecture

- `src/agent.py`: LangGraph workflow, tool routing, human approval interrupts, and platform-managed checkpointing.
- `src/mcp_client.py`: one configurable MCP client for all capability servers.
- `mcp_servers/email-mcp`: SMTP email with Pydantic-backed settings and attachment validation.
- `mcp_servers/filesystem-mcp`: sandboxed search, read, list, create, move, delete, and metadata tools.
- `mcp_servers/database-mcp`: schema-aware, parameterized SQLite CRUD without arbitrary SQL execution.
- `mcp_servers/personal-memory-mcp`: document ingestion and semantic retrieval.
- `mcp_servers/weather-mcp`: current conditions and forecasts.

## Setup

1. Use Python 3.14 and install dependencies:

   ```powershell
   uv sync
   ```

2. Copy `.env.example` to `.env` and set `GOOGLE_API_KEY` or `GEMINI_API_KEY`. Keep credentials out of source control.
3. Configure `FILESYSTEM_ALLOWED_ROOTS` with only directories the assistant may access. On Windows, separate multiple roots with `;`.
4. Configure email credentials only for the email MCP process. Gmail requires an App Password when using SMTP.

## Start MCP servers

Run each server from its directory, using the project environment. The sequential service ports are weather `8001`, email `8002`, personal-memory MCP `8003`, personal-memory API `8004`, filesystem `8005`, and database `8006`.

```powershell
$env:MCP_TRANSPORT = "streamable-http"
$env:FILESYSTEM_ALLOWED_ROOTS = "$PWD"
Push-Location mcp_servers/filesystem-mcp; python -m app.server; Pop-Location
Push-Location mcp_servers/database-mcp; python -m app.server; Pop-Location
Push-Location mcp_servers/email-mcp; python -m app.server; Pop-Location
python mcp_servers/weather-mcp/weather.py
Push-Location mcp_servers/personal-memory-mcp; python -m app.mcp_server; Pop-Location
```

The LangGraph graph can start even if optional servers are offline; those tools become available the next time the graph is initialized after the servers are running.

## Conversations and approvals

Invoke the graph with a stable LangGraph `thread_id` in the configurable metadata. LangGraph API manages checkpoint persistence automatically. The assistant executes explicitly requested operations and reports tool failures without claiming success.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q src mcp_servers
```

The database MCP intentionally exposes schema-aware CRUD instead of unrestricted SQL. All filesystem paths are resolved under configured roots, protected directory names are blocked, and text reads have a size limit.
