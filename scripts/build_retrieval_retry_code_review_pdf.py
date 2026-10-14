"""Build a code-review study guide for the RAG retrieval and retry path.

The guide deliberately reads the live source files so the embedded listings are
the code that a reviewer will find in this repository.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "RAG_Retrieval_and_Retry_Code_Review_Guide.pdf"


def source(relative_path: str, start: int | None = None, end: int | None = None) -> str:
    lines = (ROOT / relative_path).read_text(encoding="utf-8").splitlines()
    selected = lines[(start - 1 if start else 0) : end]
    return "\n".join(f"{number:>4}  {line}" for number, line in enumerate(selected, start or 1))


def page_number(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D8E0E8"))
    canvas.line(1.6 * cm, 1.45 * cm, A4[0] - 1.6 * cm, 1.45 * cm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52606D"))
    canvas.drawString(1.6 * cm, 0.9 * cm, "Azure Cost Insight RAG | Retrieval and retry code review guide")
    canvas.drawRightString(A4[0] - 1.6 * cm, 0.9 * cm, f"Page {document.page}")
    canvas.restoreState()


def build() -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="GuideTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=25, leading=30, textColor=colors.HexColor("#102A43"), alignment=TA_LEFT,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Subtitle", parent=styles["BodyText"], fontSize=11, leading=16,
        textColor=colors.HexColor("#486581"), spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="H1Guide", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=17, leading=22, textColor=colors.HexColor("#0B7285"), spaceBefore=8, spaceAfter=9,
    ))
    styles.add(ParagraphStyle(
        name="H2Guide", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12.5, leading=16, textColor=colors.HexColor("#243B53"), spaceBefore=10, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BodyGuide", parent=styles["BodyText"], fontSize=9.4, leading=14,
        textColor=colors.HexColor("#243B53"), spaceAfter=7,
    ))
    styles.add(ParagraphStyle(
        name="SmallGuide", parent=styles["BodyText"], fontSize=8.2, leading=11.5,
        textColor=colors.HexColor("#334E68"), spaceAfter=5,
    ))
    code_style = ParagraphStyle(
        "Code", fontName="Courier", fontSize=6.5, leading=8.2,
        # Preformatted does not render a background reliably in every PDF
        # viewer. Use a high-contrast ink colour on white instead.
        textColor=colors.HexColor("#172B4D"),
        borderPadding=7, leftIndent=0, rightIndent=0, spaceAfter=9,
    )
    styles.add(ParagraphStyle(
        name="Callout", parent=styles["BodyText"], fontSize=9.2, leading=13.5,
        textColor=colors.HexColor("#102A43"), backColor=colors.HexColor("#E6FCF5"),
        borderColor=colors.HexColor("#38A169"), borderWidth=0.6, borderPadding=8, spaceAfter=9,
    ))

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=1.6 * cm, leftMargin=1.6 * cm,
        topMargin=1.6 * cm, bottomMargin=1.9 * cm,
        title="RAG Retrieval and Retry Code Review Guide",
        author="Azure Cost Insight RAG project",
    )
    story = []

    def p(text: str, style="BodyGuide"):
        story.append(Paragraph(text, styles[style]))

    def h1(text: str):
        story.append(Paragraph(text, styles["H1Guide"]))

    def h2(text: str):
        story.append(Paragraph(text, styles["H2Guide"]))

    def code(path: str, start: int | None, end: int | None, why: str):
        # Keep a source listing from starting with only a few orphaned lines at
        # the bottom of an explanatory page. Large listings may still span
        # pages, but always start at the top of a fresh page.
        story.append(PageBreak())
        h2(f"Code: {path}" + (f" (lines {start}-{end})" if start and end else ""))
        p(f"<b>Why this chunk matters:</b> {escape(why)}")
        story.append(Preformatted(source(path, start, end), code_style, maxLineLength=110))

    def wrapped_table(rows, widths, header_color=colors.HexColor("#0B7285")):
        """Use Paragraph cells; bare strings in ReportLab tables do not wrap."""
        header = ParagraphStyle(
            "TableHeader", parent=styles["BodyGuide"], fontName="Helvetica-Bold",
            fontSize=7.5, leading=9.5, textColor=colors.white,
        )
        cell = ParagraphStyle(
            "TableCell", parent=styles["BodyGuide"], fontSize=7.4, leading=9.5,
            textColor=colors.HexColor("#172B4D"),
        )
        formatted = [
            [Paragraph(escape(str(value)), header if row_index == 0 else cell) for value in row]
            for row_index, row in enumerate(rows)
        ]
        result = Table(formatted, colWidths=widths, repeatRows=1)
        result.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_color),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EDF2F7")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return result

    story.append(Spacer(1, 1.0 * cm))
    story.append(Paragraph("Retrieval and Retry Mechanism", styles["GuideTitle"]))
    story.append(Paragraph("A code-review study guide for the Azure Cost Insight RAG pipeline", styles["Subtitle"]))
    p(f"Prepared from the current repository source on {date.today().isoformat()}. This guide focuses on the runtime path that selects evidence, decides whether it is safe enough, retries retrieval when it is not, and constrains answer generation.", "BodyGuide")
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph("Review purpose", styles["H2Guide"]))
    p("Use this document to explain the design in a code review. It distinguishes <b>retrieval retries</b> from <b>generation repair</b>: the first changes how evidence is found; the second fixes malformed or unsafe structured output without fetching new evidence.")
    story.append(Paragraph("Key safety property: the application does not use RAGAS at live request time. It uses deterministic checks to decide whether retrieval is adequate. RAGAS remains an offline evaluation tool.", styles["Callout"]))

    h1("1. One-page mental model")
    data = [
        ["Step", "Component", "What it does", "Can it call an LLM?"],
        ["1", "Inventory scope", "Finds the exact named Azure resource, or safely abstains if it is absent.", "No"],
        ["2", "Vector retrieval", "Embeds the question and asks Chroma for child chunks; restores unique parent chunks.", "Embedding model only"],
        ["3", "Rerank", "Keeps exact resource evidence and selects complementary decision/utilization/policy roles.", "No"],
        ["4", "Quality gate", "Checks resource-specific evidence roles needed for remove/downsize questions.", "No"],
        ["5", "Retrieval retries", "Expands candidate pool, then rewrites the retrieval query if quality is still inadequate.", "No"],
        ["6", "Structured generation", "Asks Ollama or Gemini for strict JSON grounded in the chosen evidence plan.", "Yes"],
        ["7", "Generation repair", "Retries once only if the generated JSON fails validation.", "Yes"],
        ["8", "Fallback", "Returns safe evidence-only response if retrieval or generation cannot meet requirements.", "No"],
    ]
    table = wrapped_table(data, [1.0*cm, 3.0*cm, 9.0*cm, 3.0*cm])
    story.append(table)
    p("The retry pipeline is deliberately bounded: initial retrieval, one broader candidate retrieval, then one focused-query retrieval. It does not loop forever and does not generate an answer until the deterministic quality gate passes.", "SmallGuide")

    h1("2. Data shape: child chunks, parent chunks, and metadata")
    p("During ingestion, a source PDF is split into <b>parent chunks</b> (the readable evidence returned to the LLM) and smaller <b>child chunks</b> (the units stored and searched in Chroma). A child chunk carries a <code>parent_id</code>. This lets the retriever search small, specific passages but return the broader parent evidence with source/page/role metadata.")
    code("ingestion/vector_store.py", 1, 82, "This is the Chroma persistence and query boundary. Notice the collection reset during re-ingestion, the parents.json companion store, raw-distance search, parent de-duplication, and the trace-only score conversion.")
    p("<b>Important review point:</b> <code>score = 1 / (1 + distance)</code> is only a human-friendly trace/display value. Chroma's raw distance defines the initial similarity ordering; the application does not treat the converted score as a universal probability or a safety threshold.", "Callout")

    h1("3. Scope is resolved before retrieval")
    p("The application first obtains an Azure inventory and parses it into a consistent structure. If a question explicitly contains a hyphenated resource name, that name is authoritative. If it does not exist in the inventory, the system abstains rather than retrieve a similarly named resource and make a potentially unsafe recommendation.")
    code("azure/resource_parser.py", 1, 93, "Exact-name scope resolution is the first protection against answering about the wrong resource. It uses regex boundaries so a partial name is not accepted as an exact match.")
    p("Example: a question about <code>tailspin-retry-ip-04</code> that is absent from the inventory returns an inventory-abstention response immediately. It does not query Chroma, call the answer LLM, or pretend an adjacent public IP is equivalent.")

    h1("4. Exact resource matching and resource blocks")
    p("Semantic retrieval can return a parent chunk describing more than one resource. That is useful context, but it creates a risk: a fact about a disk might be incorrectly used as evidence to downsize the VM named next to it. The matching helpers prevent this leakage.")
    code("rag/resource_matching.py", 1, 67, "The boundary-aware regex stops analytics-vm-01 from matching analytics-vm-01-data. resource_blocks() takes only the lines that belong to an allowed resource and ends the block when a different known resource begins.")
    p("<b>How to explain it:</b> a parent chunk is like a page containing several customer records. <code>resource_blocks()</code> cuts out only the record for the customer the user asked about before quality checks or answer planning inspect it.", "Callout")

    h1("5. Retrieval and deterministic reranking")
    p("<code>retrieve_best_practice_contexts()</code> is the main retrieval function. It asks Chroma for more candidates than the final <code>top_k</code>, then re-ranks them deterministically. This is not an LLM reranker: it is fast, explainable Python logic.")
    code("rag/retriever.py", 1, 119, "The retriever has three responsibilities: use built-in guidance when the database has not been ingested, get a candidate pool from Chroma, and rank resource-specific evidence with complementary evidence roles.")
    h2("How the reranker chooses")
    p("For an explicitly scoped resource, if any candidate names that exact resource, generic candidates are discarded. Candidates are then sorted by: (1) whether they mention the resource, (2) how many exact mentions they contain, and (3) the trace score. It attempts to select one source for each role in a question-specific priority order, avoiding repeated sources where possible.")
    p("For removal questions, the preferred order is <b>decision, utilization, policy, exception</b>. For downsize questions it is <b>decision, exception, utilization, policy</b>. This reflects the operational need to know both whether action is allowed and whether the data supports it.")

    h1("6. Deterministic retrieval quality gate")
    p("A vector similarity score alone cannot prove that a destructive action is safe. The quality gate checks coverage. It answers: did we retrieve evidence that names the requested resource, and does that evidence include the types of information needed for this action?")
    code("rag/retrieval_quality.py", 1, 112, "This module contains the live quality policy. It is deterministic and performs no model call. It records evidence roles, source count, best trace score, and explicit failure reasons.")
    h2("Passing conditions")
    quality = [
        ["Question type", "Minimum evidence needed"],
        ["Remove / delete", "At least one decision or exception record AND at least one utilization, policy, or exception safeguard."],
        ["Downsize / downgrade", "At least one decision or exception record AND measured utilization evidence."],
        ["Review", "Named evidence is still captured, but no additional action-specific role combination is required."],
    ]
    t2 = wrapped_table(quality, [4.0*cm, 12.5*cm], colors.HexColor("#334E68"))
    story.append(t2)
    p("Failure is expected and useful. A failed check does not mean Chroma is broken. It means the retrieved evidence does not yet support a safe answer for the requested action, so the retry sequence is allowed to try a better evidence set.")

    h1("7. The retrieval retry sequence")
    p("The orchestration lives in <code>analyze_resources()</code>. Each attempt is logged and kept in <code>retrieval_quality[\"attempts\"]</code>, making the flow visible through API traces and server logs.")
    code("rag/service.py", 1, 208, "This is the complete orchestration path: inventory resolution, initial retrieval, two bounded retrieval retries, quality abstention, structured generation, generation repair, telemetry aggregation, and the response trace.")
    h2("Attempt order")
    attempts = [
        ["Attempt", "Strategy", "What changes", "What does not change"],
        ["0", "inventory_abstention", "Used only for an explicit resource name missing from inventory.", "No vector or LLM call."],
        ["1", "initial", "Candidate pool = top_k x 6 (default); resource-aware rerank returns top_k.", "User question and requested resource."],
        ["2", "expanded_candidate_rerank", "Candidate pool = top_k x 12, then same resource-aware rerank.", "Original question; no LLM call."],
        ["3", "resource_focused_query_rewrite", "Retrieval query explicitly asks for missing decision/utilization/safety evidence; pool remains x 12.", "Original user question is preserved for generation."],
        ["4", "retrieval_quality_abstention", "Safe fallback is rendered when attempt 3 still fails.", "No generation LLM call."],
    ]
    t3 = wrapped_table(attempts, [1.2*cm, 4.4*cm, 7.0*cm, 4.0*cm])
    story.append(t3)
    p("The focused rewrite looks like: <i>Resource: analytics-vm-01. Requested action: downsize. Retrieve decision or exception record and measured utilization, capacity, owner approval, and rollback safeguards. Original question: ...</i> The rewrite is used only to search for evidence. The user-facing generation prompt still contains the original question.", "Callout")

    h1("8. From validated evidence to an answer")
    p("Retrieval success is not the final guard. The response policy extracts an evidence plan, requests strict JSON from the selected provider, parses it, and validates it against resource scope and decision constraints. This makes the LLM responsible for phrasing an answer, not for inventing the decision basis.")
    code("rag/response_policy.py", 1, 233, "This complete module builds the evidence plan, encodes the output contract, validates it, produces a safe fallback, removes duplicated lines, and renders the human-readable answer.")
    h2("Generation repair is different from retrieval retry")
    p("If the initial LLM result is not valid JSON, uses an unknown resource, contradicts a required no/conditional decision, omits reasons, or omits mandatory conditions, the service sends one repair prompt. It supplies the same question and evidence plan. It does <b>not</b> retrieve again. If repair fails, the deterministic fallback renders the evidence plan directly.")
    p("This distinction makes failures easier to diagnose: a retrieval retry means the system lacked evidence coverage; a generation repair means it had sufficient evidence but received invalid presentation/structure from the model.", "Callout")

    h1("9. LLM provider and application telemetry")
    p("The application can use a local Ollama model or the Gemini API. The retrieval quality check itself is independent of this choice. Only structured generation and, if necessary, generation repair invoke the LLM.")
    code("rag/llm_client.py", 1, 107, "The provider adapter normalizes response text and returns non-secret token counters. Ollama reads prompt_eval_count/eval_count; Gemini uses normalized LangChain usage metadata where available.")
    h2("What the API trace exposes")
    telemetry = [
        ["Field", "Meaning"],
        ["retrieved_contexts", "Parent evidence chunks with id, text, source, page, chunk index, role, and display score."],
        ["retrieval_quality", "Final assessment plus the complete attempt history and failure reasons."],
        ["scope", "Named resource scope, whether structured generation repair was used, and final response mode."],
        ["application_usage", "Only application generation calls: provider, model, deployment, number of calls, input/output/total token counters when provider data is available."],
        ["meta", "Collection name, top_k, configured provider/model, and end-to-end latency."],
    ]
    t4 = wrapped_table(telemetry, [4.2*cm, 12.3*cm], colors.HexColor("#334E68"))
    story.append(t4)
    p("Token values are not fabricated. If a provider does not return a reliable count, the value remains <code>None</code>. API keys, prompts, and raw provider secrets are never added to this telemetry.")

    h1("10. What to look for in logs")
    p("The service logs only diagnostic metadata, not prompts or evidence text. A successful first retry might look like this:")
    example = """INFO retrieval_quality strategy=initial passed=False resources=['analytics-vm-01'] matches=3 roles=['policy', 'utilization'] issues=['Rightsizing evidence lacks a decision or exception record.']
INFO retrieval_retry strategy=expanded_candidate_rerank resources=['analytics-vm-01']
INFO retrieval_quality strategy=expanded_candidate_rerank passed=True resources=['analytics-vm-01'] matches=3 roles=['decision', 'utilization'] issues=[]"""
    story.append(Preformatted(example, code_style, maxLineLength=110))
    p("Read this as: initial retrieval knew about the VM and had utilization data, but lacked a decision record. The broader candidate set found a decision record. The quality gate passed, so generation was allowed. That is a retrieval success after one retry, not an LLM answer retry.")

    h1("11. Code-review checklist")
    checklist = [
        "Does the inventory resolver safely distinguish an exact known resource from an unknown hyphenated name?",
        "Are vector-store parent/child identifiers and metadata stable after a re-ingestion?",
        "Does resource_blocks() prevent neighboring resources in a parent chunk from becoming evidence?",
        "Are evidence-role markers appropriate for the organization's documents and vocabulary?",
        "Do remove and downsize policies require sufficient operational safeguards for the risk level?",
        "Are candidate_multiplier and top_k tuned using offline evaluation rather than intuition?",
        "Are retries bounded, logged, and distinguishable from generation repair?",
        "Does the structured-answer validator reject out-of-scope resources and missing mandatory conditions?",
        "Is the fallback response safe and useful when vector evidence or model output is inadequate?",
        "Are telemetry fields free of prompts, credentials, and sensitive raw provider payloads?",
    ]
    for index, item in enumerate(checklist, 1):
        p(f"<b>{index}.</b> {item}")

    h1("12. Practical walkthrough: a downsize question")
    p("Question: <i>Can we downsize analytics-vm-01?</i>")
    walkthrough = [
        "The inventory resolver matches analytics-vm-01 exactly and makes it the only allowed resource.",
        "Chroma retrieves child hits and restores distinct parent evidence chunks. The reranker prefers chunks that mention analytics-vm-01 and aims to include decision plus utilization evidence.",
        "The quality gate sees utilization but no decision/exception record. It returns passed=False and an explicit issue.",
        "The expanded-candidate retry searches twice as many candidates, then reranks again. It finds a FINOPS decision record plus utilization snapshot.",
        "The quality gate now sees decision and utilization. It passes.",
        "The evidence planner decides approved_with_conditions/no/needs_review from the actual evidence wording and extracts mandatory conditions.",
        "The LLM receives the original question, allowed name, evidence plan, retrieved evidence, and JSON contract. It returns a structured decision.",
        "If that JSON is invalid or uses another resource, one generation repair occurs. Otherwise the answer is rendered with evidence, conditions, and next step.",
    ]
    for index, item in enumerate(walkthrough, 1):
        p(f"<b>Step {index}.</b> {item}")

    h1("Appendix: Configuration that affects the flow")
    code("config/settings.py", 1, 31, "These environment-driven settings determine vector-store location, final context count, provider choice, and local generation safety limits. Secrets are read from the environment and are not embedded in source.")
    p("For a code review, the most consequential retrieval setting is <code>RETRIEVAL_TOP_K</code>. It controls the final count of parent contexts after reranking. <code>candidate_multiplier</code> is supplied by the service: 6 for initial retrieval, 12 for each retrieval retry.")

    h1("Closing summary")
    p("This RAG design treats retrieval as an evidence-selection problem, not merely a nearest-neighbor lookup. It strengthens an initial semantic search with exact resource scope, role-aware deterministic reranking, deterministic quality criteria, bounded retries, structured generation, validation, and safe fallbacks. Each stage supplies observability so a reviewer can answer: <i>What did the system retrieve, why did it retry, and why was it allowed to answer?</i>")

    doc.build(story, onFirstPage=page_number, onLaterPages=page_number)
    print(OUTPUT)


if __name__ == "__main__":
    build()
