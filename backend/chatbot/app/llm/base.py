"""Ollama LLM Instance Factory with multi-key fallback support."""

import logging
from typing import Any, List, Union
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from chatbot.config.settings import settings

logger = logging.getLogger("chatbot.llm")

_llm: Union[ChatOllama, Runnable, None] = None


class OllamaKeyCallbackHandler(BaseCallbackHandler):
    """Logs warnings when an Ollama API key fails so that fallbacks can be observed."""

    def __init__(self, key_label: str):
        self.key_label = key_label

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        logger.warning(
            f"[Ollama Fallback] API key '{self.key_label}' failed: {error}. "
            "Falling back to subsequent key..."
        )


def _create_ollama_instance(api_key: str, key_label: str) -> ChatOllama:
    """Instantiates a ChatOllama model with the given API key and error logging callback."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    callbacks = [OllamaKeyCallbackHandler(key_label)] if api_key else None
    return ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        num_ctx=settings.OLLAMA_NUM_CTX,
        client_kwargs={"headers": headers} if headers else None,
        callbacks=callbacks,
    )


def get_llm() -> Union[ChatOllama, Runnable]:
    """Returns a ChatOllama model instance with automatic fallback across configured API keys.

    If key ONE fails or credits run out, requests seamlessly fall back to key SECOND,
    and then key THIRD.
    """
    global _llm
    if _llm is None:
        keys = settings.ollama_api_keys
        if not keys:
            _llm = _create_ollama_instance(settings.OLLAMA_API_KEY, "DEFAULT")
        elif len(keys) == 1:
            _llm = _create_ollama_instance(keys[0], "KEY_ONE")
        else:
            labels = ["KEY_ONE", "KEY_SECOND", "KEY_THIRD"]
            instances: List[ChatOllama] = [
                _create_ollama_instance(key, labels[i] if i < len(labels) else f"KEY_{i+1}")
                for i, key in enumerate(keys)
            ]
            primary = instances[0]
            fallbacks = instances[1:]
            _llm = primary.with_fallbacks(fallbacks)
            configured_labels = [labels[i] if i < len(labels) else f"KEY_{i+1}" for i in range(len(instances))]
            logger.info(
                f"Initialized ChatOllama with {len(instances)} keys fallback chain: {configured_labels}"
            )
    return _llm

