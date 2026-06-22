import logging
from contextlib import asynccontextmanager

import langsmith as ls

from langgraph.graph import (
    StateGraph,
    MessagesState,
    START,
    END,
)

from langgraph.prebuilt import ToolNode

from langchain_core.messages import AIMessage

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

# from src.tools import tools as local_tools
from src.mcp_client import get_mcp_tools
from src.prompt import SYSTEM_PROMPT


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# LOAD MCP TOOLS
# ============================================================

mcp_tools = []
all_tools = []


async def initialize_tools():
    """
    Initialize MCP + Local tools once.
    """

    global mcp_tools
    global all_tools

    if not all_tools:

        logger.info("Loading MCP tools...")

        mcp_tools = await get_mcp_tools()

        all_tools = [
            *mcp_tools,
        ]

        logger.info(f"Loaded {len(all_tools)} tools")


# ============================================================
# AGENT NODE
# ============================================================

async def agent_node(state: MessagesState):

    await initialize_tools()

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
    )

    agent = create_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
    )

    result = await agent.ainvoke(
        {
            "messages": state["messages"]
        }
    )

    return {
        "messages": result["messages"][-1].text
    }


# ============================================================
# TOOL NODE
# ============================================================

async def tool_node(state: MessagesState):

    await initialize_tools()

    tool_executor = ToolNode(all_tools)

    return await tool_executor.ainvoke(state)


# ============================================================
# DECISION FUNCTION
# ============================================================

def decision_node(state: MessagesState):
    """
    Routing logic after agent execution.
    """

    messages = state["messages"]

    if not messages:
        return END

    last_message = messages[-1]

    if isinstance(last_message, AIMessage):

        # Route to tools if tool calls exist
        if getattr(last_message, "tool_calls", None):
            return "Tool Node"

    return END


# ============================================================
# CREATE GRAPH
# ============================================================

state_graph = StateGraph(MessagesState)


# ============================================================
# ADD NODES
# ============================================================

state_graph.add_node(
    "Agent Node",
    agent_node,
)

state_graph.add_node(
    "Tool Node",
    tool_node,
)


# ============================================================
# EDGES
# ============================================================

# START → AGENT
state_graph.add_edge(
    START,
    "Agent Node",
)

# AGENT → TOOL / END
state_graph.add_conditional_edges(
    "Agent Node",
    decision_node,
    {
        "Tool Node": "Tool Node",
        END: END,
    },
)

# TOOL → AGENT
state_graph.add_edge(
    "Tool Node",
    "Agent Node",
)


# ============================================================
# COMPILE GRAPH
# ============================================================

graph = state_graph.compile(
    name="Gemini-Agent"
)


# ============================================================
# STANDARD TEMPLATE
# ============================================================

@asynccontextmanager
async def compile_agent():

    await initialize_tools()

    with ls.tracing_context():
        yield graph