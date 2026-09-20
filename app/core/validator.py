"""Validation: generates data quality reports and checks data integrity."""

from __future__ import annotations

import pandas as pd

from app.core.models import ColumnType, DataQualityReport, LoadedTable
from app.core.schema_detector import detect_schema
from app.core.utils import logger


def validate_table(df: pd.DataFrame, quality: DataQualityReport) -> DataQualityReport:
    """Run validation checks on a cleaned table and populate the quality report."""
    if df.empty:
        quality.potential_issues.append("Table is empty after cleaning.")
        return quality

    schema = detect_schema(df)

    # Check for zero-revenue rows if revenue column exists
    for col in df.columns:
        if "revenue" in col.lower() or "amount" in col.lower() or "sales" in col.lower():
            if col in quality.numeric_columns:
                zero_count = (df[col] == 0).sum()
                if zero_count > 0:
                    quality.potential_issues.append(
                        f"Column '{col}' has {zero_count} zero-value records."
                    )
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    quality.potential_issues.append(
                        f"Column '{col}' has {negative_count} negative values (possible returns/refunds)."
                    )

    # Check for single-value columns (no variance)
    for col in df.columns:
        if col in quality.numeric_columns and df[col].notna().sum() > 1:
            if df[col].std() == 0:
                quality.potential_issues.append(
                    f"Column '{col}' has no variance (all values are the same)."
                )

    # Check for very high cardinality categorical columns
    for col in quality.categorical_columns:
        if col in df.columns:
            unique_count = df[col].nunique()
            if unique_count > 500:
                quality.potential_issues.append(
                    f"Column '{col}' has {unique_count} unique values (may not be truly categorical)."
                )

    # Note: date range is useful metadata, not a potential issue
    # It is displayed in the quality report table but not flagged as an issue.

    return quality


def summarize_quality(quality: DataQualityReport) -> dict:
    """Create a summary dict for report rendering."""
    return {
        "source": quality.source,
        "entity_type": quality.entity_type,
        "rows_before": quality.rows_before,
        "rows_after": quality.rows_after,
        "duplicates_detected": quality.duplicates_detected,
        "duplicates_removed": quality.duplicates_removed,
        "columns_before": quality.columns_before,
        "columns_after": quality.columns_after,
        "missing_values": quality.missing_values,
        "missing_percentage": quality.missing_percentage,
        "date_range": quality.date_range,
        "numeric_columns": quality.numeric_columns,
        "categorical_columns": quality.categorical_columns,
        "date_columns": quality.date_columns,
        "potential_issues": quality.potential_issues,
        "transformations": quality.transformations,
        "column_mappings": [
            {"raw": m.raw_name, "canonical": m.canonical, "confidence": m.confidence, "method": m.method}
            for m in quality.column_mappings
        ],
    }
