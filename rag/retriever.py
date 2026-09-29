import os

from config.settings import CHROMA_DB_PATH
from ingestion.vector_store import query_vector_store_with_metadata
from rag.resource_matching import count_resource_mentions, mentions_resource


DEFAULT_COST_BEST_PRACTICES = """\
- Rightsize virtual machines from measured CPU, memory, and utilization data; schedule non-production workloads outside business hours when owners approve.
- Review unattached disks and unused public IP addresses with their owners before removal.
- Apply storage lifecycle policies only when resilience, retention, and retrieval requirements permit.
- Do not downsize production capacity without measured demand, owner approval, and a rollback plan.
"""


def _rerank_for_resources(contexts, resource_names, top_k, query=""):
    """Select complementary operational, policy, and decision evidence."""
    if not resource_names:
        return contexts[:top_k]

    names = [name.lower() for name in resource_names]
    action_priority = _evidence_role_priority(query)

    # A scoped question must not borrow a decision from a different resource.
    # Keep only exact-name candidates whenever any are available; generic
    # guidance remains a fallback when the vector store has no scoped evidence.
    scoped_candidates = [
        context for context in contexts
        if any(mentions_resource(context["text"], name) for name in names)
    ]
    if scoped_candidates:
        contexts = scoped_candidates

    def rank(context):
        text = context["text"].lower()
        exact_mentions = sum(count_resource_mentions(text, name) for name in names)
        semantic_score = context["score"] if context["score"] is not None else 0
        return (exact_mentions > 0, exact_mentions, semantic_score)

    ranked = sorted(contexts, key=rank, reverse=True)
    # First take the best matching context for each evidence role. A complete
    # action recommendation needs more than a single semantically similar PDF.
    selected, seen_sources = [], set()
    for role in action_priority:
        candidate = next(
            (
                item for item in ranked
                if (item.get("evidence_role") or _infer_evidence_role(item["text"])) == role
                and item.get("source") not in seen_sources
            ),
            None,
        )
        if candidate:
            selected.append(candidate)
            seen_sources.add(candidate.get("source"))
        if len(selected) == top_k:
            return selected

    for context in ranked:
        if context not in selected and context.get("source") not in seen_sources:
            selected.append(context)
            seen_sources.add(context.get("source"))
        if len(selected) == top_k:
            break
    return selected


def _infer_evidence_role(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in ("known exceptions", "required follow-up", "rollback window", "retained")):
        return "exception"
    if "decision register" in lowered:
        return "decision"
    if any(marker in lowered for marker in ("p95", "unattached", "no reads", "utilization", "metrics", "snapshot")):
        return "utilization"
    if any(marker in lowered for marker in ("approved", "deferred", "pending")):
        return "decision"
    return "policy"


def _evidence_role_priority(query: str) -> tuple[str, ...]:
    """Choose a general evidence mix based on the requested action wording."""
    question = query.lower()
    if any(term in question for term in ("delete", "remove")):
        return ("decision", "utilization", "policy", "exception")
    if any(term in question for term in ("downsize", "downgrade")):
        return ("decision", "exception", "utilization", "policy")
    return ("decision", "utilization", "policy", "exception")


def retrieve_best_practice_contexts(query, top_k=3, resource_names=None, candidate_multiplier=6):
    """Return traceable retrieved contexts, or local fallback guidance before ingestion."""
    parent_store_path = os.path.join(CHROMA_DB_PATH, "parents.json")
    if not os.path.isfile(parent_store_path):
        return [{
            "id": "built-in-guidance",
            "text": DEFAULT_COST_BEST_PRACTICES,
            "score": None,
            "source": "built-in-guidance",
            "page": None,
            "chunk_index": None,
        }]
    # Fetch extra semantic candidates before applying the deterministic,
    # resource-name-aware reranker. This avoids a broad multi-resource chunk
    # crowding out evidence for the explicitly requested resource.
    candidates = query_vector_store_with_metadata(
        query, top_k=max(top_k * candidate_multiplier, top_k)
    )
    return _rerank_for_resources(candidates, resource_names or [], top_k, query=query)


def retrieve_best_practices(query, top_k=3):
    """Backward-compatible text-only retrieval helper."""
    contexts = retrieve_best_practice_contexts(query, top_k=top_k)
    return "\n\n".join(context["text"] for context in contexts)
