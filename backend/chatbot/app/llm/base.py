"""LLM Instance Factory with multi-key fallback support (Ollama & Google Gemini)."""

import logging
from typing import Any, List, Union
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from chatbot.config.settings import settings

logger = logging.getLogger("chatbot.llm")

_llm: Union[Any, Runnable, None] = None


class KeyFallbackCallbackHandler(BaseCallbackHandler):
    """Logs warnings when an LLM API key fails so that fallbacks can be observed."""

    def __init__(self, key_label: str):
        self.key_label = key_label

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        logger.warning(
            f"[LLM Fallback] API key '{self.key_label}' failed: {error}. "
            "Falling back to subsequent key..."
        )


def _create_ollama_instance(api_key: str, key_label: str) -> ChatOllama:
    """Instantiates a ChatOllama model with the given API key and error logging callback."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    callbacks = [KeyFallbackCallbackHandler(key_label)] if api_key else None
    return ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        num_ctx=settings.OLLAMA_NUM_CTX,
        client_kwargs={"headers": headers} if headers else None,
        callbacks=callbacks,
    )


def _create_gemini_instance(api_key: str, key_label: str) -> Any:
    """Instantiates a ChatGoogleGenerativeAI model with the given API key."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    callbacks = [KeyFallbackCallbackHandler(key_label)] if api_key else None
    model_name = settings.LLM_MODEL
    # Auto-adjust model name if set to an Ollama default
    if any(m in model_name.lower() for m in ["gemma", "llama", "mistral", "qwen"]):
        model_name = "gemini-2.5-flash"
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key or None,
        temperature=0,
        callbacks=callbacks,
    )


def get_llm() -> Union[ChatOllama, Any, Runnable]:
    """Returns an LLM model instance with automatic fallback across configured API keys.

    Supports both 'gemini' (Google Generative AI) and 'ollama' providers.
    If key ONE fails or credits run out, requests seamlessly fall back to key SECOND,
    and then key THIRD.
    """
    global _llm
    if _llm is not None:
        return _llm

    provider = (settings.LLM_PROVIDER or "ollama").strip().lower()

    if provider in ("gemini", "google"):
        keys = settings.google_api_keys
        if not keys:
            _llm = _create_gemini_instance("", "DEFAULT")
        elif len(keys) == 1:
            _llm = _create_gemini_instance(keys[0], "KEY_ONE")
        else:
            labels = ["KEY_ONE", "KEY_TWO", "KEY_THREE"]
            instances: List[Any] = [
                _create_gemini_instance(key, labels[i] if i < len(labels) else f"KEY_{i+1}")
                for i, key in enumerate(keys)
            ]
            primary = instances[0]
            fallbacks = instances[1:]
            _llm = primary.with_fallbacks(fallbacks)
            configured_labels = [labels[i] if i < len(labels) else f"KEY_{i+1}" for i in range(len(instances))]
            logger.info(
                f"Initialized ChatGoogleGenerativeAI with {len(instances)} keys fallback chain: {configured_labels}"
            )
        return _llm

    # Default to Ollama provider
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
