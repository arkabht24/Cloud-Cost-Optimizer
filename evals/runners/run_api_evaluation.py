"""Run retrieval, generation, and deterministic checks against the RAG API.

Usage: ``.venv/bin/python -m evals.runners.run_api_evaluation``.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

# Importing this module installs the compatibility shim required by Ragas 0.4.
from evals.run_ragas import (  # noqa: F401
    build_evaluator_llm,
    build_gemini_judge,
    call_analysis_api,
    judge_assessment,
)
from evals.suites import deterministic_checks, generation_metrics, retrieval_metrics
from evals.pricing import calculate_cost, write_pricing_snapshot
from evals.telemetry import collect_application_usage

from config.settings import (
    GEMINI_MODEL,
    GOOGLE_API_KEY,
    RAGAS_EVALUATOR_MODEL,
    RAGAS_EVALUATOR_PROVIDER,
    RAGAS_CORRECTNESS_MAX_RETRIES,
    RAGAS_CORRECTNESS_MAX_WAIT,
    RAGAS_CORRECTNESS_TIMEOUT,
    RAGAS_JUDGE_CONCURRENCY,
    RAGAS_MAX_CASES,
    RAGAS_MAX_RETRIES,
    RAGAS_MAX_WAIT,
    RAGAS_REQUEST_TIMEOUT,
)
from google import genai
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.embeddings import GoogleEmbeddings
from ragas.run_config import RunConfig


EVALS_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = EVALS_DIR / "datasets" / "azure_cost_v1.jsonl"
RESULTS_DIR = EVALS_DIR / "results"


class LegacyEmbeddingAdapter:
    """Bridge modern Ragas embeddings to legacy metrics expecting LangChain names."""

    def __init__(self, embeddings):
        self._embeddings = embeddings

    def __getattr__(self, name):
        return getattr(self._embeddings, name)

    def embed_query(self, text: str):
        return self._embeddings.embed_text(text)

    def embed_documents(self, texts: list[str]):
        return self._embeddings.embed_texts(texts)

    async def aembed_query(self, text: str):
        return await self._embeddings.aembed_text(text)

    async def aembed_documents(self, texts: list[str]):
        return await self._embeddings.aembed_texts(texts)


def load_cases() -> list[dict]:
    cases = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return cases[:RAGAS_MAX_CASES] if RAGAS_MAX_CASES > 0 else cases


def build_embeddings():
    if RAGAS_EVALUATOR_PROVIDER != "gemini":
        raise RuntimeError(
            "Answer Relevancy and Answer Correctness currently use Gemini embeddings. "
            "Set RAGAS_EVALUATOR_PROVIDER=gemini."
        )
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is required for Gemini embeddings.")
    return LegacyEmbeddingAdapter(
        GoogleEmbeddings(
            client=genai.Client(api_key=GOOGLE_API_KEY),
            model="gemini-embedding-001",
        )
    )


def json_safe(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def metric_rows(
    dataset: EvaluationDataset,
    metrics: list,
    *,
    timeout: int = RAGAS_REQUEST_TIMEOUT,
    max_retries: int = RAGAS_MAX_RETRIES,
    max_wait: int = RAGAS_MAX_WAIT,
    max_workers: int = RAGAS_JUDGE_CONCURRENCY,
    raise_exceptions: bool = False,
) -> list[dict]:
    run_config = RunConfig(
        timeout=timeout,
        max_retries=max_retries,
        max_wait=max_wait,
        max_workers=max_workers,
    )
    return evaluate(
        dataset,
        metrics=metrics,
        run_config=run_config,
        raise_exceptions=raise_exceptions,
    ).to_pandas().to_dict(orient="records")


def answer_correctness_rows(samples, evaluator_llm, embeddings) -> list[dict]:
    """Score correctness one case at a time and retain a usable failure reason."""
    rows = []
    for index, sample in enumerate(samples, start=1):
        print(f"  Answer Correctness {index}/{len(samples)}")
        metric = generation_metrics.build_answer_correctness(evaluator_llm, embeddings)
        try:
            result = metric_rows(
                EvaluationDataset([sample]),
                [metric],
                timeout=RAGAS_CORRECTNESS_TIMEOUT,
                max_retries=RAGAS_CORRECTNESS_MAX_RETRIES,
                max_wait=RAGAS_CORRECTNESS_MAX_WAIT,
                max_workers=1,
                raise_exceptions=True,
            )[0].get("answer_correctness")
            if result is None or (isinstance(result, float) and math.isnan(result)):
                raise RuntimeError("RAGAS returned no Answer Correctness score.")
            rows.append({"score": result, "error": None})
        except Exception as exc:
            rows.append({
                "score": None,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            })
    return rows


def scoped_inventory(resources: dict, scope: dict) -> list[dict]:
    """Return only the inventory objects the application allowed for this answer."""
    matched_names = set(scope.get("matched_resources", []))
    return [
        resource
        for items in resources.values()
        for resource in items
        if resource.get("name") in matched_names
    ]


def mean_score(records: list[dict], metric_name: str):
    values = [record["metrics"].get(metric_name) for record in records]
    numeric = [value for value in values if isinstance(value, (int, float)) and not math.isnan(value)]
    return round(sum(numeric) / len(numeric), 4) if numeric else None


def usage_summary(records: list[dict]) -> dict:
    """Aggregate application-only usage without conflating unavailable with zero."""
    def total(field: str):
        values = [record.get("application_usage", {}).get(field) for record in records]
        numeric = [value for value in values if isinstance(value, int)]
        return sum(numeric) if numeric else None

    costs = [record.get("application_cost", {}).get("provider_inference_cost") for record in records]
    numeric_costs = [value for value in costs if isinstance(value, (int, float))]
    models = sorted({
        usage.get("model")
        for usage in (record.get("application_usage", {}) for record in records)
        if usage.get("model")
    })
    return {
        "models": models,
        "input_tokens": total("input_tokens"),
        "output_tokens": total("output_tokens"),
        "total_tokens": total("total_tokens"),
        "provider_inference_cost": round(sum(numeric_costs), 8) if numeric_costs else None,
        "telemetry_received_cases": sum(
            record.get("application_usage", {}).get("status") == "available" for record in records
        ),
        "case_count": len(records),
    }


def main() -> int:
    cases = load_cases()
    if not cases:
        raise RuntimeError("The evaluation dataset contains no selected cases.")

    print(f"[1/7] Capturing {len(cases)} API artifacts")
    records = []
    samples = []
    rationale_judge = build_gemini_judge() if RAGAS_EVALUATOR_PROVIDER == "gemini" else None
    for index, case in enumerate(cases, start=1):
        print(f"  API {index}/{len(cases)}: {case['id']}")
        api_response = call_analysis_api(case["question"])
        application_usage = collect_application_usage(api_response)
        answer = api_response["answer"]
        contexts = [item["text"] for item in api_response["trace"]["retrieved_contexts"]]
        scope = api_response.get("scope", api_response["trace"].get("scope", {}))
        inventory = scoped_inventory(api_response["trace"]["resources"], scope)
        evidence_metrics_applicable = bool(contexts) and scope.get("status") != "unknown_named"
        failures = deterministic_checks.run(case, answer, api_response["citations"])
        records.append({
            "id": case["id"],
            "question": case["question"],
            "reference_answer": case["reference_answer"],
            "target_outcome": case["target_outcome"],
            "answer": answer,
            "citations": api_response["citations"],
            "retrieved_contexts": contexts,
            "retrieval_trace": api_response["trace"]["retrieved_contexts"],
            "scope": scope,
            "scoped_inventory": inventory,
            "latency_ms": api_response["meta"]["latency_ms"],
            "request_id": api_response["request_id"],
            "application_usage": application_usage,
            "application_cost": calculate_cost(application_usage),
            "deterministic": {
                "status": "pass" if not failures else "fail",
                "failures": failures,
            },
            "metric_errors": {},
            "metric_applicability": {
                "context_precision": "applicable" if evidence_metrics_applicable else "not_applicable",
                "context_recall": "applicable" if evidence_metrics_applicable else "not_applicable",
                "faithfulness": "applicable" if evidence_metrics_applicable else "not_applicable",
                "answer_relevancy": "applicable",
                "answer_correctness": "applicable",
            },
        })
        samples.append(SingleTurnSample(
            user_input=case["question"],
            response=answer,
            retrieved_contexts=contexts,
            reference=case["reference_answer"],
        ))

    evaluator_llm = build_evaluator_llm()
    evidence_indexes = [
        index
        for index, record in enumerate(records)
        if record["metric_applicability"]["faithfulness"] == "applicable"
    ]
    evidence_dataset = EvaluationDataset([samples[index] for index in evidence_indexes])
    all_dataset = EvaluationDataset(samples=samples)

    print("[2/7] Running retrieval metrics: Context Precision, Context Recall")
    retrieval_rows = (
        metric_rows(evidence_dataset, retrieval_metrics.build(evaluator_llm))
        if evidence_indexes else []
    )
    print("[3/7] Running generation metrics: Faithfulness, Answer Relevancy")
    faithfulness_rows = (
        metric_rows(evidence_dataset, [generation_metrics.build_faithfulness(evaluator_llm)])
        if evidence_indexes else []
    )
    relevancy_rows = metric_rows(
        all_dataset,
        [generation_metrics.build_answer_relevancy(evaluator_llm, build_embeddings())],
    )

    print("[4/7] Running Answer Correctness sequentially")
    correctness_rows = answer_correctness_rows(samples, evaluator_llm, build_embeddings())

    print("[5/7] Generating concise Gemini judge assessments")
    retrieval_by_index = dict(zip(evidence_indexes, retrieval_rows))
    faithfulness_by_index = dict(zip(evidence_indexes, faithfulness_rows))
    for index, (case, record, relevancy_row, correctness_row) in enumerate(zip(
        cases, records, relevancy_rows, correctness_rows
    )):
        retrieval_row = retrieval_by_index.get(index, {})
        faithfulness_row = faithfulness_by_index.get(index, {})
        record["metrics"] = {
            "context_precision": retrieval_row.get("context_precision"),
            "context_recall": retrieval_row.get("context_recall"),
            "faithfulness": faithfulness_row.get("faithfulness"),
            "answer_relevancy": relevancy_row.get("answer_relevancy"),
            "answer_correctness": correctness_row["score"],
        }
        if correctness_row["error"]:
            record["metric_errors"]["answer_correctness"] = correctness_row["error"]
        record["judge_assessment"] = judge_assessment(
            rationale_judge,
            case,
            record["answer"],
            record["retrieved_contexts"],
            record["deterministic"]["failures"],
            scope=record["scope"],
            inventory=record["scoped_inventory"],
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = RESULTS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)
    records = json_safe(records)
    summary = {
        "run_id": timestamp,
        "dataset": DATASET_PATH.name,
        "case_count": len(records),
        "evaluator_provider": RAGAS_EVALUATOR_PROVIDER,
        "evaluator_model": RAGAS_EVALUATOR_MODEL or GEMINI_MODEL,
        "metrics": {
            name: mean_score(records, name)
            for name in (
                "context_precision",
                "context_recall",
                "faithfulness",
                "answer_relevancy",
                "answer_correctness",
            )
        },
        "deterministic_passes": sum(record["deterministic"]["status"] == "pass" for record in records),
        "application_usage": usage_summary(records),
    }
    print("[6/7] Writing per-case results")
    (run_dir / "cases.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_pricing_snapshot(run_dir, records)
    print(f"[7/7] Saved evaluation run to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
