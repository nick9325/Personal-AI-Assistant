# Filesystem MCP

A sandboxed filesystem MCP server. Set `FILESYSTEM_ALLOWED_ROOTS` to a list of absolute directories separated by `os.pathsep` (`;` on Windows, `:` on Unix). If omitted, only the current working directory is allowed.

Run with:

```powershell
$env:MCP_TRANSPORT = "streamable-http"
$env:FILESYSTEM_MCP_PORT = "8005"
python -m app.server
```
