"""AI insights: converts structured analytical results into natural language commentary."""

from __future__ import annotations

from app.ai.provider import AIProvider, get_ai_provider
from app.core.models import AnalysisResult, Finding


def generate_ai_commentary(
    results: list[AnalysisResult],
    findings: list[Finding],
    vertical: str,
    ai_provider: AIProvider | None = None,
) -> str:
    """Generate management-level commentary from structured results.

    Only sends structured metrics to the AI, never raw data.
    """
    if ai_provider is None:
        ai_provider = get_ai_provider(use_ai=False)

    structured_data = _prepare_structured_data(results, findings)
    return ai_provider.generate_commentary(structured_data, vertical)


def _prepare_structured_data(results: list[AnalysisResult], findings: list[Finding]) -> dict:
    """Prepare a structured summary for AI processing."""
    all_kpis = {}
    profitability = {}
    finding_summaries = []

    for result in results:
        if not result.available:
            continue
        all_kpis.update(result.kpis)
        if result.profitability:
            profitability = result.profitability
        finding_summaries.extend([
            {"title": f.title, "severity": f.severity.value, "explanation": f.explanation}
            for f in result.findings
        ])

    finding_summaries.extend([
        {"title": f.title, "severity": f.severity.value, "explanation": f.explanation}
        for f in findings
    ])

    return {
        "kpis": all_kpis,
        "profitability": profitability,
        "findings": finding_summaries,
    }
