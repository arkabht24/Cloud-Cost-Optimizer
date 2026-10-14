"""Create a controlled corpus fixture for a successful first retrieval retry.

The utilization review deliberately repeats the question vocabulary across five
pages.  Its child chunks occupy the first semantic candidate pool (18 hits).
The separate decision register is less similar to the user question, but is
available in the expanded pool (36 hits).  This demonstrates that the first
retry improves evidence coverage without needing the query-rewrite retry.
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


OUTPUT = Path(__file__).resolve().parents[1] / "data" / "pdfs"
STYLES = getSampleStyleSheet()
RESOURCE = "retry-lab-vm-01"


def build_utilization_review() -> None:
    """Write enough highly similar utilization evidence to fill initial search."""
    path = OUTPUT / "13_retry_lab_utilization_review.pdf"
    document = SimpleDocTemplate(
        str(path), pagesize=letter, rightMargin=0.7 * inch, leftMargin=0.7 * inch,
        topMargin=0.65 * inch, bottomMargin=0.65 * inch,
    )
    flow = []
    # Twenty-four independent reporting windows provide more than eighteen
    # highly similar child chunks. That is intentional: the initial candidate
    # pool contains utilization evidence only, while the 36-hit retry pool can
    # also include the separate decision record.
    for window in range(1, 25):
        paragraphs = [
            f"Retry Lab Capacity Utilization Review — reporting window {window:02d}",
            f"Resource: {RESOURCE}",
            f"Measured utilization for {RESOURCE}: CPU p95 was 17%, memory p95 was 39%, and the virtual machine had no workload saturation events.",
            f"Capacity review for {RESOURCE}: measured demand remained low during business hours, batch windows, and scheduled maintenance periods.",
            f"Rightsizing analysis for {RESOURCE}: the current D8s_v5 capacity exceeds observed CPU and memory demand in the development environment.",
            f"Downsize planning for {RESOURCE}: collect utilization evidence, validate application performance, and monitor queue latency during a capacity experiment.",
            f"Resource: {RESOURCE}. Utilization metrics: CPU p50 5%, CPU p95 17%, memory p95 39%, uptime 99.7%, and no scaling events.",
            f"Resource: {RESOURCE}. Capacity evidence: a smaller development virtual-machine SKU appears technically feasible from utilization measurements alone.",
            f"Resource: {RESOURCE}. The review contains utilization observations only; no operational approval record is included in this report.",
        ]
        for index, value in enumerate(paragraphs):
            flow.extend([Paragraph(value, STYLES["Title"] if index == 0 else STYLES["BodyText"]), Spacer(1, 0.14 * inch)])
        if window != 24:
            flow.append(PageBreak())
    document.build(flow)


def build_decision_register() -> None:
    """Write the decision evidence expected to enter only after expansion."""
    path = OUTPUT / "14_retry_lab_change_register.pdf"
    document = SimpleDocTemplate(
        str(path), pagesize=letter, rightMargin=0.7 * inch, leftMargin=0.7 * inch,
        topMargin=0.65 * inch, bottomMargin=0.65 * inch,
    )
    paragraphs = [
        "Retry Lab Change Decision Register",
        f"Resource: {RESOURCE}",
        "Decision: Approved with conditions under change RFC-482.",
        "The owner must complete a one-week D4s_v5 pilot, retain the current size as the rollback option, and confirm application latency remains within the service objective before the permanent change.",
        "Change owner: retry-lab-platform. Review the pilot evidence before closing RFC-482.",
    ]
    flow = []
    for index, value in enumerate(paragraphs):
        flow.extend([Paragraph(value, STYLES["Title"] if index == 0 else STYLES["BodyText"]), Spacer(1, 0.16 * inch)])
    document.build(flow)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    build_utilization_review()
    build_decision_register()
    print("Created retry-lab PDF fixtures.")
