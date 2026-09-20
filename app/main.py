"""Main entry point: orchestrates the full BI analysis pipeline."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from app.core.charts import generate_charts_for_result
from app.core.cleaner import clean_table
from app.core.column_mapper import apply_column_mappings, get_mapped_columns, map_columns
from app.core.findings import build_findings
from app.core.inspector import inspect_table
from app.core.loader import load_files
from app.core.models import AnalysisResult, DataQualityReport, LoadedTable, ReportContext, ReportResult
from app.core.report_generator import generate_report
from app.core.utils import setup_logging
from app.core.validator import validate_table
from app.ai.insights import generate_ai_commentary

logger = setup_logging()

VERTICAL_ANALYZERS = {
    "wholesale": ("app.verticals.wholesale.analysis", "analyze_wholesale"),
    "retail": ("app.verticals.retail.analysis", "analyze_retail"),
    "restaurant": ("app.verticals.restaurant.analysis", "analyze_restaurant"),
}

VERTICAL_REPORT_BUILDERS = {
    "wholesale": ("app.verticals.wholesale.report", "build_wholesale_report_context"),
    "retail": ("app.verticals.retail.report", "build_retail_report_context"),
    "restaurant": ("app.verticals.restaurant.report", "build_restaurant_report_context"),
}


def _import_analyzer(vertical: str):
    """Dynamically import the vertical analyzer function."""
    entry = VERTICAL_ANALYZERS.get(vertical)
    if not entry:
        raise ValueError(f"Unknown vertical: {vertical}. Available: {list(VERTICAL_ANALYZERS.keys())}")
    module_path, func_name = entry
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def _import_report_builder(vertical: str):
    """Dynamically import the vertical report builder function."""
    entry = VERTICAL_REPORT_BUILDERS.get(vertical)
    if not entry:
        raise ValueError(f"Unknown vertical: {vertical}")
    module_path, func_name = entry
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def process_table(table: LoadedTable) -> tuple:
    """Process a single table through the full pipeline.

    Returns (cleaned_df, quality_report, column_mappings, entity_hint).
    """
    # Step 0: Scan raw data for entity type hint (before cleaning removes section headers)
    entity_hint = _scan_entity_hint(table)

    # Step 1: Inspect and structurally clean
    table = inspect_table(table)

    # Step 2: Map columns to canonical names
    mappings = map_columns(table.df)
    quality = DataQualityReport()
    quality.column_mappings = mappings
    quality.source = table.label

    # Step 3: Apply column mappings
    mapped_df = apply_column_mappings(table.df, mappings)
    # After mapping, df columns are canonical names. Build col_map as canonical -> canonical.
    column_map = {}
    for m in mappings:
        if m.canonical and m.canonical in mapped_df.columns:
            column_map[m.canonical] = m.canonical

    # Step 4: Clean data (numerics, dates, text, duplicates)
    cleaned_df, quality = clean_table(LoadedTable(df=mapped_df, source=table.source, sheet_name=table.sheet_name), quality)

    # Step 5: Validate
    quality = validate_table(cleaned_df, quality)

    return cleaned_df, quality, column_map, entity_hint


def run_analysis(
    vertical: str,
    input_paths: list[str],
    business_name: str | None = None,
    output_dir: str = "reports",
    use_ai: bool = False,
    generate_pdf: bool = True,
) -> ReportResult:
    """Run the full BI analysis pipeline.

    Args:
        vertical: One of 'wholesale', 'retail', 'restaurant'.
        input_paths: List of file paths to process.
        business_name: Optional business name for the report.
        output_dir: Directory to save the report and charts.
        use_ai: Whether to enable AI commentary.
        generate_pdf: If False, skip chart and PDF generation (faster; for
            testing and programmatic use). The context is still returned.

    Returns:
        ReportResult containing the PDF path and full context.
    """
    errors = []
    business_name = business_name or "Business Intelligence Report"

    # Step 1: Load files
    logger.info(f"Loading {len(input_paths)} file(s)...")
    tables = load_files(input_paths)
    if not tables:
        return ReportResult(
            pdf_path="",
            context=None,
            success=False,
            errors=["No files could be loaded."],
        )

    analyzer_fn = _import_analyzer(vertical)

    all_quality_reports = []
    all_analysis_results = []
    all_findings = []
    all_chart_paths = {}

    assets_dir = str(Path(output_dir) / "assets")

    # Step 2: Process each table
    for idx, table in enumerate(tables):
        logger.info(f"Processing: {table.label}")
        try:
            cleaned_df, quality, column_map, entity_hint = process_table(table)

            # Determine entity type from the table (hint from raw data takes priority)
            entity_type = _detect_entity_type(cleaned_df, column_map, quality, vertical, entity_hint=entity_hint)
            quality.entity_type = entity_type

            all_quality_reports.append(quality)

            # Step 3: Run vertical-specific analysis
            analysis_result = analyzer_fn(
                cleaned_df, entity_type, table.label, column_map
            )

            # Step 4: Run anomaly detection
            from app.core.anomalies import detect_all_anomalies
            from app.core.analytics import compute_analytics

            # Merge generic analytics with vertical analysis
            generic_result = compute_analytics(cleaned_df, entity_type, table.label, column_map)
            if not analysis_result.descriptive_stats:
                analysis_result.descriptive_stats = generic_result.descriptive_stats
            if not analysis_result.time_analysis:
                analysis_result.time_analysis = generic_result.time_analysis
            if not analysis_result.category_analysis:
                analysis_result.category_analysis = generic_result.category_analysis
            if not analysis_result.product_analysis:
                analysis_result.product_analysis = generic_result.product_analysis
            if not analysis_result.profitability:
                analysis_result.profitability = generic_result.profitability

            analysis_result.anomalies = detect_all_anomalies(cleaned_df, analysis_result)

            # Step 5: Generate charts (skip if PDF not needed)
            # Use per-source subdirectory to avoid chart file collisions
            if generate_pdf:
                try:
                    safe_slug = table.label.replace(" ", "_").replace("/", "_").replace(".", "_")
                    table_assets_dir = str(Path(assets_dir) / f"{idx}_{safe_slug}")
                    charts = generate_charts_for_result(analysis_result, table_assets_dir)
                    # Prefix chart keys with source to avoid key collisions
                    prefixed_charts = {f"{safe_slug}_{k}": v for k, v in charts.items()}
                    all_chart_paths.update(prefixed_charts)
                except Exception as chart_err:
                    logger.warning(f"Chart generation failed for {table.label}: {chart_err}")

            all_analysis_results.append(analysis_result)

        except Exception as e:
            logger.error(f"Error processing {table.label}: {e}")
            errors.append(f"Error processing {table.label}: {e}")

    # Step 5b: Cross-file profitability (combined sales revenue vs purchases cost)
    combined_profit = _compute_combined_profitability(all_analysis_results)
    if combined_profit:
        all_analysis_results.append(combined_profit)

    # Step 6: Build findings
    all_findings = build_findings(all_analysis_results)

    # Step 7: Determine reporting period
    reporting_period = _get_reporting_period(all_quality_reports)

    # Step 8: AI commentary (optional)
    ai_commentary = ""
    if use_ai:
        try:
            ai_commentary = generate_ai_commentary(all_analysis_results, all_findings, vertical)
        except Exception as e:
            logger.warning(f"AI commentary failed: {e}")
            ai_commentary = ""

    # Step 9: Build report context
    report_builder_fn = _import_report_builder(vertical)
    context = report_builder_fn(
        business_name=business_name,
        reporting_period=reporting_period,
        quality_reports=all_quality_reports,
        analysis_results=all_analysis_results,
        findings=all_findings,
        chart_paths=all_chart_paths,
        ai_commentary=ai_commentary,
        output_dir=output_dir,
    )

    # Step 10: Generate PDF report (skip if not requested)
    if generate_pdf:
        logger.info("Generating PDF report...")
        result = generate_report(context)
        result.errors = errors
        logger.info(f"Report generated: {result.pdf_path}")
    else:
        result = ReportResult(pdf_path="", context=context, success=True, errors=errors)
        logger.info("Analysis complete (PDF generation skipped).")

    return result


def _scan_entity_hint(table) -> str | None:
    """Scan raw table data for entity type hints before cleaning.

    Accounting exports have section headers like 'Purchases', 'Inventory Asset',
    'Sales Receipt' that get removed during cleaning. This preserves that info.
    """
    import pandas as pd
    text = table.label.lower()
    # Scan first 30 rows of raw data
    raw = table.df.head(30)
    for col in raw.columns:
        vals = raw[col].dropna().astype(str).str.lower()
        text += " " + " ".join(vals)

    if "purchase" in text:
        return "purchases"
    if "inventory" in text or "stock" in text:
        return "inventory"
    if "sales receipt" in text or "sales receipt" in text:
        return "sales"
    return None


def _compute_combined_profitability(results: list[AnalysisResult]) -> AnalysisResult | None:
    """Compute cross-file profitability from sales revenue and purchases cost.

    Creates a synthetic AnalysisResult so the PDF/Streamlit can display it
    without any architecture changes.
    """
    total_revenue = 0.0
    total_cost = 0.0
    revenue_sources = []
    cost_sources = []

    for r in results:
        if not r.available:
            continue
        if r.entity_type == "sales" and r.kpis.get("total_revenue"):
            total_revenue += r.kpis["total_revenue"]
            revenue_sources.append(r.source)
        elif r.entity_type == "purchases":
            if r.kpis.get("total_purchases"):
                total_cost += r.kpis["total_purchases"]
                cost_sources.append(r.source)
            elif r.kpis.get("total_revenue"):
                total_cost += r.kpis["total_revenue"]
                cost_sources.append(r.source)

    if total_revenue <= 0 or total_cost <= 0:
        return None

    gross_profit = total_revenue - total_cost
    margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0

    result = AnalysisResult(
        entity_type="profitability",
        source="Combined Sales + Purchases",
    )
    result.available = True
    result.profitability = {
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(margin, 1),
        "cost_basis": "cross_file",
    }
    result.kpis = {
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(margin, 1),
    }
    return result


def _detect_entity_type(df, column_map: dict, quality: DataQualityReport, vertical: str = "", entity_hint: str | None = None) -> str:
    """Detect the entity type based on available columns.

    For restaurant vertical, 'products' entity type is mapped to 'menu'.
    entity_hint from raw data (pre-cleaning) takes priority for accounting exports.
    """
    # Raw hint from pre-cleaning scan (most reliable for accounting exports)
    if entity_hint:
        return entity_hint

    canonical_fields = set(column_map.keys())

    # Check the Type/Category column values for accounting-style exports
    # (QuickBooks etc.) where the same column names appear in sales, purchases,
    # and inventory files.
    type_col = None
    for candidate in ("category", "type"):
        if candidate in df.columns:
            type_col = candidate
            break
    if type_col is not None:
        type_values = " ".join(str(v).lower() for v in df[type_col].dropna().unique())
        if "purchase" in type_values:
            return "purchases"
        if "inventory" in type_values or "stock" in type_values:
            return "inventory"
        if "sales" in type_values or "receipt" in type_values:
            return "sales"

    # Accounting ledger: has cost (Debit) but no revenue → inventory
    if "cost" in canonical_fields and "revenue" not in canonical_fields:
        return "inventory"

    if "revenue" in canonical_fields or "invoice_id" in canonical_fields:
        return "sales"
    if "stock_level" in canonical_fields:
        return "inventory"
    if "supplier" in canonical_fields:
        return "purchases"
    if "product" in canonical_fields:
        if vertical == "restaurant":
            return "menu"
        return "products"
    if "customer" in canonical_fields:
        return "customers"

    # Fallback: use column types
    if quality.numeric_columns:
        return "sales"
    return "unknown"


def _get_reporting_period(quality_reports: list[DataQualityReport]) -> str:
    """Determine the reporting period from quality reports."""
    start_dates = []
    end_dates = []
    for qr in quality_reports:
        if qr.date_range[0]:
            start_dates.append(qr.date_range[0])
        if qr.date_range[1]:
            end_dates.append(qr.date_range[1])

    if start_dates and end_dates:
        return f"{min(start_dates)} to {max(end_dates)}"
    return "Not specified"


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Business Intelligence Automation Engine")
    parser.add_argument("vertical", choices=["wholesale", "retail", "restaurant"], help="Business vertical")
    parser.add_argument("files", nargs="+", help="Input file paths (CSV/XLSX)")
    parser.add_argument("--name", default=None, help="Business name")
    parser.add_argument("--output", default="reports", help="Output directory")
    parser.add_argument("--ai", action="store_true", help="Enable AI commentary")

    args = parser.parse_args()

    result = run_analysis(
        vertical=args.vertical,
        input_paths=args.files,
        business_name=args.name,
        output_dir=args.output,
        use_ai=args.ai,
    )

    if result.success:
        print(f"\nReport generated successfully: {result.pdf_path}")
        if result.errors:
            print(f"Warnings: {len(result.errors)} issue(s) encountered during processing.")
    else:
        print("Report generation failed.")
        for err in result.errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
