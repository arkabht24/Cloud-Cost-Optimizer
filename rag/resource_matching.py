"""Token-aware helpers for matching inventory resource names in retrieved text."""

from __future__ import annotations

import re


def mentions_resource(text: str, resource_name: str) -> bool:
    """Match a complete Azure resource name, never a hyphenated prefix.

    For example, ``analytics-vm-01`` must not match
    ``analytics-vm-01-data``.
    """
    return bool(re.search(
        rf"(?<![\w-]){re.escape(resource_name.lower())}(?![\w-])",
        text.lower(),
    ))


def count_resource_mentions(text: str, resource_name: str) -> int:
    return len(re.findall(
        rf"(?<![\w-]){re.escape(resource_name.lower())}(?![\w-])",
        text.lower(),
    ))


def resource_blocks(
    text: str,
    allowed_names: list[str],
    inventory_names: list[str],
) -> list[str]:
    """Return only line groups belonging to the requested resource(s).

    Retrieved parent chunks can contain several inventory resources. A new
    block begins at an allowed resource, and ends before another known resource
    starts. This prevents an adjacent disk record from becoming VM evidence.
    """
    blocks: list[str] = []
    active_lines: list[str] = []
    active = False
    allowed_lower = [name.lower() for name in allowed_names]
    inventory_lower = [name.lower() for name in inventory_names]

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        is_allowed = any(mentions_resource(line, name) for name in allowed_lower)
        is_other_resource = any(
            mentions_resource(line, name)
            for name in inventory_lower
            if name not in allowed_lower
        )
        if is_allowed:
            if active_lines:
                blocks.append(" ".join(active_lines))
            active_lines, active = [line], True
        elif is_other_resource:
            if active_lines:
                blocks.append(" ".join(active_lines))
            active_lines, active = [], False
        elif active:
            active_lines.append(line)

    if active_lines:
        blocks.append(" ".join(active_lines))
    return blocks
