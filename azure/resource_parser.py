import re


def parse_resource(raw: dict) -> dict:
    return {
        "name": raw.get("name"),
        "type": raw.get("type"),          # e.g. Microsoft.Compute/virtualMachines
        "region": raw.get("location"),
        "sku": raw.get("sku", {}).get("name") if raw.get("sku") else None,
        "kind": raw.get("kind"),
        "tags": raw.get("tags", {}),
        "properties": raw.get("properties", {})
    }


def parse_all_resources(raw_list: list) -> dict:
    """Parse and group resources by type to improve LLM clarity."""
    grouped = {}
    for r in raw_list:
        # Extract simple resource type name (e.g., 'virtualMachines' from 'Microsoft.Compute/virtualMachines')
        full_type = r.get("type", "Unknown")
        resource_type = full_type.split("/")[-1] if "/" in full_type else full_type

        if resource_type not in grouped:
            grouped[resource_type] = []
        grouped[resource_type].append(parse_resource(r))

    return grouped


def extract_resource_types_from_query(user_question: str) -> set:
    """Extract relevant resource types from user question to filter resources."""
    resource_patterns = (
        (r"\bvm\b|\bvirtual machines?\b", "virtualMachines"),
        (r"\bdisks?\b", "disks"),
        (r"\bstorage\b", "storageAccounts"),
        (r"\bdatabase\b|\bsql\b", "servers"),
        (r"\bnetwork\b", "virtualNetworks"),
        (r"\bnics?\b|\bnetwork interfaces?\b", "networkInterfaces"),
        (r"\bpublic ip(?: addresses?)?\b", "publicIPAddresses"),
        (r"\bload balancers?\b", "loadBalancers"),
        (r"\bapp service\b|\bapp service plans?\b", "serverfarms"),
        (r"\bweb apps?\b", "sites"),
        (r"\bcontainer registr(?:y|ies)\b|\bacr\b", "registries"),
        (r"\bkey vaults?\b", "vaults"),
    )

    question_lower = user_question.lower()
    relevant_types = {
        resource_type
        for pattern, resource_type in resource_patterns
        if re.search(pattern, question_lower)
    }
    return relevant_types if relevant_types else None


def resolve_resource_scope(resources: dict, user_question: str) -> dict:
    """Resolve an exact inventory scope before falling back to resource types.

    An explicit resource name is authoritative. A resource-like name which is
    absent from the inventory is deliberately surfaced so the service can
    abstain instead of generating advice for unrelated resources.
    """
    question_lower = user_question.lower()
    exact_matches = {
        resource_type: [
            resource
            for resource in items
            if re.search(
                rf"(?<![\w-]){re.escape(resource.get('name', '').lower())}(?![\w-])",
                question_lower,
            )
        ]
        for resource_type, items in resources.items()
    }
    exact_matches = {
        resource_type: items for resource_type, items in exact_matches.items() if items
    }
    if exact_matches:
        return {"status": "matched", "resources": exact_matches, "candidates": []}

    # Azure resource names commonly contain one or more hyphens. This is a
    # conservative signal for an explicit resource request, not a type query.
    candidates = re.findall(r"(?<![\w-])[a-z0-9]+(?:-[a-z0-9]+)+(?![\w-])", question_lower)
    if candidates:
        return {"status": "unknown_named", "resources": {}, "candidates": candidates}

    relevant_types = extract_resource_types_from_query(user_question)
    scoped_resources = resources if relevant_types is None else {
        resource_type: items
        for resource_type, items in resources.items()
        if resource_type in relevant_types
    }
    return {"status": "type_or_broad", "resources": scoped_resources, "candidates": []}


def filter_relevant_resources(resources: dict, user_question: str) -> dict:
    """Filter resources based on an exact name or token-aware type match."""
    return resolve_resource_scope(resources, user_question)["resources"]
