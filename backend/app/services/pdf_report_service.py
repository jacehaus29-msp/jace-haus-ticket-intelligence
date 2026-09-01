import io
from datetime import datetime, timezone
from typing import Dict, Any, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, HRFlowable


def generate_executive_pdf_report(
    summary_data: Dict[str, Any],
    sla_data: Dict[str, Any],
    tickets_data: List[Dict[str, Any]],
    filters: Dict[str, Any],
    organization_name: str = "All Organizations",
    is_customer_view: bool = False
) -> bytes:
    """
    Generate a high-fidelity Executive Service & SLA Performance PDF report.
    Designed for MSP account reviews, QBRs, and client compliance auditing.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e293b"),
        fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        fontName="Helvetica"
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        fontName="Helvetica-Bold",
        spaceBefore=12,
        spaceAfter=6
    )
    kpi_num_style = ParagraphStyle(
        "KpiNum",
        parent=styles["Normal"],
        fontSize=16,
        leading=18,
        textColor=colors.HexColor("#0284c7"),
        fontName="Helvetica-Bold",
        alignment=1
    )
    kpi_label_style = ParagraphStyle(
        "KpiLabel",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#64748b"),
        fontName="Helvetica",
        alignment=1
    )
    cell_text = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#334155"),
        fontName="Helvetica"
    )
    cell_header = ParagraphStyle(
        "CellHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#ffffff"),
        fontName="Helvetica-Bold"
    )

    story = []

    # 1. Header Banner
    header_data = [
        [
            Paragraph("<strong>JACE HAUS</strong> &bull; MSP Service Intelligence", ParagraphStyle("Brand", fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#0284c7"))),
            Paragraph(f"Generated: {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}", ParagraphStyle("Date", fontName="Helvetica", fontSize=9, alignment=2, textColor=colors.HexColor("#64748b")))
        ]
    ]
    header_table = Table(header_data, colWidths=[300, 240])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284c7"), spaceAfter=10))

    # 2. Report Title & Scope
    story.append(Paragraph(f"Executive Service & SLA Report — {organization_name}", title_style))
    start_d = filters.get("start_date") or "All Available History"
    end_d = filters.get("end_date") or "Current Date"
    filter_desc = f"Period: <strong>{start_d}</strong> to <strong>{end_d}</strong>"
    if filters.get("team"):
        filter_desc += f" &bull; Team: <strong>{filters['team']}</strong>"
    if filters.get("priority"):
        filter_desc += f" &bull; Priority: <strong>{filters['priority'].upper()}</strong>"
    story.append(Paragraph(filter_desc, subtitle_style))
    story.append(Spacer(1, 10))

    # 3. KPI Summary Matrix (Top 6 Executive Cards)
    tot = summary_data.get("total_tickets", 0)
    sla_comp = summary_data.get("sla_compliance_rate", 100)
    avg_resp = summary_data.get("avg_response_time_label", "N/A")
    avg_resol = summary_data.get("avg_resolution_time_label", "N/A")
    breaches = summary_data.get("sla_breaches", 0)
    escalations = summary_data.get("escalation_count", 0)

    kpi_table_data = [
        [
            [Paragraph(f"{tot}", kpi_num_style), Paragraph("TOTAL TICKETS", kpi_label_style)],
            [Paragraph(f"{sla_comp}%", kpi_num_style), Paragraph("SLA COMPLIANCE", kpi_label_style)],
            [Paragraph(f"{avg_resp}", kpi_num_style), Paragraph("AVG RESPONSE", kpi_label_style)],
            [Paragraph(f"{avg_resol}", kpi_num_style), Paragraph("AVG RESOLUTION", kpi_label_style)],
            [Paragraph(f"{breaches}", ParagraphStyle("KpiBreach", parent=kpi_num_style, textColor=colors.HexColor("#dc2626"))), Paragraph("SLA BREACHES", kpi_label_style)],
            [Paragraph(f"{escalations}", ParagraphStyle("KpiEsc", parent=kpi_num_style, textColor=colors.HexColor("#ea580c"))), Paragraph("ESCALATIONS", kpi_label_style)],
        ]
    ]
    kpi_table = Table(kpi_table_data, colWidths=[90, 90, 90, 90, 90, 90])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#e2e8f0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 14))

    # 4. Status & Volume Distribution
    story.append(Paragraph("1. Ticket Volume & Status Breakdown", section_heading))
    new_cnt = summary_data.get("status_counts", {}).get("new", 0)
    prog_cnt = summary_data.get("status_counts", {}).get("in_progress", 0)
    res_cnt = summary_data.get("status_counts", {}).get("resolved", 0)
    auto_rt = summary_data.get("automation_rate", 0)

    vol_data = [
        [
            Paragraph("Status / Lifecycle", cell_header),
            Paragraph("Count", cell_header),
            Paragraph("Share of Volume", cell_header),
            Paragraph("Operational Assessment", cell_header),
        ],
        [
            Paragraph("New / Awaiting Dispatch", cell_text),
            Paragraph(str(new_cnt), cell_text),
            Paragraph(f"{(new_cnt/tot*100):.1f}%" if tot > 0 else "0%", cell_text),
            Paragraph("Initial queue intake", cell_text),
        ],
        [
            Paragraph("In Progress / Active Work", cell_text),
            Paragraph(str(prog_cnt), cell_text),
            Paragraph(f"{(prog_cnt/tot*100):.1f}%" if tot > 0 else "0%", cell_text),
            Paragraph("Under technician investigation", cell_text),
        ],
        [
            Paragraph("Resolved / Completed", cell_text),
            Paragraph(str(res_cnt), cell_text),
            Paragraph(f"{(res_cnt/tot*100):.1f}%" if tot > 0 else "0%", cell_text),
            Paragraph("Service delivered successfully", cell_text),
        ],
        [
            Paragraph("Automated Rule Routing", cell_text),
            Paragraph(f"{auto_rt}%", cell_text),
            Paragraph(f"{summary_data.get('automated_count', 0)} tickets", cell_text),
            Paragraph("Automated dispatch rate", cell_text),
        ],
    ]
    vol_table = Table(vol_data, colWidths=[150, 80, 110, 200])
    vol_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(vol_table)
    story.append(Spacer(1, 14))

    # 5. SLA Performance Matrix
    story.append(Paragraph("2. SLA Performance by Priority Tier", section_heading))
    sla_by_pri = sla_data.get("sla_by_priority", {})
    sla_table_data = [
        [
            Paragraph("Priority Tier", cell_header),
            Paragraph("Target Response", cell_header),
            Paragraph("Target Resolution", cell_header),
            Paragraph("On Track", cell_header),
            Paragraph("At Risk", cell_header),
            Paragraph("Breached", cell_header),
            Paragraph("Met", cell_header),
        ]
    ]

    targets = {
        "critical": ("15m", "2h"),
        "high": ("30m", "4h"),
        "medium": ("1h", "8h"),
        "low": ("4h", "24h"),
    }

    for p in ["critical", "high", "medium", "low"]:
        p_data = sla_by_pri.get(p, {})
        tgt_resp, tgt_res = targets.get(p, ("-", "-"))
        sla_table_data.append([
            Paragraph(p.upper(), cell_text),
            Paragraph(tgt_resp, cell_text),
            Paragraph(tgt_res, cell_text),
            Paragraph(str(p_data.get("on_track", 0)), cell_text),
            Paragraph(str(p_data.get("at_risk", 0)), cell_text),
            Paragraph(str(p_data.get("breached", 0)), ParagraphStyle("B", parent=cell_text, textColor=colors.HexColor("#dc2626") if p_data.get("breached", 0) > 0 else colors.HexColor("#334155"))),
            Paragraph(str(p_data.get("met", 0)), ParagraphStyle("M", parent=cell_text, textColor=colors.HexColor("#16a34a"))),
        ])

    sla_tbl = Table(sla_table_data, colWidths=[80, 80, 80, 75, 75, 75, 75])
    sla_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sla_tbl)
    story.append(Spacer(1, 14))

    # 6. Team Breakdown Table (Internal view only, or sanitized for client)
    if not is_customer_view:
        story.append(Paragraph("3. Department & Team Workload Distribution", section_heading))
        team_dist = summary_data.get("tickets_by_team", {})
        team_table_data = [
            [
                Paragraph("Assigned Team", cell_header),
                Paragraph("Total Assigned", cell_header),
                Paragraph("Workload Share", cell_header),
            ]
        ]
        for tm, cnt in sorted(team_dist.items(), key=lambda x: x[1], reverse=True):
            team_table_data.append([
                Paragraph(tm, cell_text),
                Paragraph(str(cnt), cell_text),
                Paragraph(f"{(cnt/tot*100):.1f}%" if tot > 0 else "0%", cell_text),
            ])
        team_tbl = Table(team_table_data, colWidths=[240, 150, 150])
        team_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(team_tbl)
        story.append(Spacer(1, 14))

    # 7. Category Breakdown Table
    story.append(Paragraph("3. Issue Category Breakdown" if is_customer_view else "4. Issue Category Breakdown", section_heading))
    cat_dist = summary_data.get("tickets_by_category", {})
    cat_table_data = [
        [
            Paragraph("Category", cell_header),
            Paragraph("Ticket Count", cell_header),
            Paragraph("Percentage", cell_header),
        ]
    ]
    for cat, cnt in sorted(cat_dist.items(), key=lambda x: x[1], reverse=True):
        cat_table_data.append([
            Paragraph(cat, cell_text),
            Paragraph(str(cnt), cell_text),
            Paragraph(f"{(cnt/tot*100):.1f}%" if tot > 0 else "0%", cell_text),
        ])
    cat_tbl = Table(cat_table_data, colWidths=[240, 150, 150])
    cat_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#334155")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(cat_tbl)
    story.append(Spacer(1, 14))

    # 8. Sample Ticket Log (Top 10)
    story.append(Paragraph("4. Recent Ticket Log & SLA Status" if is_customer_view else "5. Recent Ticket Log & SLA Status", section_heading))
    t_table_data = [
        [
            Paragraph("ID", cell_header),
            Paragraph("Subject", cell_header),
            Paragraph("Priority", cell_header),
            Paragraph("Status", cell_header),
            Paragraph("SLA State", cell_header),
        ]
    ]
    sample_tickets = tickets_data[:12]
    for t in sample_tickets:
        sla_st = t.get("sla_status", "on_track").replace("_", " ").upper()
        pri_st = (t.get("priority") or "medium").upper()
        t_table_data.append([
            Paragraph(f"#{t.get('id')}", cell_text),
            Paragraph(t.get("title", "")[:45] + ("..." if len(t.get("title", "")) > 45 else ""), cell_text),
            Paragraph(pri_st, cell_text),
            Paragraph(t.get("status", "new").replace("_", " ").upper(), cell_text),
            Paragraph(sla_st, cell_text),
        ])
    t_tbl = Table(t_table_data, colWidths=[45, 235, 75, 95, 90])
    t_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#ffffff"), colors.HexColor("#f8fafc")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
    ]))
    story.append(t_tbl)
    story.append(Spacer(1, 16))

    # 9. Executive QBR Closing Block
    closing_text = (
        f"<strong>Service Level Review Summary:</strong> During this reporting cycle, <strong>{tot}</strong> "
        f"support requests were serviced with an overall SLA compliance rating of <strong>{sla_comp}%</strong>. "
        f"Average first response time was <strong>{avg_resp}</strong>, and average resolution time was <strong>{avg_resol}</strong>. "
        f"All services remain governed under active MSP Service Level Agreements."
    )
    story.append(Paragraph(closing_text, ParagraphStyle("Closing", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#475569"))))

    doc.build(story)
    return buffer.getvalue()
