"""Normalize optional, application-only usage telemetry from the RAG API."""

from __future__ import annotations

from typing import Any


TOKEN_FIELDS = ("input_tokens", "output_tokens", "total_tokens")


def _token(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def collect_application_usage(api_response: dict[str, Any]) -> dict[str, Any]:
    """Return display-safe telemetry; never make a quality evaluation fail."""
    raw = api_response.get("application_usage")
    if not isinstance(raw, dict):
        return {"status": "missing", "message": "No application usage telemetry received."}

    provider = raw.get("provider")
    deployment = raw.get("deployment")
    model = raw.get("model")
    usage = {
        "provider": provider if isinstance(provider, str) and provider.strip() else None,
        "deployment": deployment if isinstance(deployment, str) and deployment.strip() else None,
        "model": model if isinstance(model, str) and model.strip() else None,
        "generation_calls": _token(raw.get("generation_calls")),
        **{field: _token(raw.get(field)) for field in TOKEN_FIELDS},
    }
    messages = []
    if usage["model"] is None:
        messages.append("Model data not received from application.")
    if any(usage[field] is None for field in TOKEN_FIELDS):
        messages.append("Token data not received from application.")
    if (
        usage["input_tokens"] is not None
        and usage["output_tokens"] is not None
        and usage["total_tokens"] is not None
        and usage["input_tokens"] + usage["output_tokens"] != usage["total_tokens"]
    ):
        messages.append("Invalid application usage telemetry: token total is inconsistent.")

    usage["status"] = "available" if not messages else "partial" if any(
        usage[field] is not None for field in TOKEN_FIELDS
    ) else "invalid"
    usage["message"] = " ".join(messages) if messages else "Application usage telemetry received."
    return usage
