"""Local HTTP API for the Azure Cost Insight RAG service."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config.settings import ALLOW_TRACE_RESPONSE
from rag.service import analyze_resources

app = FastAPI(title="Azure Cost Insight API", version="1.0.0")


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4_000)
    resource_group: str = Field(default="demo-cost-lab", min_length=1, max_length=256)
    subscription: str | None = Field(default=None, max_length=256)
    include_trace: bool = False


def problem_response(status: int, title: str, detail: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"https://azure-cost-insight.local/problems/{title.lower().replace(' ', '-')}",
            "title": title,
            "status": status,
            "detail": detail,
            "instance": str(request.url.path),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return problem_response(exc.status_code, "Request rejected", str(exc.detail), request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/analyses")
def create_analysis(payload: AnalysisRequest, request: Request) -> dict[str, Any]:
    if payload.include_trace and not ALLOW_TRACE_RESPONSE:
        raise HTTPException(status_code=403, detail="Trace responses are disabled.")

    request_id = f"req_{uuid4().hex}"
    try:
        result = analyze_resources(
            question=payload.question,
            resource_group=payload.resource_group,
            subscription=payload.subscription,
        )
    except Exception as exc:
        return problem_response(503, "Analysis unavailable", str(exc), request)

    response: dict[str, Any] = {
        "request_id": request_id,
        "answer": result["answer"],
        "citations": [
            {
                "id": context["id"],
                "source": context["source"],
                "page": context["page"],
                "score": context["score"],
            }
            for context in result["retrieved_contexts"]
        ],
        "scope": result["scope"],
        "decision": result["decision"],
        "meta": result["meta"],
        # Aggregate operational telemetry only. It deliberately omits prompts,
        # contexts, provider payloads, credentials, and evaluator/Judge usage.
        "application_usage": result["application_usage"],
    }
    if payload.include_trace:
        response["trace"] = {
            "question": result["question"],
            "resource_group": result["resource_group"],
            "resources": result["resources"],
            "scope": result["scope"],
            "decision": result["decision"],
            "retrieved_contexts": result["retrieved_contexts"],
            "retrieval_quality": result["retrieval_quality"],
            "prompt": result["prompt"],
        }
    return response
