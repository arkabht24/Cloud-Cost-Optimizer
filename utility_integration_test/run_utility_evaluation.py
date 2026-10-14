"""Black-box smoke evaluation of this project's API through rag-api-eval."""

from pathlib import Path

from dotenv import load_dotenv
from rag_api_eval import evaluate_rag


ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")

summary = evaluate_rag(
    api_config={
        "url": "http://127.0.0.1:8000/v1/analyses",
        "method": "POST",
        "timeout_seconds": 90,
    },
    dataset=ROOT / "azure_cost_smoke.jsonl",
    request_mapper={
        "body_template": {
            "question": "{{ question }}",
            "resource_group": "demo-cost-lab",
            "include_trace": True,
        }
    },
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
    # Full retrieval, generation, security, and LLM Judge capability run.
    metrics_config={
        "groups": ["retrieval", "generation"],
        "metrics": [
            "context_precision",
            "context_recall",
            "faithfulness",
            "answer_relevancy",
            "answer_correctness",
        ],
        "thresholds": {"pii_leakage": 0},
    },
    judge_config={
        "provider": "gemini",
        "model": "gemini-3.6-flash",
        "api_key_env": "GOOGLE_API_KEY",
        "concurrency": 1,
        "timeout_seconds": 120,
        "generate_assessment": True,
    },
    pii_config={
        "enabled": True,
        "entity_types": ["email", "phone", "us_ssn", "payment_card"],
    },
    reporting_config={"output_dir": "rag_eval_results"},
)

print(f"Saved utility report: {summary['run_dir']}")
print(f"Successful cases: {summary['successful_cases']}/{summary['case_count']}")
