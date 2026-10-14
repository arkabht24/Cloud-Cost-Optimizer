"""Self-contained HTML report renderer for a dashboard snapshot.

The generated document intentionally contains no credentials, prompts, or raw
provider payloads.  It is safe to download and share after the normal access
review for the underlying Azure resource data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any


def _money(value: Any, currency: str = "USD") -> str:
    return f"{currency} {value:,.2f}" if isinstance(value, (int, float)) else "Not available"


def _label(value: Any) -> str:
    labels = {
        "yes": "Opportunity identified",
        "no": "No change advised",
        "approved_with_conditions": "Action after validation",
        "needs_review": "Review required",
        "insufficient_evidence": "More evidence needed",
        "analysis_unavailable": "Analysis unavailable",
        "not_supported": "Outside scope",
    }
    return labels.get(str(value), str(value or "Not analysed").replace("_", " ").title())


def render_stakeholder_report(dashboard: dict[str, Any], analyses: dict[str, Any]) -> str:
    """Render facts and completed RAG assessments as a portable HTML document."""
    summary = dashboard["summary"]
    currency = summary["currency"]
    costs = [point["cost"] for point in dashboard.get("cost_trend", [])]
    max_cost = max(costs, default=1)
    chart_points = " ".join(
        f"{index * 100 / max(len(costs) - 1, 1):.2f},{100 - (cost / max_cost * 82):.2f}"
        for index, cost in enumerate(costs)
    )
    cost_mix = dashboard.get("cost_by_type", [])[:6]
    max_mix_cost = max((item["cost"] for item in cost_mix), default=1)
    cost_mix_bars = "".join(
        "<div class='bar-row'>"
        f"<span>{escape(item['name'])}</span><div class='bar'><i style='width:{item['cost'] / max_mix_cost * 100:.1f}%'></i></div><strong>{_money(item['cost'], currency)}</strong>"
        "</div>"
        for item in cost_mix
    )
    rows = []
    assessment_sections = []
    for resource in dashboard["resources"]:
        result = analyses.get(resource["name"], {})
        decision = result.get("decision", {}).get("decision") if isinstance(result, dict) else None
        answer = result.get("answer") if isinstance(result, dict) else None
        metrics = " · ".join(f"{key}: {value}" for key, value in resource["performance"]["metrics"].items()) or "Not available"
        rows.append(
            "<tr>"
            f"<td><strong>{escape(resource['name'])}</strong><br><small>{escape(resource['type_label'])} · {escape(resource.get('region') or 'Not reported')}</small></td>"
            f"<td>{_money(resource['cost']['last_30_days'], resource['cost']['currency'])}</td>"
            f"<td>{escape(metrics)}</td>"
            f"<td><span class='pill'>{escape(_label(decision))}</span></td>"
            "</tr>"
        )
        if answer:
            assessment_sections.append(
                "<article class='assessment'>"
                f"<p class='eyebrow'>AI RESPONSE · {escape(_label(decision))}</p>"
                f"<h3>{escape(resource['name'])}</h3>"
                f"<p>{escape(answer).replace(chr(10), '<br>')}</p>"
                "</article>"
            )

    generated_at = datetime.now(UTC).strftime("%d %b %Y, %H:%M UTC")
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Cloud Cost Optimiser — {escape(dashboard['scope']['resource_group'])}</title>
<style>
  :root {{ color:#171513; background:#f8e4d3; font-family:Inter,Arial,sans-serif; }}
  * {{ box-sizing:border-box; }} body {{ margin:0; }} main {{ max-width:1200px; margin:auto; padding:42px 28px 72px; }}
  header {{ padding:38px; color:#fff8f2; background:#171513; }} .eyebrow {{ margin:0 0 10px; font-size:11px; font-weight:800; letter-spacing:.14em; }}
  h1 {{ margin:0; font-size:48px; letter-spacing:-.06em; }} h2 {{ margin:0; font-size:25px; letter-spacing:-.04em; }} h3 {{ margin:0 0 12px; font-size:20px; }}
  .scope {{ color:#d7c5b8; margin:14px 0 0; }} .grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; margin:22px 0; background:#171513; border:1px solid #171513; }}
  .card {{ min-height:128px; padding:18px; background:#fff8f2; }} .card strong {{ display:block; margin-top:30px; font-size:28px; }}
  .panel {{ margin-top:22px; padding:28px; border:1px solid #171513; background:#fff8f2; }} .chart {{ width:100%; height:180px; margin-top:20px; background:#171513; }} polyline {{ fill:none; stroke:#ff530b; stroke-width:3; vector-effect:non-scaling-stroke; }} .bar-row {{ display:grid; grid-template-columns:170px 1fr 95px; align-items:center; gap:12px; margin:14px 0; font-size:13px; }} .bar {{ height:9px; background:#ead9cd; }} .bar i {{ display:block; height:100%; background:#ff530b; }} .bar-row strong {{ text-align:right; font-size:12px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:18px; font-size:14px; }} th,td {{ padding:13px; border-bottom:1px solid #d9c7ba; vertical-align:top; text-align:left; }} th {{ font-size:11px; letter-spacing:.08em; text-transform:uppercase; }} small {{ color:#74665c; }}
  .pill {{ display:inline-block; padding:5px 8px; color:#852900; background:#fbd5c1; border-radius:20px; font-size:11px; font-weight:800; text-transform:uppercase; }} .assessment {{ margin-top:14px; padding:22px; border-left:5px solid #ff530b; background:#fff8f2; }} .assessment p:last-child {{ margin:0; line-height:1.6; white-space:normal; }} footer {{ margin-top:32px; color:#5f554e; font-size:12px; }}
  @media(max-width:700px) {{ main{{padding:18px}} h1{{font-size:36px}} .grid{{grid-template-columns:repeat(2,1fr)}} .panel{{overflow-x:auto}} }}
</style></head><body><main>
<header><p class='eyebrow'>CLOUD COST OPTIMISER · STAKEHOLDER REPORT</p><h1>Resource group overview</h1><p class='scope'>{escape(dashboard['scope']['resource_group'])} · Generated {generated_at}</p></header>
<section class='grid'><article class='card'><p class='eyebrow'>30-DAY COST</p><strong>{_money(summary['total_cost'], currency)}</strong></article><article class='card'><p class='eyebrow'>RESOURCES</p><strong>{summary['resource_count']}</strong></article><article class='card'><p class='eyebrow'>AI ANALYSES</p><strong>{len(analyses)}</strong></article><article class='card'><p class='eyebrow'>DATA SOURCE</p><strong>{escape(dashboard['source'].replace('_', ' ').title())}</strong></article></section>
<section class='panel'><p class='eyebrow'>SPEND VELOCITY</p><h2>Cost trend</h2><svg class='chart' viewBox='0 0 100 100' preserveAspectRatio='none' role='img' aria-label='Cost trend'><polyline points='{chart_points}'/></svg></section>
<section class='panel'><p class='eyebrow'>COST MIX</p><h2>Spend by resource type</h2>{cost_mix_bars or "<p>Cost distribution is unavailable for this scope.</p>"}</section>
<section class='panel'><p class='eyebrow'>RESOURCE INVENTORY</p><h2>Costs, consumption, and AI analysis status</h2><table><thead><tr><th>Resource</th><th>30-day cost</th><th>Performance / consumption</th><th>Optimization signal</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><p class='eyebrow'>GENERATED RECOMMENDATIONS</p><h2>AI responses</h2>{''.join(assessment_sections) or "<p>No AI recommendations have been generated yet. Use Analyse all resources or Suggest technique, then download the report again.</p>"}</section>
<footer>Directional guidance only. Validate owner approval, performance impact, operational dependencies, and Azure billing data before making any change.</footer>
</main></body></html>"""
