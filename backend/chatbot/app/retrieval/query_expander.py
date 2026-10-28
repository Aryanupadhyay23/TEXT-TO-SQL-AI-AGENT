from typing import List, Dict, Any
from chatbot.app.llm.base import get_llm
from chatbot.app.models import AgentState, QueryVariations
from chatbot.app.prompts.query_expansion import QUERY_EXPANSION_PROMPT


class QueryExpander:
    """Generates 3 pruned, keyword-dense search variations of user query for multi-index retrieval."""

    def __init__(self):
        self._chain = None

    def _get_chain(self):
        if self._chain is None:
            model = get_llm().with_structured_output(QueryVariations)
            self._chain = QUERY_EXPANSION_PROMPT | model
        return self._chain

    async def expand(self, query: str) -> List[str]:
        """
        Generates exactly 3 concise search variations without conversational filler words.
        Bypasses LLM for very short queries (<= 3 words).
        """
        cleaned = query.strip()
        words = cleaned.split()

        # Fast gate: short queries (<= 3 words) don't need expansion
        if len(words) <= 3:
            return [cleaned]

        try:
            chain = self._get_chain()
            result: QueryVariations = await chain.ainvoke({"user_query": cleaned})
            variations = [v.strip() for v in result.variations if v and v.strip()]
            return variations[:3] if variations else [cleaned]
        except Exception:
            # Fallback: simple stop-word stripped phrase
            filler_words = {"what", "are", "the", "is", "can", "you", "show", "me", "how", "many", "please", "list", "tell", "about", "all"}
            pruned_words = [w for w in words if w.lower() not in filler_words]
            fallback_query = " ".join(pruned_words) if pruned_words else cleaned
            return [fallback_query, cleaned]


# Singleton instance
query_expander = QueryExpander()


async def query_expansion_node(state: AgentState) -> Dict[str, Any]:
    """LangGraph node: Generates 3 search variations and pools with original query."""
    raw_query = state.processed_query or state.user_input
    variations = await query_expander.expand(raw_query)

    # Build unique search queries list: original query + generated variations
    seen = set()
    search_queries = []
    for q in [raw_query] + variations:
        q_clean = q.strip()
        if q_clean and q_clean.lower() not in seen:
            seen.add(q_clean.lower())
            search_queries.append(q_clean)

    return {
        "query_variations": variations,
        "search_queries": search_queries,
    }
