"""Create source-cited Azure/FinOps reference PDFs for the RAG knowledge base.

The documents intentionally describe Azure resource *types*, evidence, and
approval gates. They do not contain fictional resource-name recommendations.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT = Path(__file__).resolve().parents[1] / "data" / "pdfs"
STYLES = getSampleStyleSheet()
TITLE = ParagraphStyle("IndustryTitle", parent=STYLES["Title"], fontSize=21, leading=25, textColor=colors.HexColor("#17365d"), spaceAfter=10)
SUBTITLE = ParagraphStyle("IndustrySubtitle", parent=STYLES["BodyText"], fontSize=10, leading=14, textColor=colors.HexColor("#4f5d6b"), spaceAfter=16)
HEADING = ParagraphStyle("IndustryHeading", parent=STYLES["Heading2"], fontSize=13, leading=16, textColor=colors.HexColor("#17365d"), spaceBefore=12, spaceAfter=7)
BODY = ParagraphStyle("IndustryBody", parent=STYLES["BodyText"], fontSize=9.5, leading=14, spaceAfter=7)
SMALL = ParagraphStyle("IndustrySmall", parent=BODY, fontSize=8, leading=11, textColor=colors.HexColor("#4f5d6b"))


def bullet(text: str) -> Paragraph:
    return Paragraph(f"• {text}", BODY)


def section(title: str, paragraphs: list[str], bullets: list[str] | None = None) -> list:
    flow = [Paragraph(title, HEADING)]
    flow.extend(Paragraph(value, BODY) for value in paragraphs)
    flow.extend(bullet(value) for value in (bullets or []))
    return flow


def evidence_table(rows: list[tuple[str, str, str]]) -> Table:
    data = [[Paragraph("Decision area", SMALL), Paragraph("Evidence to collect", SMALL), Paragraph("Safe action gate", SMALL)]]
    data.extend([[Paragraph(cell, SMALL) for cell in row] for row in rows])
    table = Table(data, colWidths=[1.5 * inch, 2.7 * inch, 2.35 * inch], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b6c3d1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f3f7fa")),
    ]))
    return table


def build_document(filename: str, title: str, summary: str, sections: list[tuple[str, list[str], list[str]]], evidence: list[tuple[str, str, str]], sources: list[tuple[str, str]]) -> None:
    document = SimpleDocTemplate(
        str(OUTPUT / filename), pagesize=letter, leftMargin=0.62 * inch,
        rightMargin=0.62 * inch, topMargin=0.58 * inch, bottomMargin=0.58 * inch,
        title=title, author="Cloud Cost Optimiser reference corpus",
    )
    flow = [Paragraph("AZURE + FINOPS REFERENCE", SMALL), Paragraph(title, TITLE), Paragraph(summary, SUBTITLE)]
    for heading, paragraphs, bullets in sections:
        flow.extend(section(heading, paragraphs, bullets))
    flow.extend([Paragraph("Evidence and approval model", HEADING), evidence_table(evidence), Spacer(1, 0.14 * inch)])
    flow.append(Paragraph("Source material", HEADING))
    flow.append(Paragraph("This reference summarizes the following official guidance. Check the linked sources for current service limits, billing terms, and implementation details.", BODY))
    for label, url in sources:
        flow.append(Paragraph(f"• <b>{label}</b><br/>{url}", SMALL))
    document.build(flow)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    build_document(
        "15_industry_compute_virtual_machines_and_scale_sets.pdf",
        "Industry Best Practices: Virtual Machines and Scale Sets",
        "Use measured workload demand and business requirements to optimize compute safely. Cost reduction must not weaken availability, performance, security, recovery, or an approved capacity plan.",
        [
            ("Applicable resource types", ["Microsoft.Compute/virtualMachines and Microsoft.Compute/virtualMachineScaleSets."], []),
            ("Cost optimization practices", ["Establish a baseline from CPU, memory, disk, network, queue depth, and workload-specific service-level indicators. Evaluate sustained peak demand, not only averages."], ["Right-size only after observing representative business cycles, batch windows, and seasonal events.", "Use autoscale or schedules where workload patterns are predictable and the operational design supports them.", "Evaluate Spot capacity only for interruptible, fault-tolerant workloads with tested interruption handling.", "Consider reservations or savings plans only after removing avoidable waste and confirming stable, eligible demand."]),
            ("Operational safeguards", ["A lower SKU or instance count is a controlled change, not a billing action. Preserve rollback capacity and validate application latency, error rate, and throughput during a pilot."], ["Require workload-owner approval for production changes.", "Confirm high availability, zone, backup, licensing, and network throughput requirements before changing a size or family.", "Record the original configuration, success criteria, observation window, and rollback trigger."]),
        ],
        [("Rightsizing", "Utilization percentiles, workload SLOs, peak/seasonal demand, SKU capabilities", "Owner-approved pilot; compare service health before and after"), ("Scheduling", "Business-hours demand, maintenance window, operational dependencies", "Approved schedule, start-up validation, exception process"), ("Commitment discount", "Optimized hourly baseline, eligibility, utilization forecast", "Finance and owner review; avoid overlapping commitments")],
        [("Azure VM cost optimization best practices", "https://learn.microsoft.com/en-us/azure/virtual-machines/cost-optimization-best-practices"), ("Azure Well-Architected VM guidance", "https://learn.microsoft.com/azure/well-architected/service-guides/virtual-machines"), ("Azure reservations and savings plans", "https://learn.microsoft.com/azure/cost-management-billing/savings-plan/decide-between-savings-plan-reservation")],
    )
    build_document(
        "16_industry_storage_disks_and_data_services.pdf",
        "Industry Best Practices: Storage, Managed Disks, and Data Services",
        "Optimize data cost through lifecycle, tiering, capacity, retention, and access-pattern decisions. Treat data durability, recovery, legal hold, and compliance obligations as first-class constraints.",
        [
            ("Applicable resource types", ["Microsoft.Compute/disks, Microsoft.Storage/storageAccounts, Microsoft.Sql/servers, and associated backup, snapshot, and data-retention resources."], []),
            ("Cost optimization practices", ["Match redundancy, performance tier, and access tier to documented recovery and latency requirements. Use lifecycle management for eligible data after classifying access patterns and retention obligations."], ["Review disk size, performance tier, attachment state, IOPS/throughput demand, snapshots, and backup dependencies together.", "Use storage analytics to identify suitable candidates for tiering and lifecycle policy, scoped to approved containers or prefixes.", "For databases, use measured CPU/DTU/vCore, storage, IO, concurrency, and performance baselines before changing service tier.", "Prefer capacity and rate commitments only after workload usage is stable and waste has been addressed."]),
            ("Operational safeguards", ["Unattached or cold data is not automatically disposable. Validate ownership, restore requirements, legal hold, backup chain, retention policy, and business continuity requirements."], ["Apply lifecycle policies in a staged scope and verify restore behavior.", "Do not reduce redundancy, backup retention, database tier, or recovery objectives without owner and risk approval.", "Keep an auditable decision record for data-classification and retention exceptions."]),
        ],
        [("Storage lifecycle", "Access frequency, prefix/container ownership, retention and legal requirements", "Stage policy; validate restore and exception workflow"), ("Managed disk tier", "IOPS, throughput, capacity, attachment state, snapshots", "Confirm workload and recovery dependency; plan rollback"), ("Database tier", "Peak CPU/DTU/vCore, IO latency, storage and workload SLO", "Load test and approve maintenance/change window")],
        [("Azure Well-Architected data cost strategies", "https://learn.microsoft.com/en-us/azure/well-architected/cost-optimization/optimize-data-costs"), ("Azure storage architecture guidance", "https://learn.microsoft.com/en-us/azure/architecture/storage/storage-get-started"), ("Azure Cost Management recommendations", "https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-opt-recommendations")],
    )
    build_document(
        "17_industry_app_service_and_container_registry.pdf",
        "Industry Best Practices: App Service Plans, Web Apps, and Container Registries",
        "Optimize platform services through measured scaling, plan density, tier selection, image hygiene, and cost ownership. Preserve application availability, deployment safety, and supply-chain controls.",
        [
            ("Applicable resource types", ["Microsoft.Web/serverfarms, Microsoft.Web/sites, and Microsoft.ContainerRegistry/registries."], []),
            ("Cost optimization practices", ["For App Service, evaluate the plan SKU, worker count, autoscale limits, and app-to-plan placement together. A plan is billed for provisioned capacity, so idle workers and fragmented plans require workload-level review."], ["Use metric- and schedule-based autoscale with tested minimum, maximum, cooldown, and application warm-up behavior.", "Assess whether compatible applications can share a plan without violating isolation, scaling, security, or noisy-neighbor requirements.", "Review registry tier features, geo-replication needs, storage growth, image tagging, and untagged-manifest retention.", "Keep registries network-close to deployment targets where architecture and resilience requirements allow."]),
            ("Operational safeguards", ["Do not change production plan capacity or registry retention on cost evidence alone. Validate peak traffic, deployment workflows, image pull behavior, rollback, and owner approval."], ["Test autoscale under representative load.", "Before a registry retention policy, verify digest-based pulls and recovery expectations.", "Review forecast and budget impact when changing a tier or scaling envelope."]),
        ],
        [("App Service scaling", "Request rate, CPU/memory, latency, error rate, worker count, warm-up time", "Load-test autoscale; validate min/max and rollback"), ("Plan consolidation", "App compatibility, isolation, scale patterns, operational ownership", "Architecture and service-owner approval"), ("Registry retention/tier", "Image age, tags, pull references, replication and feature requirements", "Dependency scan and staged retention policy")],
        [("Azure App Service cost management", "https://learn.microsoft.com/en-us/azure/app-service/overview-manage-costs"), ("Azure Well-Architected App Service guidance", "https://learn.microsoft.com/en-us/azure/well-architected/service-guides/app-service-web-apps"), ("Azure Container Registry best practices", "https://learn.microsoft.com/en-us/azure/container-registry/container-registry-best-practices"), ("Azure Container Registry retention policy guidance", "https://learn.microsoft.com/en-us/azure/container-registry/container-registry-retention-policy")],
    )
    build_document(
        "18_industry_network_public_ip_and_connectivity.pdf",
        "Industry Best Practices: Public IP Addresses and Network Connectivity",
        "Optimize network cost only after establishing the workload's connectivity, security, routing, availability, and dependency requirements. Network resources often support multiple applications and should be reviewed as shared infrastructure.",
        [
            ("Applicable resource types", ["Microsoft.Network/publicIPAddresses and related network interfaces, load balancers, gateways, firewalls, private endpoints, and routing resources."], []),
            ("Cost optimization practices", ["Maintain a current inventory of address allocation method, association, SKU, zone requirements, DNS records, firewall rules, routing dependencies, and owning workload. Review unassociated addresses as candidates for an ownership and dependency assessment."], ["Use the least costly architecture that still meets availability, security, routing, and IPv4/IPv6 requirements.", "Monitor data-transfer patterns and cross-region traffic before redesigning connectivity.", "Tag network resources with owner, environment, application, cost center, and planned end date where applicable.", "Use Cost Management and Azure Advisor signals as triage inputs, then validate them with the network and application owners."]),
            ("Operational safeguards", ["An unassociated public IP may still be reserved for failover, migration, allowlists, DNS cutover, or an approved upcoming deployment."], ["Require dependency and change review before altering an allocation.", "Confirm DNS, firewall, load-balancer, API allowlist, and disaster-recovery implications.", "Document an approved rollback and communication plan for customer-facing endpoints."]),
        ],
        [("Unassociated allocation", "Association state, owner, DNS/allowlists, planned change, disaster-recovery role", "Network-owner dependency review and approved change record"), ("Network redesign", "Flow logs, egress pattern, latency, resilience and security architecture", "Architecture review; validate resilience and cost trade-offs"), ("Cost attribution", "Tags, subscription/resource-group scope, data-transfer billing dimensions", "FinOps owner validates allocation completeness")],
        [("Azure Cost Management recommendation workflow", "https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-opt-recommendations"), ("Azure Well-Architected Framework overview", "https://learn.microsoft.com/en-us/azure/well-architected/what-is-well-architected-framework"), ("FinOps Framework overview", "https://learn.microsoft.com/en-us/cloud-computing/finops/framework/finops-framework")],
    )
    build_document(
        "19_industry_finops_governance_commitments_and_accountability.pdf",
        "Industry Best Practices: FinOps Governance, Commitments, and Accountability",
        "Cost optimization is a continuous operating practice. Recommendations should be prioritized by measurable impact, implementation effort, risk, owner accountability, and verified outcome - not merely by theoretical savings.",
        [
            ("Applicable scope", ["All Azure resource types and billing scopes, including subscriptions, resource groups, management groups, shared services, and platform products."], []),
            ("Operating model", ["Use a shared accountability model across engineering, finance, product, security, and operations. Maintain allocation tags, cost ownership, budgets, anomaly processes, and a prioritized optimization backlog."], ["Record an accountable owner, evidence period, recommendation, risk, decision, target date, and validation result.", "Separate observed facts from estimates and approved actions.", "Treat budgets, forecasts, and anomaly alerts as decision-support signals rather than automatic authorization for configuration change."]),
            ("Commitment and rate optimization", ["Right-size and remove avoidable waste before purchasing reservations or savings plans. Evaluate discounted commitments using stable, optimized historical usage and expected workload change."], ["Use Azure's recommendation logic as an input; review coverage, utilization, scope, term, flexibility, and existing commitments.", "For stable, known service/SKU/region demand, assess reservations; for eligible dynamic compute demand, assess savings plans.", "Avoid buying overlapping commitments before recommendation systems reflect recent purchases."]),
        ],
        [("Ownership and allocation", "Mandatory tags, cost allocation coverage, business owner and technical owner", "Resolve missing ownership before material changes"), ("Optimization backlog", "Savings estimate, effort, risk, workload SLO and approval status", "Prioritize jointly; validate realized outcome"), ("Commitment purchase", "Optimized hourly baseline, 7/30/60-day usage, coverage and utilization", "Finance/procurement approval and recurring utilization review")],
        [("FinOps Framework overview", "https://learn.microsoft.com/en-us/cloud-computing/finops/framework/finops-framework"), ("FinOps Foundation usage optimization", "https://www.finops.org/framework/capabilities/usage-optimization/"), ("Azure rate optimization", "https://learn.microsoft.com/en-us/cloud-computing/finops/framework/optimize/rates"), ("Azure savings plan recommendations", "https://learn.microsoft.com/en-us/azure/cost-management-billing/savings-plan/purchase-recommendations")],
    )
    print("Created five industry best-practice PDFs.")


if __name__ == "__main__":
    main()
