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

from src.tools import tools
from src.prompt import SYSTEM_PROMPT

# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)



# ============================================================
# AGENT NODE
# ============================================================

async def agent_node(state: MessagesState):

    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
    )

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )

    result = await agent.ainvoke(
        {
            "messages": state["messages"]
        }
    )

    return {
        "messages": result["messages"][-1]
    }


# ============================================================
# TOOL NODE
# ============================================================

tool_node = ToolNode(tools)


# ============================================================
# MCP NODE
# ============================================================

async def mcp_node(state: MessagesState):

    print("MCP NODE EXECUTED")

    return state


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

        # Tool routing
        if getattr(last_message, "tool_calls", None):
            return "Tool Node"

        # MCP routing
        if "USE_MCP" in str(last_message.content):
            return "MCP Node"

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

state_graph.add_node(
    "MCP Node",
    mcp_node,
)


# ============================================================
# EDGES
# ============================================================

# Start → Agent
state_graph.add_edge(
    START,
    "Agent Node",
)

# Agent → Decision Routing
state_graph.add_conditional_edges(
    "Agent Node",
    decision_node,
    {
        "Tool Node": "Tool Node",
        "MCP Node": "MCP Node",
        END: END,
    },
)

# Tool → Agent
state_graph.add_edge(
    "Tool Node",
    "Agent Node",
)

# MCP → Agent
state_graph.add_edge(
    "MCP Node",
    "Agent Node",
)


# ============================================================
# COMPILE
# ============================================================

graph = state_graph.compile(
    name="Gemini-Agent"
)


# ============================================================
# STANDARD TEMPLATE
# ============================================================

@asynccontextmanager
async def compile_agent():

    with ls.tracing_context():

        yield graph                                                                                  