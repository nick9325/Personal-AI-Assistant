from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_mcp_tools():

    client = MultiServerMCPClient(
        {
            # "weather": {
            #     "url": "http://127.0.0.1:8000/mcp",
            #     "transport": "streamable_http",
            # },

            "memory": {
                "url": "http://127.0.0.1:8000/mcp",
                "transport": "streamable_http",
            }
        }
    )

    tools = await client.get_tools()

    return tools