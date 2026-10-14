"""Run the PII smoke evaluation against a short-lived local API server."""

from __future__ import annotations

import runpy
import subprocess
import sys
import time
import urllib.request
from copy import deepcopy
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
SERVER = [str(ROOT / ".venv/bin/python"), "-m", "uvicorn", "api:app", "--host", "127.0.0.1", "--port", "8000"]


def wait_for_api(timeout_seconds: int = 45) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("The local API did not become healthy within 45 seconds.")


def collect_api_responses() -> list[dict]:
    """Call the real API before running memory-intensive RAGAS work."""
    cases = [
        __import__("json").loads(line)
        for line in (ROOT / "utility_integration_test/azure_cost_smoke.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    responses = []
    for case in cases:
        response = requests.post(
            "http://127.0.0.1:8000/v1/analyses",
            json={
                "question": case["question"],
                "resource_group": "demo-cost-lab",
                "include_trace": True,
            },
            timeout=120,
        )
        response.raise_for_status()
        responses.append(response.json())
    return responses


def main() -> None:
    server = subprocess.Popen(SERVER, cwd=ROOT)
    try:
        wait_for_api()
        responses = collect_api_responses()
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)

    # The real API is now stopped. Feed its already-collected responses through
    # the installed package so RAGAS and the Judge do not compete with the API
    # process for local model resources.
    import rag_api_eval.runner as runner

    original_call_api = runner.call_api
    queued = iter(responses)
    runner.call_api = lambda *_args, **_kwargs: deepcopy(next(queued))
    try:
        runpy.run_path(str(ROOT / "utility_integration_test/run_utility_evaluation.py"), run_name="__main__")
    finally:
        runner.call_api = original_call_api


if __name__ == "__main__":
    main()
