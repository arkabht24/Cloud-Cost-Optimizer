import json
from azure.resource_parser import filter_relevant_resources


def build_prompt(
    resources: dict,
    retrieved_chunks: str,
    user_question: str,
    scoped_resources: dict | None = None,
) -> str:
    """Build a structured prompt with resources grouped by type for clarity."""

    # Filter resources to only relevant types based on user question
    filtered_resources = scoped_resources if scoped_resources is not None else filter_relevant_resources(resources, user_question)
    allowed_names = [
        resource["name"]
        for items in filtered_resources.values()
        for resource in items
    ]

    # Format resources with clear sections for each type
    resources_text = ""
    total_resources = 0

    for resource_type, items in sorted(filtered_resources.items()):
        s = "s" if len(items) > 1 else ""
        resources_text += f"\n## {resource_type} ({len(items)} resource{s})\n"
        resources_text += json.dumps(items, indent=2)
        resources_text += "\n"
        total_resources += len(items)

    if total_resources == 0:
        resources_text = "(No relevant resources found for this query)"

    plural_s = "s" if total_resources != 1 else ""

    return f"""You are an Azure cloud cost optimization expert.

# Real-Time Azure Resources (Grouped by Type)
Total: {total_resources} resource{plural_s}
{resources_text}
# Relevant Best Practices (from knowledge base)
{retrieved_chunks}

# User Question
{user_question}

Allowed resource names: {json.dumps(allowed_names)}

Answer format:
1. Start with a direct decision: Yes, No, Needs review, or Insufficient evidence.
2. Discuss only the allowed resource names. Evidence mentioning another resource is background only and must not be repeated.
3. List the evidence and mandatory approval, dependency, retention, or rollback conditions.
4. Do not state that no further action is required when a condition still needs to be completed.
Keep the answer concise and do not repeat the user question.

Analyze only the resources included above. For each relevant resource, provide specific cost optimization advice based on the retrieved evidence.
Consider:
- Resource-specific configurations (SKU, size, settings)
- Redundancy and high-availability requirements
- Actual vs. peak usage patterns
- When the question names a specific resource, answer only about that resource.
- Do not invent, rename, or discuss resources that are not included above.
- Clearly distinguish an observed fact, a proposed action, and an approved, pending, or deferred action.
- Do not recommend deletion, downsizing, or configuration changes when the evidence requires owner approval, retention checks, a dependency check, or a rollback plan.
- If the retrieved evidence is insufficient, state that explicitly.
"""


def build_scope_repair_prompt(
    question: str,
    allowed_names: list[str],
    retrieved_chunks: str,
    draft_answer: str,
) -> str:
    """Request one bounded rewrite when the initial answer leaks resource scope."""
    return f"""Rewrite the draft answer to comply with the scope rules.

Question: {question}
Allowed resource names: {json.dumps(allowed_names)}
Retrieved evidence:\n{retrieved_chunks}
Draft answer:\n{draft_answer}

Return only the revised answer. Start with Yes, No, Needs review, or Insufficient evidence.
Mention only the allowed resource names. Do not repeat facts or recommendations about any other resource, even if they appear in the evidence. Include only supported evidence and mandatory safety conditions."""
