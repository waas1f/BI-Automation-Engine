"""Schema detection: infer column types from data."""

from __future__ import annotations

import re
from datetime import datetime

import pandas as pd

from app.core.models import ColumnType
from app.core.utils import logger

# Common date formats to try
DATE_FORMATS = [
    "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
    "%m/%d/%Y", "%m-%d-%Y",
    "%d/%m/%y", "%m/%d/%y",
    "%d-%b-%Y", "%d-%b-%y",
    "%d %b %Y", "%d %B %Y",
    "%b %d %Y", "%B %d %Y",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
    "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S",
]

# Patterns for detecting numeric strings with currency/thousands separators
CURRENCY_PATTERN = re.compile(
    r"^\s*[$€£¥₹]?\s*[-]?\s*[\d,]+(\.\d+)?\s*(USD|EUR|GBP|JPY|INR|TL|TRY)?\s*$",
    re.IGNORECASE,
)
EUROPEAN_NUM_PATTERN = re.compile(
    r"^\s*[$€£¥₹]?\s*[-]?\s*[\d.]+,\d+\s*(USD|EUR|GBP|JPY|INR|TL|TRY)?\s*$",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"^\s*[-]?[\d,.]+%\s*$")


def try_parse_date(value) -> datetime | None:
    """Try to parse a value as a date using common formats."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, (int, float)):
        # Only treat as Excel serial date if it's a reasonable date serial number
        # Excel dates: 1 = 1899-12-31, 40000+ = ~2009+, 60000+ = ~2064
        # Avoid treating small integers (1-100) as dates unless they're in a realistic date range
        if 30000 < value < 60000:
            try:
                return pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(value))
            except Exception:
                return None
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return pd.to_datetime(s, errors="coerce").to_pydatetime() if not pd.isna(pd.to_datetime(s, errors="coerce")) else None
    except Exception:
        return None


def looks_like_date_series(series: pd.Series, sample_size: int = 50) -> bool:
    """Check if a series looks like it contains dates."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    sample = non_null.head(sample_size)
    parsed_count = 0
    for v in sample:
        if try_parse_date(v) is not None:
            parsed_count += 1
    return parsed_count / len(sample) >= 0.7


def looks_like_numeric_series(series: pd.Series, sample_size: int = 50) -> bool:
    """Check if a series looks numeric, including currency/percentage strings."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    sample = non_null.head(sample_size)
    numeric_count = 0
    for v in sample:
        if isinstance(v, (int, float)) and not pd.isna(v):
            numeric_count += 1
        else:
            s = str(v).strip()
            if CURRENCY_PATTERN.match(s) or EUROPEAN_NUM_PATTERN.match(s) or PERCENT_PATTERN.match(s):
                numeric_count += 1
            else:
                try:
                    float(s.replace(",", ""))
                    numeric_count += 1
                except (ValueError, TypeError):
                    pass
    return numeric_count / len(sample) >= 0.7


def looks_like_identifier(series: pd.Series, sample_size: int = 50) -> bool:
    """Check if a series looks like an identifier (invoice numbers, IDs)."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return False
    sample = non_null.head(sample_size)
    # Identifiers: strings with mixed alphanumerics, high cardinality, short-ish
    if len(sample) == 0:
        return False
    unique_ratio = sample.nunique() / len(sample)
    avg_len = sample.astype(str).str.len().mean()
    has_digit = sample.astype(str).str.contains(r"\d", regex=True).any()
    has_letter = sample.astype(str).str.contains(r"[a-zA-Z]", regex=True).any()
    # High cardinality + short-ish strings + mixed alphanumeric
    return unique_ratio > 0.8 and avg_len < 30 and has_digit and has_letter


def infer_column_type(series: pd.Series, col_name: str) -> ColumnType:
    """Infer the most likely type for a column."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return ColumnType.UNKNOWN

    # Check for date first (before numeric, since dates can look numeric)
    if looks_like_date_series(series):
        return ColumnType.DATE

    if looks_like_numeric_series(series):
        return ColumnType.NUMERIC

    if looks_like_identifier(series):
        return ColumnType.IDENTIFIER

    # Low cardinality = categorical
    unique_count = non_null.nunique()
    total_count = len(non_null)
    if total_count > 0 and unique_count / total_count < 0.5 and unique_count < 100:
        return ColumnType.CATEGORICAL

    return ColumnType.TEXT


def detect_schema(df: pd.DataFrame) -> dict[str, ColumnType]:
    """Detect column types for all columns in a dataframe."""
    schema = {}
    for col in df.columns:
        schema[col] = infer_column_type(df[col], col)
    return schema
