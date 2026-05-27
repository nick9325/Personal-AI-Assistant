import logging

from mcp.server.fastmcp import FastMCP

from app.vectorstore import vectorstore


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP(
    name="personal-memory",
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

if __name__ == "__main__":

    logger.info("Starting MCP Server...")

    mcp.run(
        transport="streamable-http",
    )