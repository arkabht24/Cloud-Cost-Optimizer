"""Framework-owned, versioned application token-cost calculation.

Prices intentionally live in ``evals/pricing/model_pricing.json`` rather than
in the RAG application or a fragile runtime scraper. Each run saves the exact
catalog entry used in its pricing snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path


PRICING_CATALOG_PATH = Path(__file__).with_name("pricing") / "model_pricing.json"


def _local_cost() -> dict:
    return {
        "currency": "USD",
        "provider_inference_cost": 0.0,
        "status": "local_model_no_provider_charge",
        "message": "Provider token pricing is not applicable to a local model. Local infrastructure cost is not calculated.",
        "pricing_source": None,
        "pricing_verified_at": None,
    }


def _unavailable(message: str) -> dict:
    return {
        "currency": "USD",
        "provider_inference_cost": None,
        "status": "pricing_unavailable",
        "message": message,
        "pricing_source": None,
        "pricing_verified_at": None,
    }


def _catalog_entry(provider: str, model: str) -> dict | None:
    try:
        catalog = json.loads(PRICING_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    entry = catalog.get(provider, {}).get(model)
    return entry if isinstance(entry, dict) else None


def calculate_cost(usage: dict) -> dict:
    """Calculate application provider inference cost from the approved catalog."""
    if usage.get("status") == "missing":
        return _unavailable("No application usage telemetry received.")
    if usage.get("status") != "available":
        return _unavailable(usage.get("message", "Invalid application usage telemetry."))

    provider = usage.get("provider")
    deployment = usage.get("deployment")
    model = usage.get("model")
    if not model:
        return _unavailable("Model data not received from application.")
    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return _unavailable("Token data not received from application.")
    if provider == "ollama" or deployment == "local":
        return _local_cost()
    if not isinstance(provider, str):
        return _unavailable("Provider data not received from application.")

    entry = _catalog_entry(provider, model)
    if entry is None:
        return _unavailable(f"No approved pricing catalog entry for {provider}/{model}.")
    try:
        input_rate = float(entry["input_per_million_tokens"])
        output_rate = float(entry["output_per_million_tokens"])
    except (KeyError, TypeError, ValueError):
        return _unavailable(f"Invalid pricing catalog entry for {provider}/{model}.")

    input_cost = input_tokens * input_rate / 1_000_000
    output_cost = output_tokens * output_rate / 1_000_000
    return {
        "currency": entry.get("currency", "USD"),
        "provider_inference_cost": round(input_cost + output_cost, 8),
        "input_cost": round(input_cost, 8),
        "output_cost": round(output_cost, 8),
        "status": "available",
        "message": "Calculated using the approved evaluation pricing catalog.",
        "pricing_source": entry.get("source_url"),
        "pricing_verified_at": entry.get("verified_at"),
        "pricing_tier": entry.get("tier"),
        "input_per_million_tokens": input_rate,
        "output_per_million_tokens": output_rate,
    }


def write_pricing_snapshot(run_dir: Path, records: list[dict]) -> None:
    """Persist unique applied cost metadata for reproducible historical reports."""
    snapshots = []
    seen = set()
    for record in records:
        cost = record.get("application_cost", {})
        key = (
            cost.get("pricing_source"),
            cost.get("pricing_verified_at"),
            cost.get("pricing_tier"),
            cost.get("status"),
        )
        if key not in seen:
            seen.add(key)
            snapshots.append(cost)
    (run_dir / "pricing_snapshot.json").write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
