"""Create realistic, compact PDF evidence fixtures for retrieval retry tests."""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


OUTPUT = Path(__file__).resolve().parents[1] / "data" / "pdfs"
STYLES = getSampleStyleSheet()

DOCUMENTS = {
    "09_tailspin_network_utilization_snapshot.pdf": [
        "Tailspin Platform — Network Utilization Snapshot",
        "Reporting period: August 2026 | Owner: tailspin-platform",
        "Resource: tailspin-unused-ip-02",
        "Utilization evidence: The public IP has no allocated address, no NIC association, and no load balancer dependency during the 30-day review. The resource has remained unassigned for 34 days.",
        "Required follow-up: Perform the standard dependency scan immediately before any deletion change.",
    ],
    "10_tailspin_finops_decision_register.pdf": [
        "Tailspin FinOps — Optimization Decision Register",
        "Decision register | Change window: September 2026",
        "Resource: tailspin-unused-ip-02",
        "Decision: Approved for removal after the owner confirms the final dependency scan. The change owner is tailspin-platform.",
        "Resource: tailspin-batch-vm-02",
        "Decision: Rightsizing is deferred until the September batch close. Do not reduce capacity before owner approval and a rollback plan are recorded.",
        "Resource: tailspin-archive-disk-02",
        "Decision: Deletion is on hold pending finance owner confirmation and a legal-retention check.",
    ],
    "11_tailspin_compute_and_retention_review.pdf": [
        "Tailspin Data — Compute and Retention Review",
        "Resource: tailspin-batch-vm-02",
        "Utilization evidence: Over the last 28 nightly batch runs, CPU p95 was 31%, memory p95 was 46%, and peak queue latency remained within the 10-minute SLO. A smaller SKU is technically feasible only after the September close validation.",
        "Rollback safeguard: Keep the current size available for one batch cycle and restore it if queue latency exceeds the SLO.",
        "Resource: tailspin-orphan-disk-03",
        "Utilization evidence: This unattached 256 GB disk has had no reads, writes, or attachment events for 45 days. No owner decision, retention decision, or dependency review has yet been recorded.",
        "Resource: tailspin-archive-disk-02",
        "Known exception: This unattached disk contains finance recovery artifacts. The finance forecast rollback window closes September 30. Retain it until the owner sets retentionUntil or approves deletion after legal review.",
    ],
}


def make_pdf(name: str, paragraphs: list[str]) -> None:
    target = OUTPUT / name
    doc = SimpleDocTemplate(
        str(target), pagesize=letter, rightMargin=0.75 * inch, leftMargin=0.75 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
    )
    flow = []
    for index, text in enumerate(paragraphs):
        style = STYLES["Title"] if index == 0 else STYLES["BodyText"]
        flow.extend([Paragraph(text, style), Spacer(1, 0.18 * inch)])
    doc.build(flow)


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, content in DOCUMENTS.items():
        make_pdf(filename, content)
