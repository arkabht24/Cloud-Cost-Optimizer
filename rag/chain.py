"""Compatibility wrapper for callers that only need the generated answer."""

from rag.service import analyze_resources


def run_chain(user_question: str, resource_group: str, subscription: str | None = None) -> str:
    return analyze_resources(
        question=user_question,
        resource_group=resource_group,
        subscription=subscription,
    )["answer"]
