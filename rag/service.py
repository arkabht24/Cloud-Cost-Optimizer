"""Reusable, traceable RAG service used by the UI, API, and future evaluations."""

import logging
from time import perf_counter
from typing import Any

from azure.resource_fetcher import fetch_all_resources

from azure.resource_parser import parse_all_resources, resolve_resource_scope
from config.settings import COLLECTION_NAME, LLM_PROVIDER, OLLAMA_MODEL, RETRIEVAL_TOP_K
from rag.llm_client import get_llm_response
from rag.response_policy import (
    build_repair_prompt,
    build_structured_answer_prompt,
    deduplicate_decision_fields,
    extract_evidence_plan,
    fallback_answer,
    parse_structured_answer,
    render_answer,
    validate_structured_answer,
)
from rag.retriever import retrieve_best_practice_contexts
from rag.retrieval_quality import assess_retrieval_quality, build_resource_focused_query


# Uvicorn configures this logger with its console handler at INFO level. Using
# it makes retry diagnostics visible in `uvicorn` output without requiring an
# application-wide logging configuration.
logger = logging.getLogger("uvicorn.error")


def _log_retrieval_attempt(strategy: str, quality: dict[str, Any]) -> None:
    """Emit operational retry diagnostics without logging prompts or evidence text."""
    logger.info(
        "retrieval_quality strategy=%s passed=%s resources=%s matches=%s roles=%s issues=%s",
        strategy,
        quality["passed"],
        quality["requested_resources"],
        quality["matching_context_count"],
        quality["evidence_roles"],
        quality["issues"],
    )


def analyze_resources(
    question: str,
    resource_group: str = "demo-cost-lab",
    subscription: str | None = None,
    top_k: int = RETRIEVAL_TOP_K,
) -> dict[str, Any]:
    """Run the RAG flow and return an evaluation-friendly execution trace."""
    started_at = perf_counter()
    generation_calls: list[dict[str, Any]] = []
    raw_resources = fetch_all_resources(resource_group, subscription)
    resources = parse_all_resources(raw_resources)
    scope = resolve_resource_scope(resources, question)
    scoped_resources = scope["resources"]
    allowed_names = [
        resource["name"]
        for items in scoped_resources.values()
        for resource in items
    ]

    if scope["status"] == "unknown_named":
        requested_name = scope["candidates"][0]
        answer = (
            f"Insufficient evidence. {requested_name} was not found in the supplied inventory, "
            "so its ownership, dependencies, retention requirements, and deletion safety cannot be determined."
        )
        contexts = []
        retrieval_quality = {
            "passed": False,
            "action": "review",
            "requested_resources": [requested_name],
            "matching_context_count": 0,
            "evidence_roles": [],
            "source_count": 0,
            "sources": [],
            "best_relevance_score": None,
            "issues": ["The requested resource is not present in the supplied inventory."],
            "attempts": [{"strategy": "inventory_abstention", "passed": False}],
        }
        prompt = None
        scope_rewrite_applied = False
        response_mode = "inventory_abstention"
        decision = {
            "decision": "insufficient_evidence",
            "resource": requested_name,
            "reason": ["The resource is not present in the supplied inventory."],
            "required_conditions": ["Confirm ownership, dependencies, retention, and deletion safety."],
            "recommended_next_step": "Locate the resource in the authoritative inventory before acting.",
            "citation_ids": [],
        }
    else:
        all_inventory_names = [
            resource["name"] for items in resources.values() for resource in items
        ]
        contexts = retrieve_best_practice_contexts(
            question,
            top_k=top_k,
            resource_names=allowed_names,
        )
        retrieval_quality = assess_retrieval_quality(
            question, contexts, allowed_names, inventory_names=all_inventory_names
        )
        _log_retrieval_attempt("initial", retrieval_quality)
        attempts = [{"strategy": "initial", **retrieval_quality}]
        if not retrieval_quality["passed"]:
            logger.info("retrieval_retry strategy=expanded_candidate_rerank resources=%s", allowed_names)
            contexts = retrieve_best_practice_contexts(
                question,
                top_k=top_k,
                resource_names=allowed_names,
                candidate_multiplier=12,
            )
            retrieval_quality = assess_retrieval_quality(
                question, contexts, allowed_names, inventory_names=all_inventory_names
            )
            _log_retrieval_attempt("expanded_candidate_rerank", retrieval_quality)
            attempts.append({"strategy": "expanded_candidate_rerank", **retrieval_quality})
        if not retrieval_quality["passed"]:
            logger.info("retrieval_retry strategy=resource_focused_query_rewrite resources=%s", allowed_names)
            rewritten_query = build_resource_focused_query(question, allowed_names)
            contexts = retrieve_best_practice_contexts(
                rewritten_query,
                top_k=top_k,
                resource_names=allowed_names,
                candidate_multiplier=12,
            )
            retrieval_quality = assess_retrieval_quality(
                question, contexts, allowed_names, inventory_names=all_inventory_names
            )
            _log_retrieval_attempt("resource_focused_query_rewrite", retrieval_quality)
            attempts.append({"strategy": "resource_focused_query_rewrite", **retrieval_quality})
        retrieval_quality["attempts"] = attempts
        plan = extract_evidence_plan(
            question,
            allowed_names,
            contexts,
            inventory_names=all_inventory_names,
        )
        scope_rewrite_applied = False
        if not retrieval_quality["passed"]:
            logger.warning(
                "retrieval_quality_abstention resources=%s issues=%s",
                allowed_names,
                retrieval_quality["issues"],
            )
            decision = fallback_answer({
                "decision": "insufficient_evidence",
                "resources": allowed_names,
                "evidence": [],
                "required_conditions": [],
            })
            prompt = None
            response_mode = "retrieval_quality_abstention"
        else:
            prompt = build_structured_answer_prompt(question, allowed_names, contexts, plan)
            generated_result = get_llm_response(prompt)
            generated = generated_result["text"]
            generation_calls.append({"purpose": "initial_generation", **generated_result["usage"]})
            decision = parse_structured_answer(generated)
            valid, _ = validate_structured_answer(decision, plan, all_inventory_names)
            if not valid:
                scope_rewrite_applied = True
                repaired_result = get_llm_response(build_repair_prompt(generated, question, plan))
                repaired = repaired_result["text"]
                generation_calls.append({"purpose": "repair_generation", **repaired_result["usage"]})
                decision = parse_structured_answer(repaired)
                valid, _ = validate_structured_answer(decision, plan, all_inventory_names)
            if valid:
                response_mode = "structured_repair" if scope_rewrite_applied else "structured"
            else:
                decision = fallback_answer(plan)
                response_mode = "evidence_fallback"
        answer = render_answer(deduplicate_decision_fields(decision))

    def aggregate_usage() -> dict[str, Any]:
        """Aggregate only RAG application calls; Judge calls never reach here."""
        base = generation_calls[0] if generation_calls else {}
        token_fields = ("input_tokens", "output_tokens", "total_tokens")
        totals = {}
        for field in token_fields:
            values = [call.get(field) for call in generation_calls]
            totals[field] = sum(values) if values and all(isinstance(value, int) for value in values) else None
        return {
            "provider": base.get("provider", LLM_PROVIDER),
            "deployment": base.get("deployment", "local" if LLM_PROVIDER == "ollama" else "api"),
            "model": base.get("model", OLLAMA_MODEL if LLM_PROVIDER == "ollama" else None),
            "generation_calls": len(generation_calls),
            **totals,
        }

    return {
        "answer": answer,
        "question": question,
        "resource_group": resource_group,
        "resources": resources,
        "scope": {
            "status": scope["status"],
            "matched_resources": allowed_names,
            "scope_rewrite_applied": scope_rewrite_applied,
            "response_mode": response_mode,
        },
        "retrieved_contexts": contexts,
        "retrieval_quality": retrieval_quality,
        "prompt": prompt,
        "decision": decision,
        "meta": {
            "provider": LLM_PROVIDER,
            "model": OLLAMA_MODEL if LLM_PROVIDER == "ollama" else None,
            "collection": COLLECTION_NAME,
            "top_k": top_k,
            "latency_ms": round((perf_counter() - started_at) * 1000),
        },
        "application_usage": aggregate_usage(),
    }
