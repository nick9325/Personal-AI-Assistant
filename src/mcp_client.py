import logging

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import Connection

logger = logging.getLogger(__name__)

async def get_mcp_tools() -> list[BaseTool]:
    """
    Fetch tools from configured MCP servers via HTTP streamable transport.
    Returns an empty list if servers are offline or unreachable.
    """
    mcp_servers: dict[str, Connection] = {
        # "weather": {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp"},
        "email": {"transport": "streamable_http", "url": "http://127.0.0.1:8001/mcp"},
        # "personal-memory": {
        #     "transport": "streamable_http",
        #     "url": "http://127.0.0.1:8003/mcp",
        # },
    }

    tools: list[BaseTool] = []
    for server_name in mcp_servers:
        try:
            client = MultiServerMCPClient(mcp_servers)
            server_tools = await client.get_tools(server_name=server_name)
            tools.extend(server_tools)
            logger.info("Loaded %s MCP tools from %s", len(server_tools), server_name)
        except Exception as exc:  # pragma: no cover - servers may be offline during startup
            logger.warning("Failed to load MCP tools from %s: %s", server_name, exc)

    return tools
