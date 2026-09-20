"""Data cleaning: numeric parsing, date parsing, text normalization, duplicate handling."""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from app.core.models import ColumnType, DataQualityReport, LoadedTable
from app.core.schema_detector import detect_schema, looks_like_date_series, looks_like_numeric_series, try_parse_date
from app.core.utils import is_null_like, logger, normalize_column_name, normalize_text

CURRENCY_SYMBOLS = r"[$€£¥₹]"
NUMERIC_SUFFIXES = r"(USD|EUR|GBP|JPY|INR|TL|TRY)"


def clean_numeric_value(value) -> float | None:
    """Parse a numeric value from various string formats."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s or is_null_like(s):
        return None

    # Remove currency symbols and suffixes
    s = re.sub(CURRENCY_SYMBOLS, "", s)
    s = re.sub(NUMERIC_SUFFIXES, "", s, flags=re.IGNORECASE)
    s = s.strip()

    # Handle percentages
    is_percent = s.endswith("%")
    if is_percent:
        s = s.rstrip("%").strip()

    # Detect European format (1.250,00) vs American format (1,250.00)
    if "," in s and "." in s:
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            # European format: 1.250,00
            s = s.replace(".", "").replace(",", ".")
        else:
            # American format: 1,250.00 — comma is thousands separator
            s = s.replace(",", "")
    elif "," in s:
        # Only commas: could be thousands separator or decimal
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            # Likely decimal: 1250,50
            s = s.replace(",", ".")
        else:
            # Thousands separator: 1,250
            s = s.replace(",", "")

    # Handle space-separated thousands: 1 250
    s = re.sub(r"(\d)\s+(\d)", r"\1\2", s)

    try:
        result = float(s)
        if is_percent:
            result = result / 100
        return result
    except (ValueError, TypeError):
        return None


def clean_date_value(value) -> datetime | None:
    """Parse a date value from various formats."""
    return try_parse_date(value)


def clean_text_value(value) -> str:
    """Normalize a text/categorical value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    # Normalize whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_categorical(series: pd.Series) -> tuple[pd.Series, list[str]]:
    """Normalize categorical values: trim, normalize case, report potential duplicates."""
    transformations = []
    original = series.copy()

    # Trim whitespace
    series = series.apply(lambda v: normalize_text(str(v)) if pd.notna(v) else v)

    # Detect potential duplicate entities (case-insensitive matches)
    non_null = series.dropna()
    if len(non_null) > 0:
        lower_values = non_null.astype(str).str.lower().str.strip()
        value_counts = lower_values.value_counts()
        # Find values that appear with different casings
        original_unique = non_null.astype(str).nunique()
        normalized_unique = lower_values.nunique()
        if original_unique > normalized_unique:
            diff = original_unique - normalized_unique
            transformations.append(
                f"Potential duplicate entities detected: {diff} values may be case variants of each other."
            )

    return series, transformations


def clean_table(table: LoadedTable, quality: DataQualityReport) -> tuple[pd.DataFrame, DataQualityReport]:
    """Clean a table: parse numerics, dates, normalize text, handle duplicates."""
    df = table.df.copy()
    quality.rows_before = len(df)
    quality.columns_before = len(df.columns)
    quality.source = table.label

    transformations = list(quality.transformations)

    # Detect schema
    schema = detect_schema(df)

    for col in df.columns:
        col_type = schema.get(col, ColumnType.UNKNOWN)
        raw_col = col

        if col_type == ColumnType.NUMERIC:
            before_non_null = df[col].notna().sum()
            df[col] = df[col].apply(clean_numeric_value)
            after_non_null = df[col].notna().sum()
            if after_non_null < before_non_null:
                transformations.append(
                    f"Column '{raw_col}': {before_non_null - after_non_null} values could not be parsed as numeric."
                )
            if col not in quality.numeric_columns:
                quality.numeric_columns.append(col)

        elif col_type == ColumnType.DATE:
            before_non_null = df[col].notna().sum()
            # Check for ambiguous date formats before parsing
            non_null_dates = df[col].dropna()
            ambiguous_count = 0
            for v in non_null_dates.head(100):
                s = str(v).strip()
                # Check for DD/MM/YYYY or MM/DD/YYYY patterns where both <= 12
                parts = re.split(r"[/\-]", s)
                if len(parts) == 3:
                    try:
                        p1, p2 = int(parts[0]), int(parts[1])
                        if p1 <= 12 and p2 <= 12:
                            ambiguous_count += 1
                    except ValueError:
                        pass
            if ambiguous_count > 0:
                quality.potential_issues.append(
                    f"Column '{raw_col}': {ambiguous_count} date values have ambiguous day/month ordering (e.g., 01/02/2026). Parsed day-first by default."
                )

            df[col] = df[col].apply(clean_date_value)
            after_non_null = df[col].notna().sum()
            if after_non_null < before_non_null:
                transformations.append(
                    f"Column '{raw_col}': {before_non_null - after_non_null} values could not be parsed as dates."
                )
            if col not in quality.date_columns:
                quality.date_columns.append(col)
            # Update date range
            valid_dates = df[col].dropna()
            if len(valid_dates) > 0:
                min_date = valid_dates.min()
                max_date = valid_dates.max()
                if isinstance(min_date, datetime):
                    quality.date_range = (min_date.strftime("%Y-%m-%d"), max_date.strftime("%Y-%m-%d"))

        elif col_type in (ColumnType.CATEGORICAL, ColumnType.TEXT):
            df[col], cat_transforms = normalize_categorical(df[col])
            transformations.extend(cat_transforms)
            if col_type == ColumnType.CATEGORICAL and col not in quality.categorical_columns:
                quality.categorical_columns.append(col)

    # Detect duplicates
    duplicates = df.duplicated()
    dup_count = duplicates.sum()
    quality.duplicates_detected = int(dup_count)
    if dup_count > 0:
        transformations.append(f"Detected {dup_count} duplicate rows.")
        df = df.drop_duplicates().reset_index(drop=True)
        quality.duplicates_removed = int(dup_count)

    # Missing values
    for col in df.columns:
        missing = int(df[col].isna().sum())
        if missing > 0:
            pct = (missing / len(df)) * 100 if len(df) > 0 else 0
            quality.missing_values[col] = missing
            quality.missing_percentage[col] = round(pct, 1)
            if pct > 50:
                quality.potential_issues.append(
                    f"Column '{col}' has {pct:.1f}% missing values."
                )

    quality.rows_after = len(df)
    quality.columns_after = len(df.columns)
    quality.transformations = transformations

    return df, quality
