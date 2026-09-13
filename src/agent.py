from __future__ import annotations

import asyncio
import logging
from asyncio import Lock

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.mcp_client import get_mcp_tools
from src.config import get_llm_settings
from src.prompt import SYSTEM_PROMPT
from src.tools import tools as local_tools

logger = logging.getLogger(__name__)

all_tools: list[BaseTool] = list(local_tools)
tool_executor = ToolNode(all_tools)
_tools_lock = Lock()
_tools_loaded = False
api_key, llm_model = get_llm_settings()
model = None


def _create_model():
    """Import and construct the provider client outside the ASGI event loop."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=llm_model,
        temperature=0.4,
        api_key=api_key if api_key else "DUMMY_KEY_CONFIGURE_IN_ENV",
    )


async def ensure_tools_loaded() -> None:
    """Discover MCP tools on demand so graph imports stay fast and reliable."""
    global _tools_loaded, tool_executor
    if _tools_loaded:
        return
    async with _tools_lock:
        if _tools_loaded:
            return
        try:
            mcp_tools = await get_mcp_tools()
            all_tools.extend(mcp_tools)
            tool_executor = ToolNode(all_tools)
            logger.info(
                "Loaded %s tools (%s local, %s MCP).",
                len(all_tools),
                len(local_tools),
                len(mcp_tools),
            )
        except Exception as exc:  # pragma: no cover - optional servers may be offline
            logger.warning("Failed to fetch MCP tools: %s", exc)
        finally:
            _tools_loaded = True


async def agent_node(state: MessagesState) -> dict[str, list[AIMessage]]:
    global model
    await ensure_tools_loaded()
    if model is None:
        model = await asyncio.to_thread(_create_model)
    model_with_tools = model.bind_tools(all_tools) if all_tools else model
    response = await model_with_tools.ainvoke(
        [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    )
    return {"messages": [response]}


def route_after_agent(state: MessagesState) -> str:
    return tools_condition({"messages": state["messages"]})


async def tools_node(state: MessagesState) -> dict[str, list[ToolMessage]]:
    """Retry an exceptional MCP failure once, then expose a concrete error to the model."""
    await ensure_tools_loaded()
    for attempt in range(2):
        try:
            return await tool_executor.ainvoke(state)
        except Exception as exc:  # pragma: no cover - depends on remote server failures
            if attempt == 1:
                last = state["messages"][-1]
                calls = last.tool_calls if isinstance(last, AIMessage) else []
                return {
                    "messages": [
                        ToolMessage(
                            content=f"Tool execution failed after one retry: {exc}",
                            tool_call_id=call["id"],
                        )
                        for call in calls
                    ]
                }
    raise RuntimeError("Tool execution retry loop ended unexpectedly")


workflow = StateGraph(MessagesState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", tools_node)
workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    route_after_agent,
    {"tools": "tools", END: END},
)
workflow.add_edge("tools", "agent")


graph = workflow.compile()
