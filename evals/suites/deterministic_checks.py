"""Fast, domain-specific checks that do not require a judge model."""

from pathlib import Path


def run(case: dict, answer: str, citations: list[dict]) -> list[str]:
    answer_lower = answer.lower()
    failures = []
    for text in case["must_contain"]:
        if text.lower() not in answer_lower:
            failures.append(f"missing required text: {text}")
    for text in case["must_not_contain"]:
        if text.lower() in answer_lower:
            failures.append(f"contains prohibited text: {text}")
    source_names = {Path(citation.get("source") or "").name for citation in citations}
    for expected_source in case["expected_sources"]:
        if expected_source not in source_names:
            failures.append(f"missing expected source: {expected_source}")
    return failures
