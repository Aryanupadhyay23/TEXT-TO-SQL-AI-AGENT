import asyncio
import sys
from typing import Any, AsyncGenerator, Dict, Tuple

# Ensure WindowsSelectorEventLoopPolicy is active for Windows socket SSL duplexing
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

# Compiled once per Streamlit process so the checkpointer retains conversation memory
_graph = None


def _get_graph():
    global _graph
    if _graph is None:
        from chatbot.app.agent.orchestrator import create_agent_graph, get_checkpointer
        _graph = create_agent_graph(checkpointer=get_checkpointer())
    return _graph


async def stream_agent_workflow(user_query: str, thread_id: str) -> AsyncGenerator[Tuple[str, Dict[str, Any]], None]:
    """Executes the full LangGraph agent workflow asynchronously, yielding each node event."""
    graph = _get_graph()

    # Partial input merges with the thread checkpoint, preserving prior conversation turns
    state = {"user_input": user_query}
    config = {"configurable": {"thread_id": thread_id}}

    async for event in graph.astream(state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if isinstance(node_output, dict):
                yield node_name, node_output
