from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .database import DatabaseService, DatabaseValidationError
from .schemas import CreateRecordRequest, DeleteRecordRequest, GetRecordsRequest, TableRequest, UpdateRecordRequest

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

mcp = FastMCP(
    "database-mcp",
    host=os.getenv("DATABASE_MCP_HOST", os.getenv("MCP_HOST", "127.0.0.1")),
    port=int(os.getenv("DATABASE_MCP_PORT", "8006")),
)
service = DatabaseService()
Transport = Literal["stdio", "sse", "streamable-http"]


def _get_transport() -> Transport:
    value = os.getenv("MCP_TRANSPORT", "streamable-http")
    if value not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Unsupported MCP_TRANSPORT: {value}")
    return cast(Transport, value)


def _run(operation):
    try:
        return {"ok": True, "result": operation()}
    except (DatabaseValidationError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "error": f"Database operation failed: {exc}"}


@mcp.tool()
def get_schema(request: TableRequest | None = None) -> dict[str, object]:
    """Inspect available tables and columns before constructing a data request."""
    return _run(lambda: service.schema(request.table if request else None))


@mcp.tool()
def get_records(request: GetRecordsRequest) -> dict[str, object]:
    """Read records with validated columns and equality filters."""
    return _run(lambda: service.get_records(request.table, request.columns, request.filters, request.limit))


@mcp.tool()
def create_record(request: CreateRecordRequest) -> dict[str, object]:
    """Create a record in a known table."""
    return _run(lambda: {"id": service.create_record(request.table, request.values)})


@mcp.tool()
def update_records(request: UpdateRecordRequest) -> dict[str, object]:
    """Update records using required equality filters."""
    return _run(lambda: {"updated": service.update_records(request.table, request.values, request.filters)})


@mcp.tool()
def delete_records(request: DeleteRecordRequest) -> dict[str, object]:
    """Delete records using required equality filters."""
    return _run(lambda: {"deleted": service.delete_records(request.table, request.filters)})


def main() -> None:
    mcp.run(transport=_get_transport())


if __name__ == "__main__":
    main()
