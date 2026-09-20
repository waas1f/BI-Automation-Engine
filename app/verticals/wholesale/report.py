"""Wholesale report: assembles the report context for wholesale vertical."""

from __future__ import annotations

from app.core.models import ReportContext
from app.verticals.wholesale.config import WHOLESALE_REPORT_SECTIONS


def build_wholesale_report_context(
    business_name: str,
    reporting_period: str,
    quality_reports: list,
    analysis_results: list,
    findings: list,
    chart_paths: dict,
    ai_commentary: str = "",
    output_dir: str = "reports",
) -> ReportContext:
    """Build the report context for the wholesale vertical."""
    return ReportContext(
        vertical="wholesale",
        business_name=business_name,
        reporting_period=reporting_period,
        quality_reports=quality_reports,
        analysis_results=analysis_results,
        findings=findings,
        chart_paths=chart_paths,
        ai_commentary=ai_commentary,
        output_dir=output_dir,
    )
