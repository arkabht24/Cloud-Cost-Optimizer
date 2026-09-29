"""Run local Ragas checks against the trace-enabled Azure Cost Insight API.

Start the API first with ``uvicorn api:app``. The evaluator is
configured entirely through RAGAS_EVALUATOR_* environment variables.
"""

import json
import math
import os
import sys
import types
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Ragas 0.4 imports this legacy LangChain module even when Vertex AI is not
# used. New LangChain Community releases removed the module. Alias it to the
# installed Gemini chat integration before importing Ragas; the judge below
# uses Gemini directly and does not use Vertex AI.
try:
    from langchain_community.chat_models.vertexai import ChatVertexAI
except ModuleNotFoundError:
    from langchain_google_genai import ChatGoogleGenerativeAI

    vertex_module = types.ModuleType("langchain_community.chat_models.vertexai")
    vertex_module.ChatVertexAI = ChatGoogleGenerativeAI
    sys.modules[vertex_module.__name__] = vertex_module

from langchain_google_genai import ChatGoogleGenerativeAI
import instructor
from instructor import Mode
from openai import OpenAI
from ragas import EvaluationDataset, SingleTurnSample, evaluate
from ragas.llms import llm_factory
from ragas.metrics import Faithfulness

from config.settings import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GEMINI_MODEL,
    GEMINI_OPENAI_BASE_URL,
    GOOGLE_API_KEY,
    OLLAMA_BASE_URL,
    RAGAS_API_BASE_URL,
    RAGAS_EVALUATOR_MODEL,
    RAGAS_EVALUATOR_PROVIDER,
    RAGAS_MAX_CASES,
    RAGAS_MAX_RETRIES,
    RAGAS_REQUEST_TIMEOUT,
)


CASES_PATH = Path(__file__).with_name("baseline_cases.json")
RESULTS_PATH = Path(__file__).with_name("results.json")


def call_analysis_api(question: str) -> dict:
    payload = json.dumps({
        "question": question,
        "resource_group": "demo-cost-lab",
        "include_trace": True,
    }).encode("utf-8")
    request = Request(
        f"{RAGAS_API_BASE_URL}/v1/analyses",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        # Keep the caller bounded by the same timeout used for a judge request.
        # The API also bounds its Ollama call, so a failed generation becomes a
        # case-level error instead of stalling the complete suite.
        with urlopen(request, timeout=RAGAS_REQUEST_TIMEOUT + 10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"API returned HTTP {exc.code}: {exc.read().decode('utf-8')}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Cannot reach {RAGAS_API_BASE_URL}. Start the API with: "
            "uvicorn api:app"
        ) from exc


def deterministic_checks(case: dict, answer: str, citations: list[dict]) -> list[str]:
    """Keep deterministic checks beside Ragas to catch safety-specific failures."""
    answer_lower = answer.lower()
    failures = []
    for text in case["must_contain"]:
        if text.lower() not in answer_lower:
            failures.append(f"missing required text: {text}")
    for text in case["must_not_contain"]:
        if text.lower() in answer_lower:
            failures.append(f"contains prohibited text: {text}")
    source_names = {Path(citation.get("source") or "").name for citation in citations}
    for expected_source in case["expected_sources"]:
        if expected_source not in source_names:
            failures.append(f"missing expected source: {expected_source}")
    return failures


def response_text(content) -> str:
    """Extract text from Gemini's string or structured-content response."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block if isinstance(block, str) else block.get("text", "")
            for block in content
            if isinstance(block, (str, dict))
        )
    return str(content)


def parse_json_object(value: str) -> dict:
    """Accept a plain JSON response or one wrapped in a Markdown code fence."""
    cleaned = value.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in judge response")
    return json.loads(cleaned[start : end + 1])


def build_gemini_judge():
    if not GOOGLE_API_KEY:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add a valid Gemini API key to .env "
            "before running Ragas."
        )
    return ChatGoogleGenerativeAI(
        google_api_key=GOOGLE_API_KEY,
        model=RAGAS_EVALUATOR_MODEL or GEMINI_MODEL,
        temperature=0,
        request_timeout=RAGAS_REQUEST_TIMEOUT,
        retries=RAGAS_MAX_RETRIES,
    )


def judge_assessment(
    judge,
    case: dict,
    answer: str,
    contexts: list[str],
    failures: list[str],
    *,
    scope: dict | None = None,
    inventory: list[dict] | None = None,
) -> dict:
    """Return an auditable verdict, never a hidden chain-of-thought trace."""
    if judge is None:
        return {
            "status": "not_available",
            "rationale": "Detailed rationale is available for the Gemini evaluator.",
            "evidence_used": [],
            "issues": [],
        }

    prompt = """You are evaluating a RAG system response. Give a concise, evidence-based assessment.
Do not provide private reasoning or chain-of-thought. Return only a JSON object with this schema:
{{
  "status": "pass" | "fail" | "needs_review",
  "rationale": "one concise, evidence-based explanation (maximum 80 words)",
  "evidence_used": ["up to three short facts from the supplied contexts"],
  "issues": ["specific unsupported, unsafe, or incomplete claims"]
}}

Question:
{question}

Reference answer:
{reference}

System answer:
{answer}

Retrieved contexts:
{contexts}

Scope metadata:
{scope}

Relevant inventory resources:
{inventory}

Deterministic check failures:
{failures}
""".format(
        question=case["question"],
        reference=case["reference_answer"],
        answer=answer,
        contexts=json.dumps(contexts, ensure_ascii=False),
        scope=json.dumps(scope or {}, ensure_ascii=False),
        inventory=json.dumps(inventory or [], ensure_ascii=False),
        failures=json.dumps(failures),
    )
    try:
        result = parse_json_object(response_text(judge.invoke(prompt).content))
        status = result.get("status", "needs_review")
        if status not in {"pass", "fail", "needs_review"}:
            status = "needs_review"
        return {
            "status": status,
            "rationale": str(result.get("rationale", "No rationale returned.")).strip(),
            "evidence_used": [str(item) for item in result.get("evidence_used", [])][:3],
            "issues": [str(item) for item in result.get("issues", [])],
        }
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        return {
            "status": "needs_review",
            "rationale": "The judge returned an unreadable structured assessment.",
            "evidence_used": [],
            "issues": [f"Judge output could not be parsed: {exc}"],
        }


def build_evaluator_llm():
    """Build the judge separately from the application's generation model."""
    if RAGAS_EVALUATOR_PROVIDER == "groq":
        api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to .env before running Ragas."
            )
        client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
    elif RAGAS_EVALUATOR_PROVIDER == "gemini":
        if not GOOGLE_API_KEY:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Add a valid Gemini API key to .env "
                "before running Ragas."
            )
        return llm_factory(
            RAGAS_EVALUATOR_MODEL or GEMINI_MODEL,
            provider="google",
            client=instructor.from_openai(
                OpenAI(
                    api_key=GOOGLE_API_KEY,
                    base_url=GEMINI_OPENAI_BASE_URL,
                    timeout=RAGAS_REQUEST_TIMEOUT,
                    max_retries=RAGAS_MAX_RETRIES,
                ),
                mode=Mode.JSON,
            ),
            adapter="litellm",
            temperature=0,
        )
    elif RAGAS_EVALUATOR_PROVIDER == "ollama":
        client = OpenAI(api_key="ollama", base_url=f"{OLLAMA_BASE_URL}/v1")
    else:
        raise RuntimeError(
            "Unsupported RAGAS_EVALUATOR_PROVIDER "
            f"{RAGAS_EVALUATOR_PROVIDER!r}. Use 'gemini', 'groq', or 'ollama'."
        )

    return llm_factory(
        RAGAS_EVALUATOR_MODEL,
        provider="openai",
        client=client,
        temperature=0,
        system_prompt=(
            "You are a strict RAG evaluator. Judge only against the supplied "
            "inventory, retrieved evidence, and reference answer."
        ),
    )


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    if RAGAS_MAX_CASES > 0:
        cases = cases[:RAGAS_MAX_CASES]
    if not cases:
        raise RuntimeError("No evaluation cases selected. Set RAGAS_MAX_CASES to a positive number.")
    print(f"Running {len(cases)} RAGAS case(s) with {RAGAS_EVALUATOR_PROVIDER}.")
    records = []
    ragas_samples = []
    faithfulness_indexes = []
    evaluator_llm = build_evaluator_llm()
    rationale_judge = build_gemini_judge() if RAGAS_EVALUATOR_PROVIDER == "gemini" else None

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] Generating answer and judge assessment: {case['id']}")
        response = call_analysis_api(case["question"])
        answer = response["answer"]
        contexts = [item["text"] for item in response["trace"]["retrieved_contexts"]]
        scope = response.get("scope", response["trace"].get("scope", {}))
        matched_names = set(scope.get("matched_resources", []))
        inventory = [
            resource
            for items in response["trace"]["resources"].values()
            for resource in items
            if resource.get("name") in matched_names
        ]
        failures = deterministic_checks(case, answer, response["citations"])
        assessment = judge_assessment(
            rationale_judge,
            case,
            answer,
            contexts,
            failures,
            scope=scope,
            inventory=inventory,
        )
        records.append({
            "id": case["id"],
            "question": case["question"],
            "request_id": response["request_id"],
            "expected_baseline": case["expected_baseline"],
            "deterministic_status": "pass" if not failures else "fail",
            "deterministic_failures": failures,
            "reference_answer": case["reference_answer"],
            "answer": answer,
            "citations": response["citations"],
            "retrieved_contexts": contexts,
            "scope": scope,
            "scoped_inventory": inventory,
            "faithfulness_applicability": "applicable" if contexts and scope.get("status") != "unknown_named" else "not_applicable",
            "judge_assessment": assessment,
            "latency_ms": response["meta"]["latency_ms"],
        })
        if contexts and scope.get("status") != "unknown_named":
            faithfulness_indexes.append(index - 1)
            ragas_samples.append(SingleTurnSample(
                user_input=case["question"],
                response=answer,
                retrieved_contexts=contexts,
                reference=case["reference_answer"],
            ))

    ragas_rows = []
    if ragas_samples:
        evaluation = evaluate(
            EvaluationDataset(samples=ragas_samples),
            metrics=[Faithfulness(llm=evaluator_llm)],
        )
        ragas_rows = evaluation.to_pandas().to_dict(orient="records")
    faithfulness_by_index = dict(zip(faithfulness_indexes, ragas_rows))
    for index, record in enumerate(records):
        record["faithfulness"] = faithfulness_by_index.get(index, {}).get("faithfulness")

    unavailable_scores = sum(
        score is None or (isinstance(score, float) and math.isnan(score))
        for score in (record["faithfulness"] for record in records)
    )
    if unavailable_scores:
        print(
            f"Warning: {unavailable_scores} Faithfulness score(s) were unavailable. "
            "Check the Gemini quota/rate-limit message above and retry after it resets."
        )

    output = {
        "evaluator_provider": RAGAS_EVALUATOR_PROVIDER,
        "evaluator_model": RAGAS_EVALUATOR_MODEL,
        "ragas": ragas_rows,
        "deterministic_checks": records,
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Saved results to {RESULTS_PATH}")
    for record in records:
        print(f"{record['id']}: {record['deterministic_status']}")
    return 0


if __name__ == "__main__":
    # Backward-compatible entry point for the layered API evaluation runner.
    from evals.runners.run_api_evaluation import main as run_api_evaluation

    sys.exit(run_api_evaluation())
