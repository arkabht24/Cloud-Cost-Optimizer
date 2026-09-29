"""Exercise retrieval-quality retries through the installed rag-api-eval package.

This is intentionally black-box: it calls the HTTP API only.  The assertions
inspect the API's opt-in trace saved by the package, rather than importing any
application modules.
"""

import json
import os
from pathlib import Path

from rag_api_eval import evaluate_rag


ROOT = Path(__file__).resolve().parent
summary = evaluate_rag(
    api_config={
        "url": os.getenv("RAG_UNDER_TEST_URL", "http://127.0.0.1:8002/v1/analyses"),
        "method": "POST",
        "timeout_seconds": 120,
    },
    dataset=ROOT / "retry_mechanism_cases.jsonl",
    request_mapper={"body_template": {
        "question": "{{ question }}", "resource_group": "demo-cost-lab", "include_trace": True,
    }},
    response_mapper={
        "answer_path": "$.answer",
        "retrieved_contexts_path": "$.trace.retrieved_contexts[*].text",
        "context_ids_path": "$.trace.retrieved_contexts[*].id",
        "citations_path": "$.citations[*]",
        "request_id_path": "$.request_id",
        "latency_ms_path": "$.meta.latency_ms",
        "provider_path": "$.application_usage.provider",
        "deployment_path": "$.application_usage.deployment",
        "model_path": "$.application_usage.model",
        "input_tokens_path": "$.application_usage.input_tokens",
        "output_tokens_path": "$.application_usage.output_tokens",
        "total_tokens_path": "$.application_usage.total_tokens",
        "generation_calls_path": "$.application_usage.generation_calls",
    },
    metrics_config={
        "groups": ["retrieval", "generation"],
        "metrics": [
            "context_precision", "context_recall", "faithfulness",
            "answer_relevancy", "answer_correctness",
        ],
    },
    judge_config={
        "provider": "gemini",
        "model": "gemini-3.6-flash",
        "api_key_env": "GOOGLE_API_KEY",
        "concurrency": 1,
        "timeout_seconds": 120,
        "generate_assessment": True,
    },
    reporting_config={"output_dir": "rag_eval_results"},
)

records = json.loads((Path(summary["run_dir"]) / "cases.json").read_text(encoding="utf-8"))
by_id = {record["id"]: record for record in records}


def strategies(case_id: str) -> list[str]:
    trace = by_id[case_id]["raw_api_response"]["trace"]
    return [attempt["strategy"] for attempt in trace["retrieval_quality"]["attempts"]]


assert strategies("healthy-removal-no-retry") == ["initial"]
assert strategies("healthy-rightsizing-no-retry") == ["initial"]
assert strategies("insufficient-evidence-retries-and-abstains") == [
    "initial", "expanded_candidate_rerank", "resource_focused_query_rewrite",
]
assert by_id["insufficient-evidence-retries-and-abstains"]["raw_api_response"]["scope"]["response_mode"] == "retrieval_quality_abstention"

print(f"Saved retry-mechanism report: {summary['run_dir']}")
for case_id in by_id:
    trace = by_id[case_id]["raw_api_response"]["trace"]
    quality = trace["retrieval_quality"]
    print(f"{case_id}: attempts={strategies(case_id)} quality_passed={quality['passed']} mode={trace['scope']['response_mode']}")
