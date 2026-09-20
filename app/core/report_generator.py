"""PDF report generation using ReportLab."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    Image as RLImage, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT

from app.core.models import AnalysisResult, DataQualityReport, Finding, FindingSeverity, ReportContext, ReportResult
from app.core.utils import ensure_dir, format_currency, format_number, format_percent
from app.core.validator import summarize_quality

# Color scheme
PRIMARY = colors.HexColor("#2E86AB")
DARK = colors.HexColor("#1A1A2E")
ACCENT = colors.HexColor("#F18F01")
LIGHT_BG = colors.HexColor("#F5F5F5")
SEVERITY_COLORS = {
    FindingSeverity.CRITICAL: colors.HexColor("#C73E1D"),
    FindingSeverity.HIGH: colors.HexColor("#E85D04"),
    FindingSeverity.MEDIUM: colors.HexColor("#F18F01"),
    FindingSeverity.LOW: colors.HexColor("#2D8659"),
    FindingSeverity.INFO: colors.HexColor("#2E86AB"),
}


def _build_styles() -> dict:
    base = getSampleStyleSheet()
    styles = {}
    styles["Title"] = ParagraphStyle("Title", parent=base["Title"], fontSize=24, textColor=DARK, spaceAfter=6, alignment=TA_LEFT)
    styles["Subtitle"] = ParagraphStyle("Subtitle", parent=base["Normal"], fontSize=11, textColor=colors.HexColor("#666666"), spaceAfter=20)
    styles["H1"] = ParagraphStyle("H1", parent=base["Heading1"], fontSize=16, textColor=PRIMARY, spaceBefore=20, spaceAfter=10, borderWidth=0)
    styles["H2"] = ParagraphStyle("H2", parent=base["Heading2"], fontSize=13, textColor=DARK, spaceBefore=12, spaceAfter=6)
    styles["Body"] = ParagraphStyle("Body", parent=base["Normal"], fontSize=10, leading=14, alignment=TA_JUSTIFY, spaceAfter=6)
    styles["Bullet"] = ParagraphStyle("Bullet", parent=base["Normal"], fontSize=10, leading=14, leftIndent=15, spaceAfter=3)
    styles["Finding"] = ParagraphStyle("Finding", parent=base["Normal"], fontSize=9.5, leading=13, leftIndent=10, spaceAfter=4)
    styles["TableCell"] = ParagraphStyle("TableCell", parent=base["Normal"], fontSize=9, leading=12)
    styles["TableHeader"] = ParagraphStyle("TableHeader", parent=base["Normal"], fontSize=9, leading=12, textColor=colors.white, fontName="Helvetica-Bold")
    styles["StatCell"] = ParagraphStyle("StatCell", parent=base["Normal"], fontSize=8, leading=9.5, alignment=TA_RIGHT, wordWrap="CJK")
    styles["StatCellLeft"] = ParagraphStyle("StatCellLeft", parent=base["Normal"], fontSize=8, leading=9.5, alignment=TA_LEFT, wordWrap="CJK")
    styles["Caption"] = ParagraphStyle("Caption", parent=base["Normal"], fontSize=8, textColor=colors.HexColor("#888888"), alignment=TA_CENTER, spaceAfter=10)
    return styles


def _kpi_table(kpis: dict, styles: dict) -> Table:
    """Build a KPI summary table."""
    if not kpis:
        return Paragraph("No KPIs available.", styles["Body"])

    data = [["Metric", "Value"]]
    for key, value in kpis.items():
        display_key = key.replace("_", " ").title()
        if isinstance(value, float):
            if "margin" in key or "pct" in key:
                display_val = format_percent(value)
            else:
                display_val = format_currency(value)
        elif isinstance(value, int):
            display_val = format_number(float(value))
        else:
            display_val = str(value)
        data.append([display_key, display_val])

    table = Table(data, colWidths=[8 * cm, 6 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return KeepTogether([table])


def _findings_section(findings: list[Finding], styles: dict) -> list:
    """Build the findings section of the report."""
    elements = []
    if not findings:
        elements.append(Paragraph("No significant findings were identified.", styles["Body"]))
        return elements

    # Sort by severity
    severity_order = {
        FindingSeverity.CRITICAL: 0, FindingSeverity.HIGH: 1,
        FindingSeverity.MEDIUM: 2, FindingSeverity.LOW: 3, FindingSeverity.INFO: 4
    }
    sorted_findings = sorted(findings, key=lambda f: severity_order.get(f.severity, 5))

    for f in sorted_findings:
        sev_color = SEVERITY_COLORS.get(f.severity, colors.black)
        sev_label = f.severity.value.upper()

        finding_elements = []
        header = f'<b><font color="{sev_color.hexval()}">[{sev_label}]</font> {f.title}</b>'
        finding_elements.append(Paragraph(header, styles["Finding"]))

        if f.explanation:
            finding_elements.append(Paragraph(f"<b>Details:</b> {f.explanation}", styles["Finding"]))
        if f.evidence:
            finding_elements.append(Paragraph(f"<b>Evidence:</b> {f.evidence}", styles["Finding"]))
        if f.comparison:
            finding_elements.append(Paragraph(f"<b>Comparison:</b> {f.comparison}", styles["Finding"]))
        if f.recommended_action:
            finding_elements.append(Paragraph(f"<b>Recommendation:</b> {f.recommended_action}", styles["Finding"]))
        finding_elements.append(Spacer(1, 4))

        elements.append(KeepTogether(finding_elements))

    return elements


def _quality_section(quality_reports: list[DataQualityReport], styles: dict) -> list:
    """Build the data quality section."""
    elements = []
    if not quality_reports:
        elements.append(Paragraph("No data quality information available.", styles["Body"]))
        return elements

    for qr in quality_reports:
        qr_elements = [Paragraph(f"<b>Source:</b> {qr.source}", styles["Body"])]

        data = [
            ["Metric", "Value"],
            ["Rows before cleaning", str(qr.rows_before)],
            ["Rows after cleaning", str(qr.rows_after)],
            ["Duplicates detected", str(qr.duplicates_detected)],
            ["Duplicates removed", str(qr.duplicates_removed)],
            ["Columns before", str(qr.columns_before)],
            ["Columns after", str(qr.columns_after)],
        ]
        if qr.date_range[0]:
            data.append(["Date range", f"{qr.date_range[0]} to {qr.date_range[1]}"])
        data.append(["Numeric columns", ", ".join(qr.numeric_columns) or "None"])
        data.append(["Categorical columns", ", ".join(qr.categorical_columns) or "None"])
        data.append(["Date columns", ", ".join(qr.date_columns) or "None"])

        table = Table(data, colWidths=[5 * cm, 11 * cm])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        qr_elements.append(table)
        elements.append(KeepTogether(qr_elements))
        elements.append(Spacer(1, 8))

        if qr.potential_issues:
            issues_elements = [Paragraph("<b>Potential Issues:</b>", styles["Body"])]
            for issue in qr.potential_issues:
                issues_elements.append(Paragraph(f"• {issue}", styles["Bullet"]))
            elements.append(KeepTogether(issues_elements))

        if qr.transformations:
            transform_elements = [Paragraph("<b>Transformations Applied:</b>", styles["Body"])]
            for t in qr.transformations:
                transform_elements.append(Paragraph(f"• {t}", styles["Bullet"]))
            elements.append(KeepTogether(transform_elements))

        elements.append(Spacer(1, 10))

    return elements


def _immediate_actions_section(findings: list[Finding], styles: dict) -> list:
    """Build the Immediate Actions section: top findings with recommended actions."""
    elements = []
    # Filter findings that have recommended actions
    actionable = [f for f in findings if f.recommended_action]
    if not actionable:
        return elements

    # Sort by severity (highest first)
    severity_order = {
        FindingSeverity.CRITICAL: 0, FindingSeverity.HIGH: 1,
        FindingSeverity.MEDIUM: 2, FindingSeverity.LOW: 3, FindingSeverity.INFO: 4
    }
    sorted_findings = sorted(actionable, key=lambda f: severity_order.get(f.severity, 5))

    elements.append(Paragraph("Immediate Actions", styles["H1"]))
    elements.append(Paragraph(
        "The following actions are recommended based on the analysis findings. "
        "Items are prioritized by severity.",
        styles["Body"]
    ))
    elements.append(Spacer(1, 6))

    for i, f in enumerate(sorted_findings[:8], 1):
        sev_label = f.severity.value.upper()
        action_elements = []

        # Action header with priority
        action_elements.append(Paragraph(
            f"<b>{i}. [{sev_label}] {f.title}</b>",
            styles["Finding"]
        ))

        # The recommended action
        action_elements.append(Paragraph(
            f"<b>Action:</b> {f.recommended_action}",
            styles["Finding"]
        ))

        # Evidence backing the action
        if f.evidence:
            action_elements.append(Paragraph(
                f"<b>Evidence:</b> {f.evidence}",
                styles["Finding"]
            ))

        # Comparison/context
        if f.comparison:
            action_elements.append(Paragraph(
                f"<b>Context:</b> {f.comparison}",
                styles["Finding"]
            ))

        action_elements.append(Spacer(1, 4))
        elements.append(KeepTogether(action_elements))

    return elements


def _chart_section(charts: dict, styles: dict, title: str) -> list:
    """Build a chart section."""
    elements = [Paragraph(title, styles["H2"])]
    for label, path in charts.items():
        if os.path.exists(path):
            # Use PIL to get the image's natural aspect ratio for proportional scaling
            from PIL import Image as PILImage
            try:
                with PILImage.open(path) as pil_img:
                    natural_width, natural_height = pil_img.size
                target_width = 16 * cm
                aspect = natural_height / natural_width if natural_width > 0 else 0.5
                target_height = target_width * aspect
                # Cap height to avoid oversized charts
                if target_height > 10 * cm:
                    target_height = 10 * cm
                    target_width = target_height / aspect
                img = RLImage(path, width=target_width, height=target_height)
            except Exception:
                img = RLImage(path, width=16 * cm, height=8 * cm)
            img.hAlign = "CENTER"
            elements.append(img)
            elements.append(Spacer(1, 6))
    return elements


def _header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#999999"))
    canvas_obj.drawString(2 * cm, 1 * cm, "Business Intelligence Report")
    canvas_obj.drawRightString(A4[0] - 2 * cm, 1 * cm, f"Page {doc.page}")
    canvas_obj.restoreState()


def generate_report(context: ReportContext) -> ReportResult:
    """Generate a complete PDF report."""
    output_dir = ensure_dir(context.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(output_dir, f"{context.vertical}_report_{timestamp}.pdf")

    styles = _build_styles()
    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )

    story = []

    # Cover
    story.append(Paragraph(context.business_name or "Business Intelligence Report", styles["Title"]))
    story.append(Paragraph(f"{context.vertical.title()} Vertical Analysis", styles["Subtitle"]))
    story.append(Paragraph(f"<b>Reporting Period:</b> {context.reporting_period}", styles["Body"]))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y')}", styles["Body"]))
    story.append(Spacer(1, 20))

    # Executive Summary
    story.append(Paragraph("Executive Summary", styles["H1"]))
    total_findings = len(context.findings)
    critical_count = sum(1 for f in context.findings if f.severity == FindingSeverity.CRITICAL)
    high_count = sum(1 for f in context.findings if f.severity == FindingSeverity.HIGH)

    summary_text = f"This report analyzes business data across {len(context.analysis_results)} data source(s). "
    summary_text += f"{total_findings} finding(s) were identified, including {critical_count} critical and {high_count} high-priority items. "
    summary_text += "The analysis covers sales performance, product analysis, profitability, and data quality assessment."

    story.append(Paragraph(summary_text, styles["Body"]))

    # KPI Summary
    story.append(Paragraph("Key Performance Indicators", styles["H2"]))
    all_kpis = {}
    for result in context.analysis_results:
        if result.available and result.kpis:
            entity_label = result.entity_type.replace("_", " ").title()
            source_label = result.source.replace("_", " ").title() if result.source else entity_label
            for k, v in result.kpis.items():
                # Include source filename to avoid overwriting KPIs from other files
                prefixed_key = f"{entity_label} ({source_label}) - {k.replace('_', ' ').title()}"
                all_kpis[prefixed_key] = v
    story.append(_kpi_table(all_kpis, styles))
    story.append(Spacer(1, 10))

    # Analysis sections
    for idx, result in enumerate(context.analysis_results):
        if not result.available:
            story.append(KeepTogether([
                Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]),
                Paragraph(f"Analysis was skipped because: {result.skip_reason}", styles["Body"]),
            ]))
            continue

        # Build section content — H1 header goes inside the first KeepTogether
        # to prevent orphaned headers at the bottom of pages
        section_elements = []
        first_block = True

        # KPIs (includes H1 header to prevent orphaning)
        if result.kpis:
            kpi_elements = [
                Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]),
                Paragraph("Key Metrics", styles["H2"]),
                _kpi_table(result.kpis, styles),
            ]
            section_elements.append(KeepTogether(kpi_elements))
            first_block = False
        else:
            # No KPIs — add H1 as part of the next available block
            pass

        # Charts
        # Filter charts by source slug (matching the prefix we added in main.py)
        safe_source = result.source.replace(" ", "_").replace("/", "_").replace(".", "_") if result.source else ""
        entity_charts = {k: v for k, v in context.chart_paths.items() if safe_source and k.startswith(safe_source)}
        if not entity_charts:
            # Fallback: match by entity_type in path (for backwards compat)
            entity_charts = {k: v for k, v in context.chart_paths.items() if result.entity_type in v}
        if entity_charts:
            chart_elements = []
            if first_block:
                chart_elements.append(Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]))
                first_block = False
            chart_elements.extend(_chart_section(entity_charts, styles, "Visual Analysis"))
            section_elements.extend(chart_elements)

        # Descriptive stats
        if result.descriptive_stats:
            stats_elements = []
            if first_block:
                stats_elements.append(Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]))
                first_block = False
            stats_elements.append(Paragraph("Statistical Summary", styles["H2"]))
            data = [["Column", "Count", "Sum", "Mean", "Median", "Min", "Max", "Std Dev"]]
            for col, stats in result.descriptive_stats.items():
                data.append([
                    Paragraph(col[:20], styles["StatCellLeft"]),
                    Paragraph(str(stats.get("count", "")), styles["StatCell"]),
                    Paragraph(format_number(stats.get("sum", 0), 2), styles["StatCell"]),
                    Paragraph(format_number(stats.get("mean", 0), 2), styles["StatCell"]),
                    Paragraph(format_number(stats.get("median", 0), 2), styles["StatCell"]),
                    Paragraph(format_number(stats.get("min", 0), 2), styles["StatCell"]),
                    Paragraph(format_number(stats.get("max", 0), 2), styles["StatCell"]),
                    Paragraph(format_number(stats.get("std", 0), 2), styles["StatCell"]),
                ])
            # Widened Sum/Count columns so large totals (e.g. revenue sums) don't
            # overflow into neighboring cells; total width still fits the page.
            table = Table(data, colWidths=[2.8 * cm, 1.4 * cm, 2.9 * cm, 1.9 * cm, 1.9 * cm, 1.7 * cm, 1.9 * cm, 1.9 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            stats_elements.append(table)
            section_elements.append(KeepTogether(stats_elements))
            section_elements.append(Spacer(1, 8))

        # Profitability
        if result.profitability:
            prof_elements = []
            if first_block:
                prof_elements.append(Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]))
                first_block = False
            prof_elements.append(Paragraph("Profitability", styles["H2"]))
            prof = result.profitability
            data = [
                ["Metric", "Value"],
                ["Total Revenue", format_currency(prof.get("total_revenue", 0))],
                ["Total Cost", format_currency(prof.get("total_cost", 0))],
                ["Gross Profit", format_currency(prof.get("gross_profit", 0))],
                ["Gross Margin %", format_percent(prof.get("gross_margin_pct"))],
                ["Avg Margin %", format_percent(prof.get("avg_margin_pct"))],
                ["Negative Margin Records", str(prof.get("negative_margin_count", 0))],
            ]
            table = Table(data, colWidths=[6 * cm, 8 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ]))
            prof_elements.append(table)
            section_elements.append(KeepTogether(prof_elements))
            section_elements.append(Spacer(1, 8))

        # Category/Product analysis
        cat_data = result.product_analysis or result.category_analysis
        if cat_data and cat_data.get("top"):
            dim_label = cat_data.get("dimension", result.entity_type)
            cat_elements = []
            if first_block:
                cat_elements.append(Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]))
                first_block = False
            cat_elements.append(Paragraph(f"Top {dim_label.title()}", styles["H2"]))
            data = [["Rank", "Name", "Value", "Share %"]]
            for i, item in enumerate(cat_data["top"][:10], 1):
                data.append([
                    str(i), item["name"][:30],
                    format_currency(item["value"]),
                    format_percent(item["pct"]),
                ])
            table = Table(data, colWidths=[1.5 * cm, 6 * cm, 4 * cm, 3 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ]))
            cat_elements.append(table)
            section_elements.append(KeepTogether(cat_elements))
            section_elements.append(Spacer(1, 8))

        # Time analysis
        if result.time_analysis and result.time_analysis.get("monthly_totals"):
            time_elements = []
            if first_block:
                time_elements.append(Paragraph(f"{result.entity_type.title()} Analysis", styles["H1"]))
                first_block = False
            time_elements.append(Paragraph("Monthly Performance", styles["H2"]))
            data = [["Month", "Total", "Change %"]]
            months = result.time_analysis.get("monthly_totals", {})
            prev_val = None
            for month, val in months.items():
                change = ""
                if prev_val and prev_val != 0:
                    change = format_percent(((val - prev_val) / abs(prev_val)) * 100)
                data.append([month, format_currency(val), change])
                prev_val = val
            table = Table(data, colWidths=[4 * cm, 5 * cm, 4 * cm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
            ]))
            time_elements.append(table)
            section_elements.append(KeepTogether(time_elements))
            section_elements.append(Spacer(1, 8))

        # Add all section elements to story
        story.extend(section_elements)

        # Page break between sections, but not after the last one
        if idx < len(context.analysis_results) - 1:
            story.append(PageBreak())

    # Findings section (includes all findings with full details: evidence,
    # comparison, recommended_action — no need for separate redundant sections)
    findings_elements = [Paragraph("Key Findings", styles["H1"])]
    findings_elements.extend(_findings_section(context.findings, styles))
    story.append(KeepTogether(findings_elements[:3]))  # Header + first 2 findings
    story.extend(findings_elements[3:])
    story.append(Spacer(1, 10))

    # Immediate Actions section
    actions_elements = _immediate_actions_section(context.findings, styles)
    if actions_elements:
        story.extend(actions_elements)

    # Data quality
    dq_elements = [Paragraph("Data Quality Assessment", styles["H1"])]
    dq_elements.extend(_quality_section(context.quality_reports, styles))
    story.append(KeepTogether(dq_elements[:3]))  # Header + first 2 quality items
    story.extend(dq_elements[3:])

    # AI commentary
    if context.ai_commentary:
        story.append(Paragraph("AI-Generated Commentary", styles["H1"]))
        story.append(Paragraph(context.ai_commentary, styles["Body"]))

    # Build
    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

    return ReportResult(pdf_path=pdf_path, context=context)
