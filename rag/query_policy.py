"""Deterministic request-scope policy for the cloud cost RAG application."""

from __future__ import annotations

import re
from typing import TypedDict


class QueryPolicyResult(TypedDict):
    allowed: bool
    reason_code: str | None
    message: str | None


# Deletion-like requests are intentionally handled before retrieval. This is a
# product-scope boundary, not an LLM judgement: no retrieved document should
# make the application advise a destructive resource action.
DELETION_PATTERN = re.compile(
    r"\b(delete|deletion|remove|removal|retire|retirement|decommission|"
    r"destroy|destruction|purge|terminate|termination|drop)\b",
    re.IGNORECASE,
)

# These terms define the application's supported domain. They deliberately
# cover both questions about money and operational practices that affect cost.
COST_OPTIMIZATION_PATTERN = re.compile(
    r"\b(cost|costs|spend|spending|saving|savings|budget|price|pricing|"
    r"optimi[sz](?:e|ation)|rightsiz(?:e|ing)|downsizing|downsize|downgrad(?:e|ing)|"
    r"utilization|capacity|sku|tier|reservation|reserved|lifecycle|autoscal(?:e|ing)|"
    r"scale|idle|unused|unattached|efficiency|best practice|best practices)\b",
    re.IGNORECASE,
)


def assess_query_policy(question: str) -> QueryPolicyResult:
    """Allow only non-destructive cloud cost and best-practice requests.

    This intentionally uses transparent keyword rules rather than an LLM so
    the scope boundary is fast, predictable, auditable, and cannot be bypassed
    by an unrelated retrieved document.
    """
    normalized = question.strip()
    if DELETION_PATTERN.search(normalized):
        return {
            "allowed": False,
            "reason_code": "deletion_not_supported",
            "message": (
                "This assistant provides cloud cost optimization and best-practice guidance, "
                "but it does not provide deletion or removal guidance. Ask about rightsizing, "
                "utilization, SKU selection, lifecycle policy, reservations, or autoscaling instead."
            ),
        }
    if not COST_OPTIMIZATION_PATTERN.search(normalized):
        return {
            "allowed": False,
            "reason_code": "outside_cost_optimization_scope",
            "message": (
                "This assistant only answers cloud cost optimization and best-practice questions. "
                "Ask about utilization, rightsizing, cost savings, SKU selection, lifecycle policy, "
                "reservations, or autoscaling."
            ),
        }
    return {"allowed": True, "reason_code": None, "message": None}
