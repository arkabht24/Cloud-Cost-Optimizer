"""HTTP client used by the Streamlit UI to call the deployed RAG API."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config.settings import ANALYSIS_API_BASE_URL, RAGAS_REQUEST_TIMEOUT


class AnalysisAPIError(RuntimeError):
    """A user-safe failure while communicating with the analysis API."""


def request_analysis(
    question: str,
    resource_group: str,
    subscription: str | None = None,
) -> dict[str, Any]:
    """Call the public analysis contract without requesting internal traces."""
    payload = json.dumps({
        "question": question,
        "resource_group": resource_group,
        "subscription": subscription,
        "include_trace": False,
    }).encode("utf-8")
    request = Request(
        f"{ANALYSIS_API_BASE_URL.rstrip('/')}/v1/analyses",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=RAGAS_REQUEST_TIMEOUT + 10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise AnalysisAPIError(f"Analysis API returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise AnalysisAPIError(
            "Analysis API is unavailable. Start it with `./run_api.sh` and try again."
        ) from exc
    except json.JSONDecodeError as exc:
        raise AnalysisAPIError("Analysis API returned an invalid response.") from exc

    if not isinstance(result, dict) or not isinstance(result.get("answer"), str):
        raise AnalysisAPIError("Analysis API returned no answer.")
    return result
