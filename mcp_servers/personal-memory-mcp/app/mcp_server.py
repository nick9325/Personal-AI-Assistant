import logging
import os
from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from app.vectorstore import vectorstore

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# ============================================================
# MCP SERVER
# ============================================================

Transport = Literal["stdio", "sse", "streamable-http"]


def _get_transport() -> Transport:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Unsupported MCP_TRANSPORT: {transport}")
    return cast(Transport, transport)


MCP_TRANSPORT: Transport = _get_transport()
MCP_HOST = os.getenv("PERSONAL_MEMORY_MCP_HOST", os.getenv("MCP_HOST", "127.0.0.1"))
MCP_PORT = int(os.getenv("PERSONAL_MEMORY_MCP_PORT", "8003"))

mcp = FastMCP(
    "personal-memory",
    host=MCP_HOST,
    port=MCP_PORT,
)


# ============================================================
# MCP TOOL
# ============================================================

@mcp.tool()
async def personal_query(query: str) -> str:
    """
    Query personal documents.
    """

    try:

        if not query or not query.strip():
            return "Query cannot be empty."

        documents = vectorstore.similarity_search(
            query=query,
            k=5,
        )

        if not documents:
            return "No relevant information found."

        context = "\n\n".join(
            doc.page_content
            for doc in documents
        )

        return context

    except Exception as e:

        logger.exception(e)

        return f"Error: {str(e)}"


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    logger.info("Starting personal-memory MCP server on %s:%s", MCP_HOST, MCP_PORT)
    mcp.run(transport=MCP_TRANSPORT)


if __name__ == "__main__":
    main()