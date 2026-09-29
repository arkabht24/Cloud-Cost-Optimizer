"""Evidence-first response planning and validation for cost recommendations."""

import json
import re
from typing import Any

from rag.resource_matching import mentions_resource, resource_blocks


DECISIONS = {"yes", "no", "approved_with_conditions", "needs_review", "insufficient_evidence"}
CONDITION_MARKERS = (
    "approval", "approve", "owner", "dependency", "retention", "retain",
    "rollback", "snapshot", "load test", "reassess", "after ", "pending",
)
NEGATIVE_MARKERS = (
    "do not downsize", "do not downgrade", "no immediate", "hold deletion",
    "retain", "deferred", "pending", "not clearly over-provisioned",
)
APPROVED_MARKERS = ("approved", "remove after", "delete after", "can be removed after")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sentences(text: str) -> list[str]:
    return [
        _clean_text(part).strip(" -•")
        for part in re.split(r"\n+|(?<=[.!?])\s+", text)
        if _clean_text(part).strip(" -•")
    ]


def _action_from_question(question: str) -> str:
    lowered = question.lower()
    if any(action in lowered for action in ("delete", "remove", "retire", "decommission", "get rid of")):
        return "remove"
    if any(action in lowered for action in ("downsize", "downgrade", "rightsize", "reduce capacity")):
        return "downsize"
    return "review"


def extract_evidence_plan(
    question: str,
    resource_names: list[str],
    contexts: list[dict],
    inventory_names: list[str] | None = None,
) -> dict[str, Any]:
    """Turn retrieved evidence into a compact, model-independent decision plan."""
    action = _action_from_question(question)
    names = [name.lower() for name in resource_names]
    evidence: list[dict[str, str]] = []
    conditions: list[str] = []
    inventory_names = [name.lower() for name in inventory_names or resource_names]

    for context in contexts:
        for block in resource_blocks(context["text"], resource_names, inventory_names):
            for sentence in _sentences(block):
                lowered = sentence.lower()
                references_resource = any(mentions_resource(sentence, name) for name in names)
                mentions_condition = any(marker in lowered for marker in CONDITION_MARKERS)
                mentions_observation = any(marker in lowered for marker in ("unattached", "reads", "writes", "recovery artifact", "retained"))
                # A parent paragraph can describe a VM and an associated disk.
                # Disk hygiene is not evidence for a VM capacity-reduction
                # decision unless the VM itself is named in that sentence.
                if action == "downsize" and "disk" in lowered and not references_resource:
                    continue
                if not (references_resource or mentions_condition or mentions_observation):
                    continue
                item = {"text": sentence, "citation_id": str(context["id"])}
                if item not in evidence:
                    evidence.append(item)
                if mentions_condition and sentence not in conditions:
                    conditions.append(sentence)

    combined_evidence = " ".join(item["text"] for item in evidence).lower()
    question_lower = question.lower()
    # A required condition means an action cannot be taken "immediately" or
    # "today", even if it may become approved after that condition is met.
    if conditions and ("immediately" in question_lower or " today" in question_lower):
        decision = "no"
    # Prefer safety over optimistic interpretation when the selected evidence is mixed.
    elif any(marker in combined_evidence for marker in NEGATIVE_MARKERS):
        decision = "no"
    elif any(marker in combined_evidence for marker in APPROVED_MARKERS):
        decision = "approved_with_conditions"
    else:
        decision = "needs_review"

    if not evidence:
        decision = "insufficient_evidence"

    return {
        "action": action,
        "decision": decision,
        "resources": resource_names,
        "evidence": evidence[:5],
        "required_conditions": conditions[:4],
    }


def build_structured_answer_prompt(
    question: str,
    resource_names: list[str],
    contexts: list[dict],
    plan: dict[str, Any],
) -> str:
    """Ask the model for a constrained transport format, not free-form prose."""
    schema = {
        "decision": "yes | no | approved_with_conditions | needs_review | insufficient_evidence",
        "resource": "one exact allowed resource name",
        "reason": ["one to three evidence-backed statements"],
        "required_conditions": ["mandatory safeguards before the action"],
        "recommended_next_step": "one concise action",
        "citation_ids": ["ids from supplied evidence"],
    }
    return f"""You are an Azure cost-optimization response generator.
Return JSON only, with no Markdown and no explanation outside the JSON.

Question: {question}
Allowed resource names: {json.dumps(resource_names)}
Structured evidence plan: {json.dumps(plan)}
Retrieved evidence: {json.dumps(contexts)}
Required JSON schema: {json.dumps(schema)}

Rules:
- Use only an allowed resource name.
- Follow the evidence-plan decision. A pending, deferred, retained, or approval-required action is not immediately allowed.
- Include all material approval, dependency, retention, rollback, or load-test conditions from the evidence plan.
- Do not mention another resource, generic regional pricing, or an unsupported recommendation.
- For a yes/no question, the decision must answer it directly."""


def build_repair_prompt(draft: str, question: str, plan: dict[str, Any]) -> str:
    return f"""Return corrected JSON only. Repair this cost-optimization response so it follows the required schema and evidence plan.

Question: {question}
Evidence plan: {json.dumps(plan)}
Draft response: {draft}

Use the same JSON schema fields: decision, resource, reason, required_conditions, recommended_next_step, citation_ids.
Do not mention resources outside {json.dumps(plan['resources'])}."""


def parse_structured_answer(value: str) -> dict[str, Any] | None:
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def validate_structured_answer(
    payload: dict[str, Any] | None,
    plan: dict[str, Any],
    all_inventory_names: list[str],
) -> tuple[bool, str]:
    if not payload:
        return False, "response was not a JSON object"
    if payload.get("decision") not in DECISIONS:
        return False, "invalid decision"
    if payload.get("resource") not in plan["resources"]:
        return False, "response used an out-of-scope resource"
    if plan["decision"] in {"no", "approved_with_conditions"} and payload["decision"] != plan["decision"]:
        return False, "response contradicted the evidence-plan decision"
    if not isinstance(payload.get("reason"), list) or not payload["reason"]:
        return False, "response omitted evidence-backed reasons"
    if plan["required_conditions"] and not payload.get("required_conditions"):
        return False, "response omitted mandatory conditions"

    text = json.dumps(payload).lower()
    for name in all_inventory_names:
        if name not in plan["resources"] and re.search(rf"(?<![\w-]){re.escape(name.lower())}(?![\w-])", text):
            return False, f"response leaked out-of-scope resource {name}"
    return True, ""


def fallback_answer(plan: dict[str, Any]) -> dict[str, Any]:
    """Produce a safe evidence-grounded response if structured generation fails."""
    resource = plan["resources"][0] if plan["resources"] else "the requested resource"
    evidence = [item["text"] for item in plan["evidence"]]
    conditions = plan["required_conditions"]
    next_step = (
        "Complete the required conditions and reassess the action."
        if conditions else "Gather the required ownership and utilization evidence before acting."
    )
    return {
        "decision": plan["decision"],
        "resource": resource,
        "reason": evidence or ["The retrieved evidence is insufficient for a safe recommendation."],
        "required_conditions": conditions,
        "recommended_next_step": next_step,
        "citation_ids": [item["citation_id"] for item in plan["evidence"]],
    }


def deduplicate_decision_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Do not render identical evidence as both a reason and a condition."""
    conditions = payload.get("required_conditions")
    reasons = payload.get("reason")
    if not isinstance(conditions, list) or not isinstance(reasons, list):
        return payload
    normalized_conditions = {_clean_text(str(item)).lower() for item in conditions}
    payload["reason"] = [
        item for item in reasons
        if _clean_text(str(item)).lower() not in normalized_conditions
    ]
    return payload


def render_answer(payload: dict[str, Any]) -> str:
    labels = {
        "yes": "Yes.",
        "no": "No.",
        "approved_with_conditions": "Approved with conditions.",
        "needs_review": "Needs review.",
        "insufficient_evidence": "Insufficient evidence.",
    }
    lines = [labels[payload["decision"]], f"Resource: {payload['resource']}"]
    if payload.get("reason"):
        lines.append("Evidence:")
        lines.extend(f"- {item}" for item in payload["reason"])
    if payload.get("required_conditions"):
        lines.append("Required conditions:")
        lines.extend(f"- {item}" for item in payload["required_conditions"])
    lines.append(f"Next step: {payload.get('recommended_next_step', '')}")
    return "\n".join(lines)
