import asyncio
import logging
from typing import Any

from langchain_core.tools import BaseTool

from src.config import MCPServerConfig, get_mcp_servers

logger = logging.getLogger(__name__)


def _load_mcp_client_class():
    from langchain_mcp_adapters.client import MultiServerMCPClient

    return MultiServerMCPClient


async def get_mcp_tools(servers: tuple[MCPServerConfig, ...] | None = None) -> list[BaseTool]:
    """
    Fetch tools from configured MCP servers via HTTP streamable transport.
    Returns an empty list if servers are offline or unreachable.
    """
    configured_servers = servers or get_mcp_servers()
    enabled_servers = tuple(server for server in configured_servers if server.enabled)
    mcp_servers: dict[str, Any] = {
        server.name: server.connection for server in enabled_servers
    }

    if not mcp_servers:
        return []

    client_class = await asyncio.to_thread(_load_mcp_client_class)
    tools: list[BaseTool] = []
    for server_name, connection in mcp_servers.items():
        try:
            client = client_class({server_name: connection})
            server_tools = await client.get_tools(server_name=server_name)
            tools.extend(server_tools)
            logger.info("Loaded %s MCP tools from %s", len(server_tools), server_name)
        except Exception as exc:  # pragma: no cover - servers may be offline
            logger.warning("Failed to load MCP tools from %s: %s", server_name, exc)

    return tools
