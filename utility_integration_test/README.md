# Utility integration test

This folder validates `rag-api-eval` against the current FastAPI contract as a
black-box client. It maps the request body, answer, trace contexts, citations,
and optional application telemetry without importing the current RAG chain.

Run the API in one terminal:

```bash
zsh run_api.sh
```

Then run:

```bash
.venv/bin/python utility_integration_test/run_utility_evaluation.py
```

View the generated report:

```bash
rag-eval
```
