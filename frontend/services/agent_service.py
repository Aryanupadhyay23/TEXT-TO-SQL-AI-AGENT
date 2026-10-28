import sys
import asyncio
from typing import AsyncGenerator, Tuple, Dict, Any

# Ensure WindowsSelectorEventLoopPolicy is active for Windows socket SSL duplexing
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass


async def stream_agent_workflow(user_query: str, thread_id: str) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
    """Executes the full LangGraph agent workflow asynchronously, yielding each node event."""
    import importlib

    # Ensure fresh execution and orchestrator instances in persistent Streamlit processes
    for mod in ["chatbot.app.sql.executor", "chatbot.app.agent.orchestrator"]:
        if mod in sys.modules:
            try:
                importlib.reload(sys.modules[mod])
            except Exception:
                pass

    from chatbot.app.agent.orchestrator import create_agent_graph, get_checkpointer
    from chatbot.app.models import AgentState

    # Compile graph fresh on the active event loop
    fresh_graph = create_agent_graph(checkpointer=get_checkpointer())

    state = AgentState(
        user_input=user_query,
        history=[],
    )
    config = {"configurable": {"thread_id": thread_id}}

    async for event in fresh_graph.astream(state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if isinstance(node_output, dict):
                yield node_name, node_output
