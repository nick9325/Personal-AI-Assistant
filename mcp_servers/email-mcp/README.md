# Email MCP Server

A standalone MCP server exposing Gmail SMTP email sending as tools, so it
can live outside your LangGraph agent's local `tools.py` and be reused by
any MCP-compatible client.

Built on `mcp` SDK **v1.28.0** (the current stable v1.x line as of
June 2026; v2 is in alpha and not yet recommended for production).

## Why a separate server

- Keeps SMTP credentials and email logic out of the agent's core graph code.
- Reusable across any MCP client (Claude Desktop, Claude Code, your
  LangGraph agent, future agents) without copy-pasting `send_email`.
- Mirrors the architecture of your Personal Memory MCP server: one
  focused MCP server per capability, mounted on its own port.

## Tools

| Tool | Purpose |
|---|---|
| `send_email` | Plain-text email |
| `send_email_html` | HTML-formatted email (reports, summaries) |
| `send_email_with_attachments` | Email with one or more file attachments |

All three return a **string** on both success and failure — they never
raise. This matches the debugging lesson from your memory project: MCP
tool functions should return error strings rather than raise exceptions,
or the failure surfaces to the LLM as an opaque "tool execution failed"
with no actionable detail.

## Resource

`email://config` — returns a non-secret summary of the active SMTP
config (host, port, TLS, limits) so an agent or you can sanity-check
setup without exposing the app password.

## Setup

```bash
cd email-mcp-server
pip install -e .
cp .env.example .env
# edit .env with your Gmail address + App Password
```

Generate a Gmail App Password (not your normal password) at
https://myaccount.google.com/apppasswords — requires 2-Step Verification
to be enabled on the Google account.

## Running

**stdio** (default — for Claude Desktop, Claude Code, or any client that
spawns the server as a subprocess):

```bash
python -m src.server
```

**streamable-http** (using the sequential service ports):

```bash
MCP_TRANSPORT=streamable-http EMAIL_MCP_PORT=8002 python -m src.server
```

The server validates SMTP login **at startup** (in the lifespan handler),
so a bad app password or wrong host fails immediately and loudly in the
logs — not silently on the first real send attempt by a user.

## Wiring into your LangGraph agent

Your current `mcp_client.py` already does `get_mcp_tools()` to pull in
external MCP tools. Add this server's URL (if running streamable-http)
or stdio command alongside whatever you already connect to — for
example, with `langchain-mcp-adapters`:

```python
from langchain_mcp_adapters.client import MultiServerMCPClient

client = MultiServerMCPClient(
    {
        "personal_memory": {
            "transport": "streamable_http",
            "url": "http://localhost:8003/mcp",
        },
        "email": {
            "transport": "streamable_http",
            "url": "http://localhost:8002/mcp",
        },
    }
)
tools = await client.get_tools()
```

Then drop the `send_email` function and `tools = [send_email]` list out
of your current `src/tools.py` entirely — `local_tools` becomes empty
(or holds only genuinely-local, non-network tools), and email arrives
through `mcp_tools` instead.

## Safety limits (configurable via `.env`)

- `MAX_RECIPIENTS_PER_CALL` (default 20) — caps To+Cc+Bcc combined per send.
- `MAX_ATTACHMENT_MB` (default 20) — caps each attachment's size.

These exist so a misbehaving or adversarial prompt can't turn this into
a mass-mailer or get an oversized attachment silently rejected by Gmail.

## Testing without sending real email

The validation logic (`src/email_client.py::_build_message`) is pure
and network-free — bad addresses, empty subjects, missing attachments,
and recipient-limit violations are all caught before any SMTP
connection opens. You can exercise that path directly to unit-test
without touching the network or your real inbox.
