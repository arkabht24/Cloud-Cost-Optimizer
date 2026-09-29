"""RAGAS quality evaluation of the current API through the installed utility."""

import os
from pathlib import Path

from rag_api_eval import evaluate_rag


ROOT = Path(__file__).resolve().parent

summary = evaluate_rag(
    api_config={"url": os.getenv("RAG_UNDER_TEST_URL", "http://127.0.0.1:8000/v1/analyses"), "timeout_seconds": 90},
    dataset=ROOT / "azure_cost_smoke.jsonl",
    request_mapper={"body_template": {
        "question": "{{ question }}", "resource_group": "demo-cost-lab", "include_trace": True,
    }},
    response_mapper={
        "answer_path": "$.answer",
        "retrieved_contexts_path": "$.trace.retrieved_contexts[*].text",
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
    metrics_config={"groups": ["retrieval", "generation"], "metrics": [
        "context_precision", "context_recall", "faithfulness",
        "answer_relevancy", "answer_correctness",
    ], "thresholds": {
        "context_precision": 0.80,
        "context_recall": 0.80,
        "faithfulness": 0.75,
        "answer_relevancy": 0.75,
        "answer_correctness": 0.70,
    }},
    judge_config={"provider": "gemini", "model": "gemini-3.6-flash", "api_key_env": "GOOGLE_API_KEY", "concurrency": 1},
    pricing_config={"catalog": {
        "gemini": {
            "gemini-3.6-flash": {
                "tier": "paid",
                "currency": "USD",
                "input_per_million_tokens": 0.75,
                "output_per_million_tokens": 3.75,
                "source_url": "https://ai.google.dev/gemini-api/docs/pricing",
                "verified_at": "2026-09-25",
            }
        }
    }},
    reporting_config={"output_dir": "rag_eval_results"},
)

print(f"Saved RAGAS report: {summary['run_dir']}")
