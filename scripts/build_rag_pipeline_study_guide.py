"""Build a study guide for the current Azure Cost Insight RAG implementation."""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


OUT = Path("/Users/arkabhattacharyya/Documents/Azure_Cost_Insight_RAG_Study_Guide.docx")
NAVY = "17365D"
LIGHT_BLUE = "DCE6F1"
PALE_BLUE = "F4F8FC"
GRAY = "D9E2F3"
TEXT = RGBColor(0, 0, 0)


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_border(cell, color="D9D9D9"):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = qn(f"w:{edge}")
        node = borders.find(tag)
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "6")
        node.set(qn("w:color"), color)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    element = OxmlElement("w:tblHeader")
    element.set(qn("w:val"), "true")
    tr_pr.append(element)


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.add_run("Page ")
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    paragraph._p.append(fld)


def add_text(doc, text, style=None, bold_lead=None):
    p = doc.add_paragraph(style=style)
    if bold_lead and text.startswith(bold_lead):
        run = p.add_run(bold_lead)
        run.bold = True
        p.add_run(text[len(bold_lead):])
    else:
        p.add_run(text)
    return p


def add_bullets(doc, values):
    for value in values:
        doc.add_paragraph(value, style="List Bullet")


def add_code(doc, code):
    p = doc.add_paragraph(style="Code Block")
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(8)
    p.add_run(code)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    table.style = "Table Grid"
    header = table.rows[0]
    set_repeat_table_header(header)
    for i, value in enumerate(headers):
        cell = header.cells[i]
        shade(cell, NAVY)
        set_cell_border(cell)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell.text = value
        for run in cell.paragraphs[0].runs:
            run.font.color.rgb = RGBColor(255, 255, 255)
            run.bold = True
            run.font.size = Pt(9)
        if widths:
            cell.width = Inches(widths[i])
    for row_index, row_values in enumerate(rows):
        cells = table.add_row().cells
        for i, value in enumerate(row_values):
            cell = cells[i]
            shade(cell, "FFFFFF" if row_index % 2 == 0 else PALE_BLUE)
            set_cell_border(cell)
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            cell.text = value
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(2)
                for run in p.runs:
                    run.font.size = Pt(9)
            if widths:
                cell.width = Inches(widths[i])
    return table


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(16 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(6)
    return p


def add_flow(doc):
    rows = [
        ["1", "PDF evidence and Azure inventory", "data/pdfs and data/sample_azure_resources.json", "Knowledge and inventory inputs"],
        ["2", "Ingestion", "ingest.py and ingestion package", "Chunks, embeddings, Chroma collection, parents.json"],
        ["3", "API request", "POST /v1/analyses", "Validated question and resource scope"],
        ["4", "Retrieval and quality gate", "rag/retriever.py and rag/retrieval_quality.py", "Scoped contexts or safe abstention"],
        ["5", "Evidence plan and LLM", "rag/response_policy.py and rag/llm_client.py", "Structured decision and answer"],
        ["6", "UI and evaluation", "app.py and rag_api_eval", "User answer, telemetry, RAGAS report"],
    ]
    add_table(doc, ["Step", "Stage", "Main code", "Output"], rows, [0.45, 1.45, 2.65, 2.2])


def build_document():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = TEXT
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12
    for name, size in (("Title", 26), ("Subtitle", 13), ("Heading 1", 16), ("Heading 2", 12), ("Heading 3", 11)):
        style = styles[name]
        style.font.name = "Aptos Display" if name != "Normal" else "Aptos"
        style.font.size = Pt(size)
        style.font.color.rgb = TEXT
        style.font.bold = name != "Subtitle"
    # Word's built-in Title style can carry a blue bottom border. The guide
    # uses the required Title style but removes that inherited decoration.
    title_ppr = styles["Title"]._element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)
    code = styles.add_style("Code Block", WD_STYLE_TYPE.PARAGRAPH)
    code.font.name = "Menlo"
    code.font.size = Pt(8.5)
    code.font.color.rgb = TEXT
    code.paragraph_format.left_indent = Inches(0.18)
    code.paragraph_format.right_indent = Inches(0.1)
    code.paragraph_format.line_spacing = 1.0
    code.paragraph_format.space_after = Pt(5)
    code._element.get_or_add_pPr().append(OxmlElement("w:shd"))
    code._element.pPr[-1].set(qn("w:fill"), "F3F5F7")

    header = section.header.paragraphs[0]
    header.text = "Azure Cost Insight RAG Study Guide"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in header.runs:
        run.font.name = "Aptos"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(80, 80, 80)
    add_page_number(section.footer.paragraphs[0])

    # Cover page
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.add_run("Azure Cost Insight RAG Study Guide")
    sub = doc.add_paragraph(style="Subtitle")
    sub.add_run("From PDF ingestion and Chroma retrieval to guarded answer generation and evaluation")
    add_text(doc, "Purpose", style="Heading 1")
    add_text(doc, "This guide explains the working implementation in this project. It follows a question from the Streamlit interface through the FastAPI contract, inventory scope resolution, vector retrieval, deterministic retry checks, evidence planning, LLM generation, and evaluation. Use it as a study reference before changing the pipeline or designing RAGAS tests.")
    add_text(doc, "The central design decision", style="Heading 2")
    add_text(doc, "The application does not treat a high vector similarity score as permission to make a cost-changing recommendation. It first confirms the requested resource exists in the inventory, then requires resource-specific evidence appropriate to the requested action. If evidence remains incomplete after retrieval retries, it abstains without calling the generation model.")
    add_text(doc, "Current defaults", style="Heading 2")
    add_table(doc, ["Area", "Current implementation"], [
        ["Generation provider", "Gemini via LLM_PROVIDER=gemini and GEMINI_MODEL=gemini-3.6-flash"],
        ["Embedding model", "all-MiniLM-L6-v2 with normalized CPU embeddings"],
        ["Vector store", "Persistent Chroma collection plus parents.json for parent chunks"],
        ["API", "FastAPI POST /v1/analyses"],
        ["UI", "Streamlit calls the API instead of invoking the chain directly"],
        ["Offline evaluation", "rag-api-eval utility with RAGAS metrics and Gemini Judge"],
    ], [1.65, 5.1])

    add_heading(doc, "How to Read This Guide")
    add_text(doc, "Read Sections 1 through 6 in order for the complete execution path. Sections 7 through 10 explain reliability controls, API behavior, observability, evaluation, and the practical commands used to operate the system.")
    add_heading(doc, "Pipeline Map", level=2)
    add_flow(doc)
    add_heading(doc, "Project Map", level=2)
    add_table(doc, ["Path", "Role"], [
        ["data/pdfs", "Source PDF evidence embedded into Chroma"],
        ["data/sample_azure_resources.json", "Local Azure inventory fixture used when Azure CLI is not used"],
        ["ingestion", "PDF loading, parent child chunking, embeddings, Chroma persistence"],
        ["rag", "Retriever, quality gate, policy, model client, API client, service orchestration"],
        ["azure", "Inventory retrieval and normalized resource scope resolution"],
        ["api.py", "FastAPI request validation and response contract"],
        ["app.py", "Streamlit chat interface"],
        ["evals and utility_integration_test", "Datasets and black box evaluation scripts"],
    ], [2.5, 4.25])

    add_heading(doc, "1 Data Sources and Ingestion")
    add_text(doc, "The system uses two complementary sources. The Azure inventory identifies what resources exist. The PDFs provide decisions, utilization records, policies, exceptions, approvals, and safeguards. A good answer needs both: inventory scope prevents cross-resource claims, while PDF evidence supports the recommendation.")
    add_heading(doc, "Input Assets", level=2)
    add_bullets(doc, [
        "PDFs in data/pdfs contain cost optimization, decision-log, utilization, ownership, and exception evidence.",
        "data/sample_azure_resources.json contains normalized Azure-like resources for local development and tests.",
        "The ingestion pipeline treats PDF content as knowledge. It does not embed API keys, live Azure credentials, or evaluator prompts.",
    ])
    add_heading(doc, "Ingestion Entry Point", level=2)
    add_code(doc, "# ingest.py\nfrom ingestion.pdf_loader import load_pdfs, get_parent_child_chunks\nfrom ingestion.vector_store import store_chunks\n\ndocs = load_pdfs()\nparents, children = get_parent_child_chunks(docs)\nstore_chunks(parents, children)")
    add_heading(doc, "Parent Child Chunking", level=2)
    add_text(doc, "PyPDFLoader reads each PDF page. The loader first makes parent chunks of 1,000 characters with a 100-character overlap. It then makes child chunks of 200 characters with a 20-character overlap. Child chunks give Chroma finer retrieval targets. Parent chunks retain enough surrounding context for evidence planning and citations.")
    add_code(doc, "# ingestion/pdf_loader.py\nparent_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)\nchild_splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)\n\nfor parent in parents:\n    parent.metadata[\"evidence_role\"] = evidence_role(parent.page_content)\n    parent.metadata[\"resource_names\"] = resource_names(parent.page_content)")
    add_text(doc, "The parent metadata is useful for retrieval diagnostics, but it is not treated as decisive for named questions. A parent can mention several resources, so the quality gate now derives the role from the requested resource block inside that parent.")

    add_heading(doc, "2 Embeddings and Vector Persistence")
    add_text(doc, "The embedder uses the local all-MiniLM-L6-v2 sentence-transformer model on CPU. It uses local_files_only so API requests use the downloaded model rather than attempting network downloads. Normalized embeddings improve cosine-style comparison behavior.")
    add_code(doc, "# ingestion/embedder.py\nreturn HuggingFaceEmbeddings(\n    model_name=EMBEDDING_MODEL,\n    model_kwargs={\"device\": \"cpu\", \"local_files_only\": True},\n    encode_kwargs={\"normalize_embeddings\": True},\n)")
    add_heading(doc, "What Is Stored", level=2)
    add_table(doc, ["Storage", "Contents", "Why it exists"], [
        ["Chroma collection", "Embedded child chunks and their metadata", "Fast semantic candidate search"],
        ["chroma_db/parents.json", "Parent chunk text and metadata keyed by parent ID", "Restores broader context after a child hit"],
        ["PDF source field", "Path to originating PDF", "Citation and traceability"],
    ], [1.55, 2.85, 2.35])
    add_text(doc, "Re-running ingest.py replaces the Chroma collection rather than appending duplicates. Do this whenever PDFs or ingestion metadata change. Pure application logic fixes, such as exact resource matching, do not require re-embedding.")
    add_heading(doc, "Distance and Display Relevance", level=2)
    add_text(doc, "The retriever requests raw Chroma distances with similarity_search_with_score. It converts each non-negative distance to 1 divided by 1 plus distance for trace display. This yields a bounded diagnostic value without claiming it is a calibrated probability. Chroma ranking itself is preserved.")
    add_code(doc, "# ingestion/vector_store.py\nhits = db.similarity_search_with_score(query, k=top_k)\n...\nscore = round(1 / (1 + max(float(distance), 0.0)), 6)")

    add_heading(doc, "3 API Entry and Inventory Scope")
    add_text(doc, "The UI does not call the RAG chain directly. It sends an HTTP request to FastAPI. This gives the browser, Postman, and the black-box evaluator the same public contract.")
    add_code(doc, "POST /v1/analyses\n{\n  \"question\": \"Should we reduce capacity for analytics-vm-01 now?\",\n  \"resource_group\": \"demo-cost-lab\",\n  \"include_trace\": false\n}")
    add_heading(doc, "Request Validation", level=2)
    add_text(doc, "Pydantic requires question to be 3 to 4,000 characters. resource_group defaults to demo-cost-lab and is limited to 256 characters. include_trace is false by default. The API permits trace output only when ALLOW_TRACE_RESPONSE is enabled, because traces contain retrieved contexts and prompt content.")
    add_code(doc, "class AnalysisRequest(BaseModel):\n    question: str = Field(min_length=3, max_length=4_000)\n    resource_group: str = Field(default=\"demo-cost-lab\", min_length=1, max_length=256)\n    subscription: str | None = Field(default=None, max_length=256)\n    include_trace: bool = False")
    add_heading(doc, "Exact Scope Resolution", level=2)
    add_text(doc, "Before retrieval, resolve_resource_scope scans inventory resource names using a boundary-aware expression. analytics-vm-01 therefore matches that VM but not analytics-vm-01-data. If the user names an inventory-like resource that does not exist, the service returns an inventory abstention immediately. It does not query Chroma or call the LLM.")
    add_code(doc, "rf\"(?<![\\w-]){re.escape(resource_name.lower())}(?![\\w-])\"")
    add_text(doc, "This exact-name rule is used in scope resolution, reranking, quality checks, and evidence extraction. Keeping the rule shared prevents a correct scope from being undone later in the pipeline.")

    add_heading(doc, "4 Retrieval and Deterministic Retry Gate")
    add_text(doc, "retrieve_best_practice_contexts first asks Chroma for more candidates than the final top_k. It then performs deterministic resource-aware reranking. For a named question, it discards candidates that do not mention the requested resource with exact boundaries whenever scoped candidates are available.")
    add_code(doc, "# rag/retriever.py\ncandidates = query_vector_store_with_metadata(query, top_k=max(top_k * candidate_multiplier, top_k))\nscoped_candidates = [\n    context for context in contexts\n    if any(mentions_resource(context[\"text\"], name) for name in names)\n]\nreturn _rerank_for_resources(candidates, resource_names, top_k, query=query)")
    add_heading(doc, "Quality Rules", level=2)
    add_table(doc, ["Question type", "Minimum evidence required"], [
        ["Remove or delete", "A decision or exception record, plus utilization, policy, or exception safeguards"],
        ["Downsize or reduce capacity", "A decision or exception record and measured utilization evidence"],
        ["General review", "At least scoped contextual evidence; no action-specific role combination"],
    ], [2.0, 4.75])
    add_text(doc, "The assessment is deterministic. It does not invoke RAGAS, DeepEval, Gemini, or Ollama. It evaluates resource-specific blocks, reports matched sources and roles, and emits an explainable issues list.")
    add_heading(doc, "Retry Order", level=2)
    add_code(doc, "initial retrieval\n  └─ quality pass → build answer\n  └─ quality fail → expanded_candidate_rerank with a larger candidate pool\n       └─ quality pass → build answer\n       └─ quality fail → resource_focused_query_rewrite\n            └─ quality pass → build answer\n            └─ quality fail → retrieval_quality_abstention")
    add_text(doc, "The query rewrite retains the user question for generation. It changes only retrieval by asking for action-appropriate evidence, such as decision approval, utilization, retention, and rollback safeguards. If all attempts fail, generation_calls is zero.")

    add_heading(doc, "5 Evidence Planning and Answer Generation")
    add_text(doc, "After retrieval quality passes, extract_evidence_plan converts context into a model-independent plan. It identifies the action, selected evidence, mandatory conditions, and a conservative decision. This narrows the LLM's job: it turns an evidence plan into a structured response rather than deciding from unfiltered chunks.")
    add_heading(doc, "Resource Specific Blocks", level=2)
    add_code(doc, "# rag/resource_matching.py\ndef resource_blocks(text, allowed_names, inventory_names):\n    # Start at an exact allowed resource name.\n    # Close the block when another known inventory resource begins.\n    # Return only the requested resource's line groups.")
    add_text(doc, "For capacity questions, unnamed associated-disk sentences are excluded from VM evidence. This prevents disk hygiene or deletion facts from influencing a VM rightsizing decision.")
    add_heading(doc, "Structured Generation Contract", level=2)
    add_code(doc, "{\n  \"decision\": \"yes | no | approved_with_conditions | needs_review | insufficient_evidence\",\n  \"resource\": \"one exact allowed resource name\",\n  \"reason\": [\"one to three evidence-backed statements\"],\n  \"required_conditions\": [\"mandatory safeguards\"],\n  \"recommended_next_step\": \"one concise action\",\n  \"citation_ids\": [\"IDs from supplied evidence\"]\n}")
    add_text(doc, "The service validates the model JSON. It rejects an invalid decision, an out-of-scope resource, a contradiction of a required no or approved-with-conditions decision, missing reasons, missing mandatory conditions, or leakage of another inventory resource name.")
    add_heading(doc, "Generation Repair and Fallback", level=2)
    add_bullets(doc, [
        "Initial generation asks the configured provider for JSON only.",
        "If validation fails, build_repair_prompt asks the model to repair the draft against the same evidence plan.",
        "If repair still fails, fallback_answer returns a deterministic, evidence-grounded answer. This is safer than forwarding malformed model text.",
        "Before rendering, duplicate text is removed from reason when the same text is already present in required_conditions.",
    ])

    add_heading(doc, "6 Model Providers and Telemetry")
    add_text(doc, "rag/llm_client.py supports two application providers. Ollama runs locally. Gemini uses the configured Google API key. The service returns only aggregate application usage, never the prompt, key, or Judge usage in its normal response.")
    add_table(doc, ["Provider", "Configuration", "Deployment field", "Usage fields"], [
        ["Ollama", "LLM_PROVIDER=ollama and OLLAMA_MODEL", "local", "prompt_eval_count and eval_count"],
        ["Gemini", "LLM_PROVIDER=gemini, GEMINI_MODEL, GOOGLE_API_KEY", "api", "LangChain usage_metadata fields"],
    ], [1.0, 2.75, 1.1, 1.9])
    add_code(doc, "# rag/llm_client.py\nif LLM_PROVIDER == \"gemini\":\n    llm = ChatGoogleGenerativeAI(google_api_key=GOOGLE_API_KEY, model=GEMINI_MODEL)\n...\nreturn {\n  \"text\": response_text,\n  \"usage\": {\"provider\": provider, \"model\": model,\n              \"input_tokens\": input_tokens, \"output_tokens\": output_tokens}\n}")
    add_heading(doc, "Operational Telemetry", level=2)
    add_text(doc, "application_usage aggregates only generation calls made by the application. When a retrieval-quality abstention occurs, token counters are null and generation_calls is zero. The evaluator uses these values for application cost reporting; it keeps Judge costs separate.")
    add_heading(doc, "Retry Logging", level=2)
    add_text(doc, "The service writes retry diagnostics through uvicorn.error, so they appear in the API terminal. Logs include strategy, resource names, matching-context count, evidence roles, and issue messages. They deliberately exclude prompts, credentials, and full PDF content.")
    add_code(doc, "INFO  retrieval_quality strategy=initial passed=False resources=['analytics-vm-01'] ...\nINFO  retrieval_retry strategy=expanded_candidate_rerank resources=['analytics-vm-01']\nINFO  retrieval_quality strategy=expanded_candidate_rerank passed=True ...")

    add_heading(doc, "7 API Response and Streamlit Flow")
    add_text(doc, "The Streamlit UI calls rag.api_client.request_analysis. It sends include_trace=false. The user sees the answer while the API response also carries citations, scope, decision, latency, model information, and aggregate usage. The UI does not invoke retrieval or the LLM directly.")
    add_code(doc, "# rag/api_client.py\npayload = {\n  \"question\": question,\n  \"resource_group\": resource_group,\n  \"subscription\": subscription,\n  \"include_trace\": False,\n}\nPOST {ANALYSIS_API_BASE_URL}/v1/analyses")
    add_heading(doc, "Normal Response Shape", level=2)
    add_code(doc, "{\n  \"request_id\": \"req_...\",\n  \"answer\": \"Approved with conditions...\",\n  \"citations\": [{\"id\": \"4\", \"source\": \"...pdf\", \"page\": 0, \"score\": 0.94}],\n  \"scope\": {\"status\": \"matched\", \"matched_resources\": [\"analytics-vm-01\"]},\n  \"decision\": { ... },\n  \"meta\": {\"provider\": \"gemini\", \"latency_ms\": 1234},\n  \"application_usage\": {\"input_tokens\": 0, \"output_tokens\": 0, \"generation_calls\": 1}\n}")
    add_text(doc, "For controlled debugging, include_trace=true returns retrieved_contexts, retrieval_quality attempts, resource inventory, and the generation prompt. Do not enable traces for general users because this exposes internal evidence and prompt data.")
    add_heading(doc, "Failure Behavior", level=2)
    add_table(doc, ["Condition", "Response behavior"], [
        ["Unknown named resource", "Immediate inventory abstention; no Chroma retrieval and no LLM call"],
        ["Missing Chroma parent store", "Built-in cost guidance fallback is returned by the retriever"],
        ["Retrieval quality fails after retries", "Safe retrieval_quality_abstention; no generation call"],
        ["Provider or API exception", "HTTP 503 application/problem+json response"],
        ["Malformed LLM output", "One repair attempt, then deterministic evidence fallback"],
    ], [2.2, 4.55])

    add_heading(doc, "8 RAGAS and Black Box Evaluation")
    add_text(doc, "The application is evaluated as a black box through the separate rag-api-eval pip utility. The utility maps any project-specific request and response fields into a portable evaluation record. This project maps answer, retrieved contexts, citations, latency, provider, model, and application token counters from /v1/analyses.")
    add_heading(doc, "Metric Groups", level=2)
    add_table(doc, ["Group", "Metric", "What it checks"], [
        ["Retrieval", "Context Precision", "Whether retrieved contexts are relevant to the reference answer"],
        ["Retrieval", "Context Recall", "Whether contexts cover claims needed by the reference answer"],
        ["Generation", "Faithfulness", "Whether response claims are supported by retrieved contexts"],
        ["Generation", "Answer Relevancy", "Whether the answer addresses the question"],
        ["Generation", "Answer Correctness", "Semantic alignment with the reference answer"],
        ["Judge", "Gemini verdict", "An explainable pass or fail assessment with rationale and evidence used"],
    ], [1.0, 1.65, 4.1])
    add_text(doc, "RAGAS numeric metrics and the Judge verdict serve different purposes. A safe abstention can receive a positive Judge verdict because it reaches the right decision, while its answer relevancy or correctness score can be lower if the reference answer expects more specific facts.")
    add_heading(doc, "Retry Demonstration Case", level=2)
    add_code(doc, "Question\nShould we reduce capacity for analytics-vm-01 now?\n\nExpected trace\ninitial → fail because utilization exists but a decision record is absent\nexpanded candidate rerank → pass after FINOPS-104 is retrieved\nGemini → approved with conditions")
    add_heading(doc, "Evaluation Boundary", level=2)
    add_text(doc, "The application does not call RAGAS for every production request. RAGAS uses an LLM Judge and can be slow or costly. Production uses deterministic retrieval checks for immediate safety. Offline evaluation uses RAGAS and the Judge to measure quality trends and regressions.")
    doc.add_page_break()

    add_heading(doc, "9 Practical Operation")
    add_heading(doc, "Run Ingestion", level=2)
    add_code(doc, "source .venv/bin/activate\npython ingest.py")
    add_heading(doc, "Run the API", level=2)
    add_code(doc, "zsh run_api.sh")
    add_heading(doc, "Run the Streamlit UI", level=2)
    add_code(doc, ".venv/bin/streamlit run app.py")
    add_heading(doc, "Test the API Directly", level=2)
    add_code(doc, "curl -X POST http://127.0.0.1:8000/v1/analyses \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"question\": \"Should we reduce capacity for analytics-vm-01 now?\", \\\n       \"resource_group\": \"demo-cost-lab\", \"include_trace\": true}'")
    add_heading(doc, "Study Checklist", level=2)
    add_bullets(doc, [
        "Confirm that ingest.py produces parent and child chunks and replaces the Chroma collection.",
        "Trace a named resource through exact inventory scope, reranking, quality assessment, and evidence planning.",
        "Run the analytics-vm-01 question and observe initial failure followed by expanded-rerank success.",
        "Run the tailspin-orphan-disk-03 deletion question and observe both retries followed by abstention.",
        "Compare a Gemini application answer with the RAGAS report, keeping application telemetry separate from Judge usage.",
    ])
    add_heading(doc, "Safe Change Rules", level=2)
    add_bullets(doc, [
        "Re-ingest only when PDFs, chunks, embedding model, or stored metadata change.",
        "Restart the API after code or .env changes.",
        "Keep ALLOW_TRACE_RESPONSE disabled outside controlled development and evaluation.",
        "Add a regression test whenever a resource-scoping or evidence-leakage defect is fixed.",
    ])
    doc.add_page_break()

    add_heading(doc, "10 End to End Walkthrough")
    add_text(doc, "Consider the question Should we reduce capacity for analytics-vm-01 now. The API validates it, finds the exact VM in the inventory, and begins the initial retrieval. The initial candidate set contains utilization evidence but not the approval record, so the deterministic quality check fails. The service expands the candidate set and reranks resource-specific contexts. This second attempt finds FINOPS-104, which approves a business-hours shutdown pilot and D4s_v5 evaluation in development. The quality gate now sees both a decision and measured utilization evidence.")
    add_text(doc, "The evidence planner extracts only analytics-vm-01 blocks. It records the low CPU and memory utilization, development classification, and the approved pilot. Gemini receives a constrained JSON prompt and returns an approved-with-conditions response. If Gemini returned malformed JSON, the service would ask once for a repair and then fall back to a deterministic answer if necessary. The API returns the answer, citations, scope, timing, provider, model, and token counts to Streamlit.")
    add_text(doc, "This design makes the important reasoning steps inspectable. Inventory scope prevents invented resources. Exact resource matching prevents analytics-vm-01-data from contaminating analytics-vm-01. The retry gate raises retrieval quality before generation. Structured validation constrains the LLM. The separate evaluator measures whether those controls improve retrieval and response quality over time.")
    add_heading(doc, "Key Takeaway", level=2)
    add_text(doc, "The pipeline is deliberately layered. Chroma finds evidence, deterministic code checks whether that evidence is sufficient, Gemini expresses a constrained recommendation, and RAGAS evaluates the finished behavior from outside the application. Each layer handles a different failure mode.")

    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build_document()
