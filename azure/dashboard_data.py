"""Normalize Azure inventory, cost, and metric data for the dashboard.

The demo workspace supplies deterministic *Azure-shaped source telemetry* so
the UI is usable without Azure access.  It never supplies a recommendation:
recommendations are produced on demand by the RAG endpoint for demo and real
resource groups alike.  Real scopes use the signed-in Azure CLI identity;
missing permissions are represented as unavailable data, never fabricated as
zero cost or zero utilization.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
import json
from typing import Any

from azure.resource_fetcher import DEMO_RESOURCE_GROUP, fetch_all_resources, run_azure_cli


# This fixture contains only data one would obtain from Azure Resource Manager,
# Cost Management and Azure Monitor (inventory, cost and telemetry).  It does
# not encode an optimization technique, verdict, confidence, or saving amount.
DEMO_AZURE_TELEMETRY: dict[str, dict[str, Any]] = {
    "analytics-vm-01": {"cost": 418.26, "trend": 4.2, "metrics": {"CPU p95": "19%", "Memory p95": "42%", "Uptime": "99.8%"}},
    "web-prod-01": {"cost": 682.10, "trend": 8.7, "metrics": {"CPU p95": "71%", "Memory p95": "68%", "Uptime": "99.99%"}},
    "analytics-vm-01-data": {"cost": 121.90, "trend": 0.0, "metrics": {"Capacity": "1,024 GB", "State": "Unattached", "Snapshots": "14"}},
    "democostarchive": {"cost": 286.44, "trend": 1.1, "metrics": {"Capacity": "2.8 TB", "Cold data": "74%", "Access tier": "Hot"}},
    "democost-sql": {"cost": 3106.00, "trend": 3.7, "metrics": {"DTU p95": "76%", "Storage": "62%", "Log IO p95": "58%"}},
    "democost-app-plan": {"cost": 714.60, "trend": 11.9, "metrics": {"Workers": "3", "CPU p95": "58%", "Autoscale": "Not configured"}},
    "democost-portal": {"cost": 52.20, "trend": -2.4, "metrics": {"Requests": "1.3M", "Latency p95": "241 ms", "Availability": "99.95%"}},
    "democost-unused-ip": {"cost": 3.65, "trend": 0.0, "metrics": {"Allocation": "Static", "Assigned address": "No", "Association": "None"}},
    "democostregistry": {"cost": 842.10, "trend": 31.1, "metrics": {"SKU": "Premium", "Untagged images": "84", "Retention policy": "Not configured"}},
    "democost-kv": {"cost": 18.40, "trend": 0.6, "metrics": {"Purge protection": "Enabled", "RBAC": "Enabled", "Operations": "42K"}},
    "tailspin-unused-ip-02": {"cost": 3.65, "trend": 0.0, "metrics": {"Allocation": "Static", "Assigned address": "No", "Association": "None"}},
    "tailspin-batch-vm-02": {"cost": 454.70, "trend": -1.2, "metrics": {"CPU p95": "31%", "Memory p95": "46%", "Queue SLO": "10 min"}},
    "tailspin-archive-disk-02": {"cost": 65.10, "trend": 0.0, "metrics": {"Capacity": "512 GB", "State": "Unattached", "Classification": "Regulated"}},
    "tailspin-orphan-disk-03": {"cost": 22.80, "trend": 0.0, "metrics": {"Capacity": "256 GB", "State": "Unattached", "Reads/writes": "None for 45 days"}},
    "retry-lab-vm-01": {"cost": 406.91, "trend": 4.1, "metrics": {"CPU p95": "17%", "Memory p95": "39%", "Uptime": "99.7%"}},
}


def _type_label(resource_type: str) -> str:
    return resource_type.rsplit("/", 1)[-1].replace("serverfarms", "App Service plans").replace("publicIPAddresses", "Public IP addresses")


def _demo_cost_series(total: float, days: int) -> list[dict[str, Any]]:
    today = datetime.now(UTC).date()
    daily = total / max(days, 1)
    return [
        {
            "timestamp": datetime.combine(today - timedelta(days=days - offset - 1), datetime.min.time(), tzinfo=UTC).isoformat(),
            "cost": round(daily * (0.9 + ((offset * 7) % 13) / 100), 2),
        }
        for offset in range(days)
    ]


def _demo_resource(resource: dict[str, Any]) -> dict[str, Any]:
    name = resource["name"]
    details = DEMO_AZURE_TELEMETRY.get(name, {"cost": None, "trend": None, "metrics": {}})
    return {
        "id": resource["id"], "name": name, "type": resource["type"], "type_label": _type_label(resource["type"]),
        "region": resource.get("location"), "sku": (resource.get("sku") or {}).get("name") or resource.get("properties", {}).get("hardwareProfile", {}).get("vmSize"),
        "tags": resource.get("tags", {}),
        "cost": {"last_30_days": details["cost"], "trend_percent": details["trend"], "currency": "USD", "status": "available" if details["cost"] is not None else "unavailable"},
        "performance": {"metrics": details["metrics"], "status": "available" if details["metrics"] else "unavailable"},
        "optimization": {"status": "not_requested"},
    }


def _safe_json_cli(args: list[str]) -> Any | None:
    try:
        output = run_azure_cli(args, check=False)
        return json.loads(output) if output else None
    except Exception:
        return None


def _real_cost_by_resource(resource_group: str, subscription: str | None) -> tuple[dict[str, float], str | None]:
    if not subscription:
        return {}, "Select a subscription to load Cost Management data."
    scope = f"/subscriptions/{subscription}/resourceGroups/{resource_group}"
    body = {"type": "Usage", "timeframe": "MonthToDate", "dataset": {"granularity": "None", "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}}, "grouping": [{"type": "Dimension", "name": "ResourceId"}, {"type": "Dimension", "name": "Currency"}]}}
    result = _safe_json_cli(["az", "rest", "--method", "post", "--url", f"https://management.azure.com{scope}/providers/Microsoft.CostManagement/query?api-version=2025-03-01", "--body", json.dumps(body)])
    properties = result.get("properties", {}) if isinstance(result, dict) else {}
    columns, rows = properties.get("columns", []), properties.get("rows", [])
    positions = {column.get("name"): index for index, column in enumerate(columns)}
    if "ResourceId" not in positions or "PreTaxCost" not in positions:
        return {}, "Cost data is unavailable. Verify Cost Management Reader access and billing data availability."
    return {str(row[positions["ResourceId"]]).lower(): float(row[positions["PreTaxCost"]]) for row in rows if len(row) > max(positions.values())}, None


def _real_metric_summary(resource_id: str, resource_type: str) -> dict[str, str]:
    metric_by_type = {
        "Microsoft.Compute/virtualMachines": "Percentage CPU",
        "Microsoft.Web/serverfarms": "CpuPercentage",
        "Microsoft.Web/sites": "CpuTime",
        "Microsoft.Sql/servers": "dtu_consumption_percent",
    }
    metric = metric_by_type.get(resource_type)
    if not metric:
        return {}
    result = _safe_json_cli(["az", "monitor", "metrics", "list", "--resource", resource_id, "--metric", metric, "--interval", "P30D", "--aggregation", "Average", "Maximum", "--output", "json"])
    values = result.get("value", []) if isinstance(result, dict) else []
    points = [point for item in values for point in item.get("timeseries", [{}])[0].get("data", [])]
    averages = [point.get("average") for point in points if isinstance(point.get("average"), (int, float))]
    maximums = [point.get("maximum") for point in points if isinstance(point.get("maximum"), (int, float))]
    summary: dict[str, str] = {}
    if averages:
        summary[f"{metric} avg"] = f"{sum(averages) / len(averages):.1f}%"
    if maximums:
        summary[f"{metric} max"] = f"{max(maximums):.1f}%"
    return summary


def _real_resource(resource: dict[str, Any], costs: dict[str, float]) -> dict[str, Any]:
    resource_id = resource["id"]
    metrics = _real_metric_summary(resource_id, resource["type"])
    amount = costs.get(resource_id.lower())
    return {
        "id": resource_id, "name": resource["name"], "type": resource["type"], "type_label": _type_label(resource["type"]),
        "region": resource.get("location"), "sku": (resource.get("sku") or {}).get("name") or resource.get("properties", {}).get("hardwareProfile", {}).get("vmSize"),
        "tags": resource.get("tags", {}),
        "cost": {"last_30_days": round(amount, 2) if amount is not None else None, "trend_percent": None, "currency": "USD", "status": "available" if amount is not None else "unavailable"},
        "performance": {"metrics": metrics, "status": "available" if metrics else "unavailable"},
        "optimization": {"status": "not_requested"},
    }


def build_dashboard_data(resource_group: str, subscription: str | None = None, days: int = 30) -> dict[str, Any]:
    """Return a display-ready, source-labelled dashboard payload."""
    resources = fetch_all_resources(resource_group, subscription)
    is_demo = resource_group.strip().lower() == DEMO_RESOURCE_GROUP
    cost_error: str | None = None
    if is_demo:
        records = [_demo_resource(resource) for resource in resources]
    else:
        costs, cost_error = _real_cost_by_resource(resource_group, subscription)
        records = [_real_resource(resource, costs) for resource in resources]

    known_costs = [item["cost"]["last_30_days"] for item in records if isinstance(item["cost"]["last_30_days"], (int, float))]
    total_cost = round(sum(known_costs), 2)
    by_type: dict[str, float] = defaultdict(float)
    for item in records:
        if isinstance(item["cost"]["last_30_days"], (int, float)):
            by_type[item["type_label"]] += item["cost"]["last_30_days"]
    return {
        "scope": {"resource_group": resource_group, "subscription": subscription, "days": days},
        "source": "demo" if is_demo else "azure_cli",
        "last_refreshed": datetime.now(UTC).isoformat(),
        "availability": {"inventory": "available", "cost": "available" if is_demo or not cost_error else "unavailable", "performance": "available" if is_demo else "partial", "message": cost_error},
        "summary": {"total_cost": total_cost, "currency": "USD", "resource_count": len(records), "opportunity_count": None, "potential_monthly_savings": None, "high_confidence_count": None},
        "cost_trend": _demo_cost_series(total_cost, days) if is_demo else [],
        "cost_by_type": [{"name": name, "cost": round(amount, 2)} for name, amount in sorted(by_type.items(), key=lambda pair: pair[1], reverse=True)],
        "resources": sorted(records, key=lambda item: item["cost"]["last_30_days"] or 0, reverse=True),
    }
