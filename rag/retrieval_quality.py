"""Deterministic, low-latency checks used before asking the generation LLM.

This module deliberately does not call an evaluator model.  It checks whether
the evidence selected for an action has the minimum operational coverage needed
to make a safe answer.  RAGAS remains an offline evaluation tool, not a
per-request production dependency.
"""

from __future__ import annotations

from typing import Any

from rag.resource_matching import resource_blocks


def action_from_question(question: str) -> str:
    lowered = question.lower()
    if any(word in lowered for word in ("delete", "remove", "retire", "decommission", "get rid of")):
        return "remove"
    if any(word in lowered for word in ("downsize", "downgrade", "rightsize", "reduce capacity")):
        return "downsize"
    return "review"


def evidence_role(context: dict[str, Any], text: str | None = None) -> str:
    # Roles for a named question must be derived from its resource-specific
    # block, rather than broad metadata from a parent chunk mentioning several
    # resources.
    declared = context.get("evidence_role") if text is None else None
    if declared:
        return str(declared)
    lowered = str(text if text is not None else context.get("text", "")).lower()
    if any(marker in lowered for marker in ("known exceptions", "required follow-up", "rollback window", "retained")):
        return "exception"
    if "decision register" in lowered or any(marker in lowered for marker in ("approved", "deferred", "pending")):
        return "decision"
    if any(marker in lowered for marker in ("p95", "unattached", "no reads", "utilization", "metrics", "snapshot")):
        return "utilization"
    return "policy"


def assess_retrieval_quality(
    question: str,
    contexts: list[dict[str, Any]],
    resource_names: list[str],
    inventory_names: list[str] | None = None,
) -> dict[str, Any]:
    """Return explainable quality signals and a deterministic pass/fail verdict.

    Exact resource evidence is essential for a scoped recommendation.  For
    destructive or capacity-reduction questions, the answer also needs a
    decision/exception plus an operational or policy safeguard.  This avoids
    treating a high vector similarity score as proof that an action is safe.
    """
    action = action_from_question(question)
    inventory_names = inventory_names or resource_names
    matching: list[tuple[dict[str, Any], str]] = []
    for context in contexts:
        for block in resource_blocks(context.get("text", ""), resource_names, inventory_names):
            matching.append((context, block))
    roles = sorted({evidence_role(context, block) for context, block in matching})
    sources = sorted({str(context.get("source")) for context, _ in matching if context.get("source")})
    scores = [context.get("score") for context, _ in matching if isinstance(context.get("score"), (int, float))]

    issues: list[str] = []
    if not contexts:
        issues.append("No contexts were retrieved.")
    if resource_names and not matching:
        issues.append("No retrieved context names the requested resource.")
    if action == "remove":
        if not ({"decision", "exception"} & set(roles)):
            issues.append("Removal evidence lacks a decision or exception record.")
        if not ({"utilization", "policy", "exception"} & set(roles)):
            issues.append("Removal evidence lacks a utilization, policy, or exception safeguard.")
    elif action == "downsize":
        if not ({"decision", "exception"} & set(roles)):
            issues.append("Rightsizing evidence lacks a decision or exception record.")
        if "utilization" not in roles:
            issues.append("Rightsizing evidence lacks measured utilization evidence.")

    return {
        "passed": not issues,
        "action": action,
        "requested_resources": resource_names,
        "matching_context_count": len(matching),
        "evidence_roles": roles,
        "source_count": len(sources),
        "sources": sources,
        "best_relevance_score": max(scores) if scores else None,
        "issues": issues,
    }


def build_resource_focused_query(question: str, resource_names: list[str]) -> str:
    """Rewrite retrieval only; preserve the user's original question for generation."""
    action = action_from_question(question)
    names = ", ".join(resource_names) or "requested resource"
    if action == "remove":
        need = "decision approval or hold, utilization or dependency evidence, retention and rollback safeguards"
    elif action == "downsize":
        need = "decision or exception record and measured utilization, capacity, owner approval, and rollback safeguards"
    else:
        need = "resource-specific decision, utilization, policy, and exception evidence"
    return f"Resource: {names}. Requested action: {action}. Retrieve {need}. Original question: {question}"
