"""Interactive viewer for timestamped API evaluation runs."""

import json
from pathlib import Path

import pandas as pd
import streamlit as st


RESULTS_DIR = Path(__file__).with_name("results")
METRICS = {
    "context_precision": "Context Precision",
    "context_recall": "Context Recall",
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "answer_correctness": "Answer Correctness",
}


def display_decimal(value, places: int = 2):
    """Round only the UI representation; preserve full result precision on disk."""
    if isinstance(value, float):
        return round(value, places)
    return value


def display_safe(value, places: int = 2):
    """Apply UI rounding recursively before handing values to Streamlit."""
    if isinstance(value, dict):
        return {key: display_safe(item, places) for key, item in value.items()}
    if isinstance(value, list):
        return [display_safe(item, places) for item in value]
    return display_decimal(value, places)


def metric_display(record: dict, metric_name: str):
    if record.get("metric_applicability", {}).get(metric_name) == "not_applicable":
        return "N/A"
    return display_decimal(record["metrics"].get(metric_name))


def usage_display(record: dict, field: str):
    usage = record.get("application_usage")
    if not isinstance(usage, dict):
        return "No data received"
    value = usage.get(field)
    return value if value is not None else "No data received"


def cost_display(record: dict):
    cost = record.get("application_cost")
    if not isinstance(cost, dict):
        return "No data received"
    value = cost.get("provider_inference_cost")
    if value is None:
        return "N/A"
    return f"${value:.4f}"

st.set_page_config(page_title="RAGAS Evaluation Dashboard", page_icon="🧪", layout="wide")
st.title("🧪 RAGAS Evaluation Dashboard")
st.caption("Retrieval quality, generation quality, deterministic safety checks, and Gemini judge assessments.")


@st.cache_data
def load_run(run_id: str, modified_time: float) -> tuple[dict, list[dict]]:
    del modified_time
    run_dir = RESULTS_DIR / run_id
    return (
        json.loads((run_dir / "summary.json").read_text(encoding="utf-8")),
        json.loads((run_dir / "cases.json").read_text(encoding="utf-8")),
    )


run_dirs = sorted(
    (path for path in RESULTS_DIR.glob("*") if (path / "summary.json").exists()),
    key=lambda path: path.name,
    reverse=True,
) if RESULTS_DIR.exists() else []
if not run_dirs:
    st.info("No timestamped evaluation runs yet. Run `.venv/bin/python -m evals.runners.run_api_evaluation` first.")
    st.stop()

if st.button("Refresh runs"):
    st.cache_data.clear()
    st.rerun()

run_id = st.selectbox("Evaluation run", [path.name for path in run_dirs])
run_dir = RESULTS_DIR / run_id
summary, records = load_run(run_id, (run_dir / "cases.json").stat().st_mtime)

cards = st.columns(4)
cards[0].metric("Test cases", summary["case_count"])
cards[1].metric("Deterministic passes", f"{summary['deterministic_passes']}/{summary['case_count']}")
cards[2].metric("Avg. context precision", "—" if summary["metrics"]["context_precision"] is None else f"{summary['metrics']['context_precision']:.2f}")
cards[3].metric("Avg. faithfulness", "—" if summary["metrics"]["faithfulness"] is None else f"{summary['metrics']['faithfulness']:.2f}")
st.caption(f"Judge: {summary['evaluator_provider']} / {summary['evaluator_model']} · Run: {summary['run_id']}")

usage_summary = summary.get("application_usage", {})
st.subheader("Application usage and cost")
usage_cards = st.columns(5)
usage_cards[0].metric("Application models", ", ".join(usage_summary.get("models", [])) or "No data received")
usage_cards[1].metric("Input tokens", usage_summary.get("input_tokens") if usage_summary.get("input_tokens") is not None else "No data received")
usage_cards[2].metric("Output tokens", usage_summary.get("output_tokens") if usage_summary.get("output_tokens") is not None else "No data received")
usage_cards[3].metric("Total tokens", usage_summary.get("total_tokens") if usage_summary.get("total_tokens") is not None else "No data received")
total_cost = usage_summary.get("provider_inference_cost")
usage_cards[4].metric("Provider inference cost", f"${total_cost:.4f}" if total_cost is not None else "N/A")
if usage_summary:
    st.caption(
        f"Telemetry received for {usage_summary.get('telemetry_received_cases', 0)}/"
        f"{usage_summary.get('case_count', summary['case_count'])} cases. "
        "RAGAS/Judge tokens and costs are excluded."
    )
else:
    st.info("No application usage telemetry received for this historical run.")

frame = pd.DataFrame({
    "Case": [record["id"] for record in records],
    "Deterministic": [record["deterministic"]["status"] for record in records],
    "Judge verdict": [record["judge_assessment"]["status"] for record in records],
    **{label: [metric_display(record, name) for record in records] for name, label in METRICS.items()},
    "Model": [usage_display(record, "model") for record in records],
    "Deployment": [usage_display(record, "deployment") for record in records],
    "Input tokens": [usage_display(record, "input_tokens") for record in records],
    "Output tokens": [usage_display(record, "output_tokens") for record in records],
    "Total tokens": [usage_display(record, "total_tokens") for record in records],
    "LLM calls": [usage_display(record, "generation_calls") for record in records],
    "App cost": [cost_display(record) for record in records],
    "Latency (ms)": [record["latency_ms"] for record in records],
})
status_filter = st.multiselect("Filter deterministic status", ["pass", "fail"], default=["pass", "fail"])
st.dataframe(frame[frame["Deterministic"].isin(status_filter)], use_container_width=True, hide_index=True)

case_id = st.selectbox("Inspect a test case", frame["Case"].tolist())
record = next(item for item in records if item["id"] == case_id)
assessment = record["judge_assessment"]
left, right = st.columns(2)
with left:
    st.subheader("Question and response")
    st.markdown("**Question**")
    st.write(record["question"])
    st.markdown("**System answer**")
    st.write(record["answer"])
    st.markdown("**Reference answer**")
    st.write(record["reference_answer"])
with right:
    st.subheader("Judge assessment")
    st.metric("Verdict", assessment["status"].replace("_", " ").title())
    st.markdown("**Rationale**")
    st.write(assessment["rationale"])
    st.markdown("**Evidence used**")
    st.write(assessment["evidence_used"] or "None reported.")
    st.markdown("**Issues found**")
    st.write(assessment["issues"] or "None reported.")

st.subheader("Metric scores")
st.dataframe(pd.DataFrame({"Metric": list(METRICS.values()), "Score": [metric_display(record, name) for name in METRICS]}), use_container_width=True, hide_index=True)
if record.get("metric_errors"):
    st.warning("One or more metrics could not be calculated for this case.")
    st.json(record["metric_errors"])
st.subheader("Application usage and cost")
usage = record.get("application_usage")
cost = record.get("application_cost")
if not isinstance(usage, dict):
    st.info("No application usage telemetry received from the application for this case.")
else:
    st.json(display_safe(usage))
    if usage.get("message"):
        st.caption(usage["message"])
if not isinstance(cost, dict):
    st.info("No cost calculation is available because application telemetry was not received.")
else:
    st.json(display_safe(cost, places=4))
    if cost.get("status") == "local_model_no_provider_charge":
        st.caption("Provider cost is $0.00 for local inference. Local hardware and electricity costs are not calculated.")
    elif cost.get("status") == "pricing_unavailable":
        st.warning(cost.get("message", "Pricing unavailable."))
with st.expander("Deterministic checks and citations"):
    st.json(display_safe({"failures": record["deterministic"]["failures"], "citations": record["citations"]}))
with st.expander("Application scope"):
    st.json(display_safe({
        "scope": record.get("scope", {}),
        "scoped_inventory": record.get("scoped_inventory", []),
        "metric_applicability": record.get("metric_applicability", {}),
    }))
with st.expander("Retrieved contexts"):
    for index, context in enumerate(record["retrieved_contexts"], start=1):
        st.markdown(f"**Context {index}**")
        st.text(context)
with st.expander("Raw API retrieval trace"):
    st.json(display_safe(record["retrieval_trace"]))
with st.expander("Raw result record"):
    st.json(display_safe(record))

st.download_button("Download run summary", (run_dir / "summary.json").read_bytes(), file_name=f"{run_id}-summary.json", mime="application/json")
st.download_button("Download case results", (run_dir / "cases.json").read_bytes(), file_name=f"{run_id}-cases.json", mime="application/json")
