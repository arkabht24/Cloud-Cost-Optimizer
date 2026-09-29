# Local Ragas Evaluation

This harness evaluates the trace-enabled local API against the synthetic FinOps corpus.

## Prerequisites

1. Configure the evaluator in `.env`. The current judge uses the existing Gemini API configuration:

   ```env
   RAGAS_EVALUATOR_PROVIDER=gemini
   RAGAS_EVALUATOR_MODEL=gemini-3.6-flash
   GOOGLE_API_KEY=your_valid_gemini_api_key
   ```

   The application itself continues to use Ollama. Do not commit the API key.
2. Start the API in another terminal:

   ```bash
   source .venv/bin/activate
   uvicorn api:app
   ```

3. Run the complete API evaluation suite:

   ```bash
   .venv/bin/python -m evals.runners.run_api_evaluation
   ```

Each run writes `cases.json` and `summary.json` to a timestamped directory under `evals/results/`. It combines deterministic safety checks with retrieval metrics (Context Precision, Context Recall) and generation metrics (Faithfulness, Answer Relevancy, Answer Correctness).

This is a black-box suite: every case has `target_outcome: "pass"`. Cases may use unsafe, adversarial, or unknown-resource questions, but a passing result always means the externally observable answer met its required behavior.

Metric calls use a bounded timeout, retry policy, and Gemini concurrency. Tune `RAGAS_REQUEST_TIMEOUT`, `RAGAS_MAX_RETRIES`, `RAGAS_MAX_WAIT`, and `RAGAS_JUDGE_CONCURRENCY` in `.env` if needed. Answer Correctness is run sequentially because it makes multiple dependent judge calls per case; its dedicated controls are `RAGAS_CORRECTNESS_TIMEOUT`, `RAGAS_CORRECTNESS_MAX_RETRIES`, and `RAGAS_CORRECTNESS_MAX_WAIT`.

Gemini evaluation uses Gemini's OpenAI-compatible endpoint with RAGAS's LiteLLM structured-output adapter, rather than the deprecated LangChain wrapper.

`RAGAS_MAX_CASES=0` runs the full dataset. Set a positive number to run only that many cases, for example:

```env
RAGAS_MAX_CASES=2
```

## View results interactively

After the suite completes, start the dashboard:

```bash
.venv/bin/streamlit run evals/dashboard.py
```

It includes the Ragas faithfulness score, deterministic pass/fail state, response and retrieved contexts, plus a concise Gemini judge rationale. The rationale is an evidence-based verdict and issue list; it intentionally does not expose hidden chain-of-thought.

## Use local Ollama instead

After the download completes, change one line in `.env`:

```env
RAGAS_EVALUATOR_PROVIDER=ollama
RAGAS_EVALUATOR_MODEL=qwen3:8b
```

No application code changes are needed. Ollama must be running and the selected
model must be installed locally.

## Use Groq instead

```env
RAGAS_EVALUATOR_PROVIDER=groq
RAGAS_EVALUATOR_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=your_groq_api_key
```
