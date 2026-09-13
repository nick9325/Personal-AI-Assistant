from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .schemas import CreateDirectoryRequest, DeleteRequest, FilePathRequest, FileSearchRequest, MoveRequest
from .tools import FilesystemPolicyError, FilesystemService

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

mcp = FastMCP(
    "filesystem-mcp",
    host=os.getenv("FILESYSTEM_MCP_HOST", os.getenv("MCP_HOST", "127.0.0.1")),
    port=int(os.getenv("FILESYSTEM_MCP_PORT", "8005")),
)
service = FilesystemService()
Transport = Literal["stdio", "sse", "streamable-http"]


def _get_transport() -> Transport:
    value = os.getenv("MCP_TRANSPORT", "streamable-http")
    if value not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Unsupported MCP_TRANSPORT: {value}")
    return cast(Transport, value)


def _run(operation):
    try:
        return operation()
    except FilesystemPolicyError as exc:
        return {"ok": False, "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": f"Filesystem operation failed: {exc}"}


@mcp.tool()
async def search_files(request: FileSearchRequest) -> dict[str, object]:
    """Find files under an allowed workspace root using a glob pattern."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "files": service.search(request.directory, request.pattern, request.recursive, request.max_results)},
    )


@mcp.tool()
async def read_file(request: FilePathRequest) -> dict[str, object]:
    """Read a UTF-8 text file within an allowed workspace root."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "path": request.path, "content": service.read(request.path)},
    )


@mcp.tool()
async def list_directory(request: FilePathRequest) -> dict[str, object]:
    """List entries in an allowed directory."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "entries": service.list_directory(request.path)},
    )


@mcp.tool()
async def create_directory(request: CreateDirectoryRequest) -> dict[str, object]:
    """Create a directory inside an allowed workspace root."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "path": service.create_directory(request.path)},
    )


@mcp.tool()
async def move_file(request: MoveRequest) -> dict[str, object]:
    """Move a file or directory within allowed workspace roots."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "path": service.move(request.source, request.destination)},
    )


@mcp.tool()
async def delete_file(request: DeleteRequest) -> dict[str, object]:
    """Delete a file or directory. Recursive deletion is explicit."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "path": service.delete(request.path, request.recursive)},
    )


@mcp.tool()
async def get_file_metadata(request: FilePathRequest) -> dict[str, object]:
    """Return metadata for an allowed file or directory."""
    return await asyncio.to_thread(
        _run,
        lambda: {"ok": True, "metadata": service.metadata(request.path)},
    )


def main() -> None:
    mcp.run(transport=_get_transport())


if __name__ == "__main__":
    main()
