"""Grounded, conversational FinOps answers for the dashboard assistant.

This deliberately differs from ``rag.service``: optimization signals need a
strict decision transport format, whereas a user-facing assistant should
explain observed cost facts and relevant practices in plain language.
"""

from __future__ import annotations

import json
from typing import Any

from azure.dashboard_data import build_dashboard_data
from rag.llm_client import get_llm_response
from rag.query_policy import assess_query_policy
from rag.retriever import retrieve_best_practice_contexts
from rag.service import analyze_resources


def _resource_named_in_text(resources: list[dict[str, Any]], text: str) -> dict[str, Any] | None:
    """Return the longest explicit inventory-name mention in free text."""
    lowered = text.lower()
    matches = [item for item in resources if item["name"].lower() in lowered]
    return max(matches, key=lambda item: len(item["name"])) if matches else None


def _find_resource(
    resources: list[dict[str, Any]],
    requested_name: str | None,
    question: str,
    history: list[dict[str, str]] | None,
) -> dict[str, Any] | None:
    # A name in the newest user turn always wins over stale UI context.
    explicit = _resource_named_in_text(resources, question)
    if explicit:
        return explicit
    if requested_name:
        match = next((item for item in resources if item["name"].lower() == requested_name.lower()), None)
        if match:
            return match
    # Follow-up phrasing such as "what about it?" resolves to the most recent
    # resource explicitly named by the user in the bounded conversation.
    for turn in reversed(history or []):
        if turn.get("role") == "user":
            match = _resource_named_in_text(resources, turn.get("text", ""))
            if match:
                return match
    return None


def _facts_for_prompt(resource: dict[str, Any] | None) -> tuple[dict[str, Any], str]:
    if resource is None:
        return {}, "No individual dashboard resource was selected or matched."
    cost = resource["cost"].get("last_30_days")
    currency = resource["cost"].get("currency", "USD")
    weekly_run_rate = round(cost / 30 * 7, 2) if isinstance(cost, (int, float)) else None
    facts = {
        "resource_name": resource["name"],
        "azure_resource_type": resource["type"],
        "region": resource.get("region"),
        "sku": resource.get("sku") or "not reported",
        "observed_cost_period": "last 30 days",
        "observed_cost": cost,
        "currency": currency,
        "directional_seven_day_run_rate": weekly_run_rate,
        "performance_or_consumption": resource["performance"].get("metrics", {}),
    }
    return facts, json.dumps(facts, indent=2)


def _render_facts(facts: dict[str, Any]) -> str:
    if not facts:
        return ""
    lines = [
        "Current dashboard facts:",
        f"- Resource: {facts['resource_name']} ({facts['azure_resource_type']}) in {facts['region'] or 'an unreported region'}.",
        f"- Observed cost: {facts['currency']} {facts['observed_cost']:,.2f} for the last 30 days." if isinstance(facts.get("observed_cost"), (int, float)) else "- Observed cost: unavailable from the connected cost data.",
    ]
    if isinstance(facts.get("directional_seven_day_run_rate"), (int, float)):
        lines.append(
            f"- Directional 7-day run-rate estimate: {facts['currency']} {facts['directional_seven_day_run_rate']:,.2f}, calculated from the 30-day observed spend. It is not an Azure invoice forecast."
        )
    metrics = facts.get("performance_or_consumption") or {}
    if metrics:
        lines.append("- Performance / consumption: " + "; ".join(f"{key}: {value}" for key, value in metrics.items()) + ".")
    return "\n".join(lines)


def answer_finops_question(
    question: str,
    resource_group: str,
    subscription: str | None = None,
    context_resource: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Answer a scoped FinOps question without emitting an optimization verdict."""
    # Context is safe to add for policy classification: it allows questions
    # like "what is its cost?" when a selected resource is in scope.
    policy = assess_query_policy(f"Cloud cost optimization question: {question}")
    if not policy["allowed"]:
        return {"answer": str(policy["message"]), "facts": {}, "citations": [], "usage": None}

    snapshot = build_dashboard_data(resource_group, subscription)
    resource = _find_resource(snapshot["resources"], context_resource, question, history)
    # The dashboard lookup above is refreshed server-side for every turn, so
    # chat is never dependent on whether the browser happened to load a row.
    # If an explicitly requested resource cannot be resolved, fall back to the
    # existing /v1/analyses service logic rather than inventing telemetry.
    if resource is None:
        fallback = analyze_resources(question, resource_group, subscription)
        return {
            "answer": fallback["answer"],
            "facts": {},
            "citations": [{"source": item["source"], "page": item["page"]} for item in fallback["retrieved_contexts"]],
            "usage": fallback["application_usage"],
            "mode": "analysis_fallback",
        }
    facts, fact_text = _facts_for_prompt(resource)
    contexts = retrieve_best_practice_contexts(
        question,
        top_k=3,
        resource_names=[resource["name"]] if resource else None,
    )
    evidence = [{"source": item["source"], "page": item["page"], "text": item["text"]} for item in contexts]
    prompt = f"""You are a helpful Azure FinOps assistant. Answer the user's question directly in concise business language.

User question: {question}

Dashboard facts (authoritative for this answer):
{fact_text}

Recent conversation (use it only to resolve user references, never as factual evidence):
{json.dumps((history or [])[-8:])}

Retrieved best-practice evidence:
{json.dumps(evidence)}

Rules:
- Do not begin with a yes/no verdict or labels such as "Approved with conditions", "No", "Needs review", or "Evidence".
- If dashboard cost is present, distinguish the observed 30-day cost from the directional 7-day run-rate calculation. Never call the run-rate an invoice forecast.
- If a requested cost, forecast, or metric is unavailable, say exactly what is unavailable and how to obtain it from Azure Cost Management or monitoring.
- Explain the resource type and relevant FinOps practice using the supplied facts and evidence.
- Keep within cloud cost optimization and best-practice scope. Do not advise destructive changes.
- Do not invent Azure prices, consumption, billing data, or resource configuration.
- End with one practical, non-destructive next step when appropriate.
"""
    generated = get_llm_response(prompt)
    response = _render_facts(facts)
    if generated["text"].strip():
        response = f"{response}\n\nFinOps guidance:\n{generated['text'].strip()}" if response else generated["text"].strip()
    return {
        "answer": response,
        "facts": facts,
        "citations": [{"source": item["source"], "page": item["page"]} for item in contexts],
        "usage": generated["usage"],
        "mode": "dashboard_facts",
    }
