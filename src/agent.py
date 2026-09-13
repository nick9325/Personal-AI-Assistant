import asyncio
import logging
import os
from typing import List

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from src.mcp_client import get_mcp_tools
from src.prompt import SYSTEM_PROMPT
from src.tools import tools as local_tools

load_dotenv()
logger = logging.getLogger(__name__)


def load_tools() -> List[BaseTool]:
    """
    Load local tools and remote MCP tools for graph initialization.
    """
    tools: List[BaseTool] = list(local_tools)

    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            mcp_tools = []
        else:
            mcp_tools = asyncio.run(get_mcp_tools())

        tools.extend(mcp_tools)
        logger.info(f"Loaded {len(tools)} tools ({len(local_tools)} local, {len(mcp_tools)} MCP).")
    except Exception as e:
        logger.warning(f"Failed to fetch MCP tools during graph build: {e}. Defaulting to local tools.")

    return tools


# 1. Load Tools & Initialize LLM Model
all_tools = load_tools()

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.4,
    api_key=api_key if api_key else "DUMMY_KEY_CONFIGURE_IN_ENV",
)

# Bind tools to model if any exist
model_with_tools = model.bind_tools(all_tools) if all_tools else model


# 2. Define Agent Node Function
async def agent_node(state: MessagesState):
    """
    Invokes the LLM with the system prompt prepended to message history.
    """
    messages = state["messages"]
    system_message = SystemMessage(content=SYSTEM_PROMPT)
    response = await model_with_tools.ainvoke([system_message] + list(messages))
    return {"messages": [response]}


# 3. Build Standard LangGraph Workflow
workflow = StateGraph(MessagesState)

# Add Nodes
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode(all_tools))

# Add Edges & Conditional Tool Routing
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", tools_condition)
workflow.add_edge("tools", "agent")

# 4. Compile Graph (Exported as `graph` for langgraph.json)
graph = workflow.compile()

