from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from config.settings import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    LLM_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_PREDICT,
    OLLAMA_REQUEST_TIMEOUT,
    OLLAMA_TEMPERATURE,
)


def _non_negative_int(value):
    """Return a provider token counter only when it is safe to expose."""
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None

def _response_text(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "".join(text_parts)

    return str(content)

def get_llm_response(prompt: str) -> dict:
    """Generate text and return provider usage without returning the prompt.

    Usage is intentionally limited to aggregate counters.  It is application
    telemetry, not an evaluator trace, and never contains secrets or prompt
    contents.
    """
    if LLM_PROVIDER == "ollama":
        llm = ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=OLLAMA_TEMPERATURE,
            # Azure-cost answers should be concise. This also prevents an
            # accidental long generation from monopolising the local model.
            num_predict=OLLAMA_NUM_PREDICT,
            # Without a client timeout, a stalled local generation can hold
            # the API worker (and an evaluation run) indefinitely.
            client_kwargs={"timeout": OLLAMA_REQUEST_TIMEOUT},
        )
    elif LLM_PROVIDER == "gemini":
        if not GOOGLE_API_KEY:
            raise RuntimeError("GOOGLE_API_KEY is required when LLM_PROVIDER=gemini.")
        llm = ChatGoogleGenerativeAI(google_api_key=GOOGLE_API_KEY, model=GEMINI_MODEL)
    else:
        raise RuntimeError(
            f"Unsupported LLM_PROVIDER '{LLM_PROVIDER}'. Use 'ollama' or 'gemini'."
        )

    response = llm.invoke([HumanMessage(content=prompt)])
    response_metadata = getattr(response, "response_metadata", {}) or {}
    usage_metadata = getattr(response, "usage_metadata", {}) or {}

    if LLM_PROVIDER == "ollama":
        input_tokens = _non_negative_int(response_metadata.get("prompt_eval_count"))
        output_tokens = _non_negative_int(response_metadata.get("eval_count"))
        provider = "ollama"
        model = OLLAMA_MODEL
        deployment = "local"
    else:
        # LangChain normalizes Gemini usage into usage_metadata.  Keep this
        # tolerant because provider integrations have changed field names.
        input_tokens = _non_negative_int(
            usage_metadata.get("input_tokens", usage_metadata.get("prompt_token_count"))
        )
        output_tokens = _non_negative_int(
            usage_metadata.get("output_tokens", usage_metadata.get("candidates_token_count"))
        )
        provider = "gemini"
        model = GEMINI_MODEL
        deployment = "api"

    total_tokens = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else _non_negative_int(usage_metadata.get("total_tokens"))
    )
    return {
        "text": _response_text(response.content),
        "usage": {
            "provider": provider,
            "deployment": deployment,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        },
    }
