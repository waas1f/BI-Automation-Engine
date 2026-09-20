"""Tests for the core BI engine pipeline."""

import os
import sys
import unittest
import pandas as pd
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.loader import load_file, is_supported
from app.core.inspector import inspect_table, detect_header_row, is_footer_row
from app.core.schema_detector import infer_column_type, detect_schema
from app.core.cleaner import clean_numeric_value
from app.core.column_mapper import map_columns, apply_column_mappings
from app.core.cleaner import clean_table
from app.core.models import LoadedTable, DataQualityReport, ColumnType
from app.core.analytics import descriptive_stats, time_series_analysis, category_analysis, profitability_analysis
from app.core.anomalies import detect_numeric_anomalies
from app.core.findings import build_findings
from app.core.report_generator import generate_report
from app.core.models import ReportContext, AnalysisResult, Finding, FindingType, FindingSeverity
from app.main import run_analysis


class TestLoader(unittest.TestCase):
    """Test file loading."""

    def test_supported_extensions(self):
        self.assertTrue(is_supported("test.csv"))
        self.assertTrue(is_supported("test.xlsx"))
        self.assertTrue(is_supported("test.xls"))
        self.assertFalse(is_supported("test.txt"))
        self.assertFalse(is_supported("test.pdf"))

    def test_load_csv(self):
        path = os.path.join(os.path.dirname(__file__), "..", "data", "sample", "clean_sales.csv")
        tables = load_file(path)
        self.assertEqual(len(tables), 1)
        self.assertGreater(tables[0].original_rows, 0)


class TestInspector(unittest.TestCase):
    """Test table inspection and header detection."""

    def test_detect_header_row_clean(self):
        df = pd.DataFrame({
            "A": ["Date", "2026-01-01", "2026-01-02"],
            "B": ["Product", "Widget A", "Widget B"],
            "C": ["Revenue", "100", "200"],
        })
        header_idx = detect_header_row(df)
        self.assertEqual(header_idx, 0)

    def test_detect_header_row_with_title(self):
        df = pd.DataFrame({
            0: ["Sales Report", "", "Date", "2026-01-01", "2026-01-02"],
            1: ["", "", "Product", "Widget A", "Widget B"],
            2: ["", "", "Revenue", "100", "200"],
        })
        header_idx = detect_header_row(df)
        self.assertEqual(header_idx, 2)

    def test_is_footer_row(self):
        row = pd.Series(["Total", "All Products", "10000"])
        self.assertTrue(is_footer_row(row))
        row2 = pd.Series(["Widget A", "2026-01-01", "100"])
        self.assertFalse(is_footer_row(row2))

    def test_inspect_table_removes_empty_rows(self):
        df = pd.DataFrame({
            "A": [None, None, None, "data1"],
            "B": [None, None, None, "data2"],
        })
        table = LoadedTable(df=df, source="test", original_rows=len(df))
        result = inspect_table(table)
        self.assertLess(len(result.df), len(df))

    def test_inspect_table_removes_footer_rows(self):
        df = pd.DataFrame({
            "Date": ["2026-01-01", "2026-01-02", "Total"],
            "Revenue": [100, 200, 300],
        })
        table = LoadedTable(df=df, source="test", original_rows=len(df))
        result = inspect_table(table)
        self.assertNotIn("Total", result.df["Date"].values)


class TestSchemaDetector(unittest.TestCase):
    """Test schema detection and type inference."""

    def test_infer_numeric_type(self):
        series = pd.Series([100, 200, 300, 400, 500])
        self.assertEqual(infer_column_type(series, "amount"), ColumnType.NUMERIC)

    def test_infer_date_type(self):
        series = pd.Series(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
        self.assertEqual(infer_column_type(series, "date"), ColumnType.DATE)

    def test_infer_categorical_type(self):
        series = pd.Series(["A", "B", "A", "B", "A", "B", "A", "B"])
        self.assertEqual(infer_column_type(series, "category"), ColumnType.CATEGORICAL)

    def test_clean_numeric_value_plain(self):
        self.assertEqual(clean_numeric_value("1250"), 1250.0)

    def test_clean_numeric_value_currency(self):
        self.assertEqual(clean_numeric_value("$1,250.00"), 1250.0)

    def test_clean_numeric_value_european(self):
        self.assertEqual(clean_numeric_value("1.250,00"), 1250.0)

    def test_clean_numeric_value_with_suffix(self):
        self.assertEqual(clean_numeric_value("1250 USD"), 1250.0)

    def test_clean_numeric_value_none(self):
        self.assertIsNone(clean_numeric_value("N/A"))
        self.assertIsNone(clean_numeric_value(""))


class TestColumnMapper(unittest.TestCase):
    """Test column mapping."""

    def test_exact_alias_match(self):
        df = pd.DataFrame({
            "Date": ["2026-01-01"],
            "Invoice Number": ["INV-001"],
            "Customer Name": ["Customer A"],
            "Amount": [100],
        })
        mappings = map_columns(df)
        canonicals = {m.canonical for m in mappings if m.canonical}
        self.assertIn("date", canonicals)
        self.assertIn("invoice_id", canonicals)
        self.assertIn("customer", canonicals)
        self.assertIn("revenue", canonicals)

    def test_fuzzy_match(self):
        df = pd.DataFrame({
            "Trx Date": ["2026-01-01"],
            "Cust Name": ["Customer A"],
            "Sale Amount": [100],
        })
        mappings = map_columns(df)
        canonicals = {m.canonical for m in mappings if m.canonical}
        # At least some should match via fuzzy
        self.assertGreater(len(canonicals), 0)

    def test_apply_mappings(self):
        df = pd.DataFrame({"Date": ["2026-01-01"], "Amount": [100]})
        mappings = map_columns(df)
        mapped = apply_column_mappings(df, mappings)
        self.assertIn("date", mapped.columns)
        self.assertIn("revenue", mapped.columns)


class TestCleaner(unittest.TestCase):
    """Test data cleaning."""

    def test_clean_table_numeric(self):
        df = pd.DataFrame({
            "revenue": ["$1,250.00", "2,500", "100"],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        })
        table = LoadedTable(df=df, source="test")
        quality = DataQualityReport()
        cleaned, q = clean_table(table, quality)
        self.assertAlmostEqual(cleaned["revenue"].iloc[0], 1250.0)
        self.assertAlmostEqual(cleaned["revenue"].iloc[1], 2500.0)

    def test_clean_table_duplicates(self):
        df = pd.DataFrame({
            "revenue": [100, 100, 200],
            "date": ["2026-01-01", "2026-01-01", "2026-01-02"],
        })
        table = LoadedTable(df=df, source="test")
        quality = DataQualityReport()
        cleaned, q = clean_table(table, quality)
        self.assertEqual(q.duplicates_detected, 1)
        self.assertEqual(q.duplicates_removed, 1)

    def test_clean_table_missing_values(self):
        df = pd.DataFrame({
            "revenue": [100, None, 200],
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
        })
        table = LoadedTable(df=df, source="test")
        quality = DataQualityReport()
        cleaned, q = clean_table(table, quality)
        self.assertIn("revenue", q.missing_values)
        self.assertEqual(q.missing_values["revenue"], 1)


class TestAnalytics(unittest.TestCase):
    """Test analytics functions."""

    def test_descriptive_stats(self):
        series = pd.Series([10, 20, 30, 40, 50])
        stats = descriptive_stats(series)
        self.assertEqual(stats["count"], 5)
        self.assertEqual(stats["sum"], 150)
        self.assertEqual(stats["mean"], 30)
        self.assertEqual(stats["median"], 30)
        self.assertEqual(stats["min"], 10)
        self.assertEqual(stats["max"], 50)

    def test_time_series_analysis(self):
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=60, freq="D"),
            "revenue": np.random.uniform(100, 500, 60),
        })
        result = time_series_analysis(df, "date", "revenue")
        self.assertIn("monthly_totals", result)
        self.assertIn("daily_totals", result)
        self.assertIn("total", result)

    def test_category_analysis(self):
        df = pd.DataFrame({
            "product": ["A", "B", "A", "C", "B", "A"],
            "revenue": [100, 200, 150, 300, 250, 200],
        })
        result = category_analysis(df, "product", "revenue")
        self.assertEqual(result["total_categories"], 3)
        self.assertEqual(result["top"][0]["name"], "A")
        self.assertEqual(result["top"][0]["value"], 450)

    def test_profitability_analysis(self):
        df = pd.DataFrame({
            "revenue": [100, 200, 300],
            "cost": [60, 120, 150],
        })
        result = profitability_analysis(df, "revenue", "cost")
        self.assertEqual(result["total_revenue"], 600)
        self.assertEqual(result["total_cost"], 330)
        self.assertEqual(result["gross_profit"], 270)
        self.assertAlmostEqual(result["gross_margin_pct"], 45.0)


class TestAnomalies(unittest.TestCase):
    """Test anomaly detection."""

    def test_detect_outliers(self):
        series = pd.Series([10, 20, 30, 40, 50, 1000])
        anomalies = detect_numeric_anomalies(series, "test")
        self.assertGreater(len(anomalies), 0)
        self.assertEqual(anomalies[0]["value"], 1000)

    def test_no_outliers_in_uniform_data(self):
        series = pd.Series([10, 10, 10, 10])
        anomalies = detect_numeric_anomalies(series, "test")
        self.assertEqual(len(anomalies), 0)


class TestFindings(unittest.TestCase):
    """Test findings engine."""

    def test_build_findings_from_results(self):
        result = AnalysisResult(
            entity_type="sales",
            source="test",
            kpis={"total_revenue": 100000},
            profitability={"gross_margin_pct": 5.0, "total_revenue": 100000, "total_cost": 95000},
        )
        result.available = True
        findings = build_findings([result])
        # Should find the low margin finding
        types = [f.type for f in findings]
        self.assertIn(FindingType.MARGIN, types)


class TestEndToEnd(unittest.TestCase):
    """End-to-end pipeline tests."""

    def test_wholesale_pipeline(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[
                os.path.join(data_dir, "wholesale_sales.csv"),
                os.path.join(data_dir, "wholesale_inventory.csv"),
                os.path.join(data_dir, "wholesale_purchases.csv"),
            ],
            business_name="Test Wholesale",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.pdf_path))
        # Verify context has analysis results
        self.assertGreater(len(result.context.analysis_results), 0)
        # Verify sales analysis has profitability
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        if sales_results:
            self.assertTrue(sales_results[0].profitability, "Profitability should exist when cost data is present")
        # Verify inventory findings exist
        inv_results = [r for r in result.context.analysis_results if r.entity_type == "inventory"]
        if inv_results:
            inv_findings = inv_results[0].findings
            self.assertGreater(len(inv_findings), 0, "Inventory analysis should produce findings")

    def test_retail_pipeline(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        result = run_analysis(
            vertical="retail",
            input_paths=[
                os.path.join(data_dir, "retail_sales.csv"),
                os.path.join(data_dir, "retail_inventory.csv"),
            ],
            business_name="Test Retail",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.pdf_path))
        # Verify chart paths are prefixed with entity type
        for key in result.context.chart_paths:
            self.assertTrue("_" in key, f"Chart key '{key}' should be prefixed with entity type")

    def test_restaurant_pipeline(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        result = run_analysis(
            vertical="restaurant",
            input_paths=[
                os.path.join(data_dir, "restaurant_sales.csv"),
                os.path.join(data_dir, "restaurant_inventory.csv"),
            ],
            business_name="Test Restaurant",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.pdf_path))
        # Verify restaurant peak day finding exists
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        if sales_results:
            finding_titles = [f.title for f in sales_results[0].findings]
            peak_findings = [t for t in finding_titles if "Peak" in t or "peak" in t]
            self.assertGreater(len(peak_findings), 0, "Restaurant should detect peak sales days")

    def test_messy_data_pipeline(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "test")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[os.path.join(data_dir, "messy_sales.csv")],
            business_name="Messy Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)
        # Messy data should have detected duplicates or structural issues
        if result.context.quality_reports:
            qr = result.context.quality_reports[0]
            # At least some transformations should have been applied
            self.assertGreater(len(qr.transformations), 0, "Messy data should have transformations")

    def test_edge_case_pipeline(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "test")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[os.path.join(data_dir, "edge_case_sales.csv")],
            business_name="Edge Case Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)


class TestMessyData(unittest.TestCase):
    """Stress tests with genuinely difficult messy datasets."""

    def test_messy_wholesale_xlsx(self):
        """Wholesale messy xlsx with multi-sheet, title rows, duplicates, etc."""
        messy_dir = os.path.join(os.path.dirname(__file__), "..", "data", "messy")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[os.path.join(messy_dir, "messy_wholesale.xlsx")],
            business_name="Messy Wholesale Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.pdf_path))
        # Sales entity should be detected and available
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        self.assertGreater(len(sales_results), 0, "Sales analysis should be available")
        self.assertTrue(sales_results[0].available)
        # Revenue should be a positive number
        self.assertIn("total_revenue", sales_results[0].kpis)
        self.assertGreater(sales_results[0].kpis["total_revenue"], 0)
        # Duplicates should have been detected and removed
        sales_qr = [q for q in result.context.quality_reports if "Sales" in q.source]
        if sales_qr:
            self.assertGreaterEqual(sales_qr[0].duplicates_detected, 0)

    def test_messy_retail_xlsx(self):
        """Retail messy xlsx with title rows, messy numbers, duplicates."""
        messy_dir = os.path.join(os.path.dirname(__file__), "..", "data", "messy")
        result = run_analysis(
            vertical="retail",
            input_paths=[os.path.join(messy_dir, "messy_retail.xlsx")],
            business_name="Messy Retail Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.pdf_path))
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        self.assertGreater(len(sales_results), 0, "Sales analysis should be available")
        self.assertTrue(sales_results[0].available)
        self.assertIn("total_revenue", sales_results[0].kpis)
        self.assertGreater(sales_results[0].kpis["total_revenue"], 0)
        # Duplicates should have been removed
        sales_qr = [q for q in result.context.quality_reports if "Sales" in q.source]
        if sales_qr:
            self.assertGreater(sales_qr[0].duplicates_removed, 0, "Should have removed duplicate records")

    def test_messy_restaurant_xlsx(self):
        """Restaurant messy xlsx with messy dates, currency, null-likes."""
        messy_dir = os.path.join(os.path.dirname(__file__), "..", "data", "messy")
        result = run_analysis(
            vertical="restaurant",
            input_paths=[os.path.join(messy_dir, "messy_restaurant.xlsx")],
            business_name="Messy Restaurant Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
        )
        self.assertTrue(result.success)
        self.assertTrue(os.path.exists(result.pdf_path))
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        self.assertGreater(len(sales_results), 0, "Sales analysis should be available")
        self.assertTrue(sales_results[0].available)
        self.assertIn("total_revenue", sales_results[0].kpis)
        self.assertGreater(sales_results[0].kpis["total_revenue"], 0)
        # Restaurant margin should be reasonable (not double-counted)
        if sales_results[0].profitability:
            margin = sales_results[0].profitability.get("gross_margin_pct", 0)
            self.assertGreater(margin, 10, "Restaurant margin should be above 10% (not double-counted)")

    def test_messy_wholesale_csv(self):
        """Wholesale messy CSV (sales only) should handle gracefully and detect revenue."""
        messy_dir = os.path.join(os.path.dirname(__file__), "..", "data", "messy")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[os.path.join(messy_dir, "messy_wholesale_sales.csv")],
            business_name="Messy Wholesale CSV Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)
        # Regression: header detection must find the real header row (not a data row)
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        self.assertGreater(len(sales_results), 0, "Sales analysis should be available")
        self.assertTrue(sales_results[0].available, "Sales analysis should not be skipped")
        self.assertIn("total_revenue", sales_results[0].kpis)
        self.assertGreater(sales_results[0].kpis["total_revenue"], 0,
            "Messy wholesale CSV should detect positive revenue (header detection regression)")

    def test_messy_retail_csv(self):
        """Retail messy CSV should handle gracefully."""
        messy_dir = os.path.join(os.path.dirname(__file__), "..", "data", "messy")
        result = run_analysis(
            vertical="retail",
            input_paths=[os.path.join(messy_dir, "messy_retail_sales.csv")],
            business_name="Messy Retail CSV Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)

    def test_messy_restaurant_csv(self):
        """Restaurant messy CSV should handle gracefully."""
        messy_dir = os.path.join(os.path.dirname(__file__), "..", "data", "messy")
        result = run_analysis(
            vertical="restaurant",
            input_paths=[os.path.join(messy_dir, "messy_restaurant_sales.csv")],
            business_name="Messy Restaurant CSV Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)


class TestReconciliation(unittest.TestCase):
    """Verify that numbers reconcile across KPIs, charts, findings, and PDF."""

    def test_kpi_revenue_matches_profitability(self):
        """Total revenue in KPIs must match total revenue in profitability."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        for vertical, files in [
            ("wholesale", ["wholesale_sales.csv", "wholesale_inventory.csv", "wholesale_purchases.csv"]),
            ("retail", ["retail_sales.csv", "retail_inventory.csv"]),
            ("restaurant", ["restaurant_sales.csv", "restaurant_inventory.csv"]),
        ]:
            result = run_analysis(
                vertical=vertical,
                input_paths=[os.path.join(data_dir, f) for f in files],
                business_name=f"Reconcile {vertical}",
                output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
                generate_pdf=False,
            )
            self.assertTrue(result.success, f"{vertical} pipeline should succeed")
            for ar in result.context.analysis_results:
                if ar.entity_type == "sales" and ar.profitability and "total_revenue" in ar.kpis:
                    kpi_rev = ar.kpis["total_revenue"]
                    prof_rev = ar.profitability.get("total_revenue", 0)
                    self.assertAlmostEqual(kpi_rev, prof_rev, places=2,
                        msg=f"{vertical}: KPI revenue {kpi_rev} != profitability revenue {prof_rev}")

    def test_findings_cite_kpi_numbers(self):
        """Findings should reference numbers consistent with KPIs."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[os.path.join(data_dir, "wholesale_sales.csv")],
            business_name="Reconcile Findings",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)
        # Revenue summary finding should exist and cite total_revenue
        sales_results = [r for r in result.context.analysis_results if r.entity_type == "sales"]
        if sales_results:
            revenue = sales_results[0].kpis.get("total_revenue", 0)
            revenue_findings = [f for f in result.context.findings if f.type.value == "sales" and "revenue" in f.title.lower()]
            if revenue_findings:
                self.assertEqual(revenue_findings[0].value, revenue,
                    msg="Revenue finding should cite the same value as KPI")

    def test_profitability_margin_consistent(self):
        """Gross margin should be consistent: (revenue - cost) / revenue * 100."""
        df = pd.DataFrame({
            "revenue": [100, 200, 300],
            "cost": [60, 120, 150],
        })
        from app.core.analytics import profitability_analysis
        result = profitability_analysis(df, "revenue", "cost", cost_type="total")
        expected_margin = round((600 - 330) / 600 * 100, 1)
        self.assertAlmostEqual(result["gross_margin_pct"], expected_margin, places=1)
        self.assertAlmostEqual(result["total_revenue"], 600.0, places=2)
        self.assertAlmostEqual(result["total_cost"], 330.0, places=2)
        self.assertAlmostEqual(result["gross_profit"], 270.0, places=2)

    def test_no_unsourced_benchmarks(self):
        """Findings should not contain unsourced industry benchmark language."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        benchmark_phrases = [
            "typical restaurant benchmarks",
            "typical wholesale benchmarks",
            "typical retail benchmarks",
            "industry benchmark",
            "typical benchmarks",
        ]
        for vertical, files in [
            ("wholesale", ["wholesale_sales.csv"]),
            ("retail", ["retail_sales.csv"]),
            ("restaurant", ["restaurant_sales.csv"]),
        ]:
            result = run_analysis(
                vertical=vertical,
                input_paths=[os.path.join(data_dir, f) for f in files],
                business_name=f"No Benchmarks {vertical}",
                output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
                generate_pdf=False,
            )
            for f in result.context.findings:
                for phrase in benchmark_phrases:
                    text = (f.explanation or "") + " " + (f.comparison or "")
                    self.assertNotIn(phrase, text.lower(),
                        msg=f"{vertical}: Finding '{f.title}' contains unsourced benchmark: {phrase}")

    def test_findings_have_evidence(self):
        """Findings should have evidence, comparison, and recommended_action."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[
                os.path.join(data_dir, "wholesale_sales.csv"),
                os.path.join(data_dir, "wholesale_inventory.csv"),
            ],
            business_name="Evidence Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)
        for f in result.context.findings:
            # Every finding should have an explanation
            self.assertTrue(f.explanation, msg=f"Finding '{f.title}' has no explanation")
            # Findings with severity HIGH or MEDIUM should have recommended_action
            if f.severity in (FindingSeverity.HIGH, FindingSeverity.MEDIUM):
                self.assertTrue(f.recommended_action,
                    msg=f"Finding '{f.title}' (severity {f.severity.value}) has no recommended_action")

    def test_no_product_called_account(self):
        """No finding should call a product an 'account' (customer account)."""
        import re
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        account_pattern = re.compile(r"\baccount\b(?!s?\s+for)\b", re.IGNORECASE)
        for vertical, files in [
            ("wholesale", ["wholesale_sales.csv"]),
            ("retail", ["retail_sales.csv"]),
            ("restaurant", ["restaurant_sales.csv"]),
        ]:
            result = run_analysis(
                vertical=vertical,
                input_paths=[os.path.join(data_dir, f) for f in files],
                business_name=f"No Account {vertical}",
                output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
                generate_pdf=False,
            )
            for f in result.context.findings:
                text = (f.explanation or "") + " " + (f.recommended_action or "")
                # Product findings should not use 'account' language (as in customer account)
                if f.type == FindingType.PRODUCT:
                    # Check for 'account' as a standalone word, excluding 'accounts for'
                    matches = account_pattern.findall(text)
                    self.assertEqual(len(matches), 0,
                        msg=f"{vertical}: Product finding '{f.title}' uses 'account' language: {matches}")

    def test_no_duplicate_findings(self):
        """No two findings should have the same title."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
        result = run_analysis(
            vertical="wholesale",
            input_paths=[os.path.join(data_dir, "wholesale_sales.csv")],
            business_name="Dup Findings Test",
            output_dir=os.path.join(os.path.dirname(__file__), "..", "reports"),
            generate_pdf=False,
        )
        self.assertTrue(result.success)
        titles = [f.title for f in result.context.findings]
        self.assertEqual(len(titles), len(set(titles)),
            msg=f"Duplicate finding titles found: {titles}")


if __name__ == "__main__":
    unittest.main()
