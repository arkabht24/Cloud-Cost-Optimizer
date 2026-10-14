"""Local HTTP API for the Azure Cost Insight RAG service."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from azure.dashboard_data import build_dashboard_data
from azure.resource_fetcher import list_resource_groups, list_subscriptions
from azure.stakeholder_report import render_stakeholder_report
from config.settings import ALLOW_TRACE_RESPONSE
from rag.chat_service import answer_finops_question
from rag.service import analyze_resources

app = FastAPI(title="Azure Cost Insight API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4_000)
    resource_group: str = Field(default="demo-cost-lab", min_length=1, max_length=256)
    subscription: str | None = Field(default=None, max_length=256)
    include_trace: bool = False


class OptimizationRequest(BaseModel):
    resource_group: str = Field(default="demo-cost-lab", min_length=1, max_length=256)
    subscription: str | None = Field(default=None, max_length=256)
    days: int = Field(default=30, ge=7, le=90)


class AssistantRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4_000)
    resource_group: str = Field(min_length=1, max_length=256)
    subscription: str | None = Field(default=None, max_length=256)
    context_resource: str | None = Field(default=None, max_length=512)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=8)


class StakeholderReportRequest(OptimizationRequest):
    """Client-held RAG responses to include in a downloadable report."""

    analyses: dict[str, dict[str, Any]] = Field(default_factory=dict)


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


@app.get("/v1/scopes")
def scopes(subscription: str | None = None) -> dict[str, Any]:
    """Discover Azure CLI scopes; demo remains available without Azure login."""
    try:
        subscriptions = list_subscriptions()
        resource_groups = list_resource_groups(subscription) if subscription else []
        return {
            "mode": "azure_cli",
            "subscriptions": subscriptions,
            "resource_groups": resource_groups,
            "demo_resource_group": "demo-cost-lab",
        }
    except Exception as exc:
        return {
            "mode": "demo_only",
            "subscriptions": [],
            "resource_groups": [],
            "demo_resource_group": "demo-cost-lab",
            "message": str(exc),
        }


@app.get("/v1/dashboard")
def dashboard(
    request: Request,
    resource_group: str = "demo-cost-lab",
    subscription: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    if not 7 <= days <= 90:
        raise HTTPException(status_code=422, detail="days must be between 7 and 90")
    try:
        return build_dashboard_data(resource_group, subscription, days)
    except Exception as exc:
        return problem_response(503, "Dashboard unavailable", str(exc), request)


def _optimization_question(resource: dict[str, Any]) -> str:
    """Build a cost-only prompt from normalized Azure facts for one resource."""
    facts = [
        f"resource type: {resource['type_label']}",
        f"SKU: {resource['sku'] or 'not reported'}",
        f"last 30-day cost: {resource['cost']['last_30_days'] if resource['cost']['last_30_days'] is not None else 'not available'} {resource['cost']['currency']}",
        *[f"{key}: {value}" for key, value in resource['performance']['metrics'].items()],
    ]
    return (
        f"Suggest cloud cost optimization techniques for {resource['name']}. "
        f"Use these Azure facts: {'; '.join(facts)}. "
        "Provide safe, non-destructive cost optimization guidance with evidence, conditions, and a next step."
    )


def _analyse_resource_optimization(resource: dict[str, Any], payload: OptimizationRequest) -> dict[str, Any]:
    return analyze_resources(
        _optimization_question(resource), payload.resource_group, payload.subscription
    )


@app.post("/v1/resources/{resource_name}/optimization")
def resource_optimization(
    resource_name: str,
    payload: OptimizationRequest,
    request: Request,
) -> dict[str, Any]:
    """Generate a non-destructive, evidence-grounded recommendation for one resource."""
    try:
        snapshot = build_dashboard_data(payload.resource_group, payload.subscription, payload.days)
        resource = next((item for item in snapshot["resources"] if item["name"].lower() == resource_name.lower()), None)
        if resource is None:
            raise HTTPException(status_code=404, detail="Resource was not found in the selected resource group.")
        analysis = _analyse_resource_optimization(resource, payload)
        return {"resource": resource, "dashboard_source": snapshot["source"], "analysis": analysis}
    except HTTPException:
        raise
    except Exception as exc:
        return problem_response(503, "Optimization unavailable", str(exc), request)


@app.post("/v1/assistant")
def assistant_chat(payload: AssistantRequest, request: Request) -> dict[str, Any]:
    """Return a conversational, fact-grounded FinOps answer for the UI chat."""
    try:
        return answer_finops_question(
            payload.question,
            payload.resource_group,
            payload.subscription,
            payload.context_resource,
            payload.history,
        )
    except Exception as exc:
        return problem_response(503, "Assistant unavailable", str(exc), request)


@app.post("/v1/dashboard/optimizations")
def dashboard_optimizations(payload: OptimizationRequest, request: Request) -> dict[str, Any]:
    """Generate one RAG assessment per resource, in a controlled sequential batch.

    Sequential execution avoids bursting a local model or provider quota.  A
    failed resource is recorded independently so successful assessments are
    still returned to the dashboard.
    """
    try:
        snapshot = build_dashboard_data(payload.resource_group, payload.subscription, payload.days)
        results: dict[str, dict[str, Any]] = {}
        for resource in snapshot["resources"]:
            try:
                results[resource["name"]] = _analyse_resource_optimization(resource, payload)
            except Exception as exc:
                results[resource["name"]] = {"answer": f"Analysis unavailable: {exc}", "decision": {"decision": "analysis_unavailable"}}
        return {"dashboard_source": snapshot["source"], "resource_count": len(snapshot["resources"]), "results": results}
    except Exception as exc:
        return problem_response(503, "Batch optimization unavailable", str(exc), request)


@app.post("/v1/dashboard/optimizations/stream")
def dashboard_optimizations_stream(payload: OptimizationRequest, request: Request) -> StreamingResponse:
    """Stream each completed RAG assessment to the UI as a Server-Sent Event.

    The model work remains sequential to protect local/provider capacity, but
    the browser receives and renders each resource outcome immediately rather
    than waiting for the complete resource-group batch.
    """
    try:
        snapshot = build_dashboard_data(payload.resource_group, payload.subscription, payload.days)
    except Exception as exc:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"]),
            media_type="text/event-stream",
        )

    def events():
        names = [resource["name"] for resource in snapshot["resources"]]
        yield f"data: {json.dumps({'type': 'started', 'resources': names})}\n\n"
        for resource in snapshot["resources"]:
            yield f"data: {json.dumps({'type': 'resource_started', 'resource': resource['name']})}\n\n"
            try:
                analysis = _analyse_resource_optimization(resource, payload)
                message = {"type": "resource_completed", "resource": resource["name"], "analysis": analysis}
            except Exception as exc:
                message = {
                    "type": "resource_failed",
                    "resource": resource["name"],
                    "analysis": {"answer": f"Analysis unavailable: {exc}", "decision": {"decision": "analysis_unavailable"}},
                }
            yield f"data: {json.dumps(message)}\n\n"
        yield f"data: {json.dumps({'type': 'completed'})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/v1/reports/resource-group", response_class=HTMLResponse)
def stakeholder_report(payload: StakeholderReportRequest, request: Request) -> HTMLResponse:
    """Return a self-contained, downloadable stakeholder-ready HTML report."""
    try:
        snapshot = build_dashboard_data(payload.resource_group, payload.subscription, payload.days)
        html = render_stakeholder_report(snapshot, payload.analyses)
        filename = f"cloud-cost-report-{payload.resource_group}.html".replace("/", "-")
        return HTMLResponse(html, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as exc:
        return problem_response(503, "Report unavailable", str(exc), request)


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
