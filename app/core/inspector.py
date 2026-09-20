"""Inspects raw loaded tables to detect header rows and table structure."""

from __future__ import annotations

import re

import pandas as pd

from app.core.models import LoadedTable
from app.core.utils import logger, normalize_column_name, normalize_text

# Patterns that suggest a row is a summary/footer/subtotal
FOOTER_PATTERNS = [
    re.compile(r"\btotal\b", re.IGNORECASE),
    re.compile(r"\bsubtotal\b", re.IGNORECASE),
    re.compile(r"\bgrand\s*total\b", re.IGNORECASE),
    re.compile(r"\bsum\b", re.IGNORECASE),
    re.compile(r"\baverage\b", re.IGNORECASE),
    re.compile(r"\bnet\b", re.IGNORECASE),
    re.compile(r"^---", re.IGNORECASE),
    re.compile(r"^={2,}"),
]

# Patterns that suggest a row is a title/metadata row (not data)
TITLE_KEYWORDS = ["report", "statement", "generated", "company", "page", "date:"]
EMPTY_THRESHOLD = 0.8


# Common header keywords that strongly indicate a header row
HEADER_KEYWORDS = {
    "date", "time", "invoice", "receipt", "order", "customer", "client", "product",
    "item", "category", "qty", "quantity", "price", "amount", "revenue", "cost",
    "discount", "supplier", "vendor", "stock", "reorder",
    "payment", "waiter", "server", "table", "name", "description", "code",
    "id", "number", "no", "unit", "value", "sales", "billing",
    "menu", "dish", "cuisine", "department", "group", "type", "level",
}


def detect_header_row(df: pd.DataFrame, max_scan: int = 20) -> int:
    """Find the most likely header row by scanning the first max_scan rows.

    A header row tends to have mostly non-null string values with low
    duplication across cells, and the row after it starts the actual data.
    """
    if df.empty:
        return 0

    scan_rows = min(max_scan, len(df))
    best_row = 0
    best_score = -1

    for i in range(scan_rows):
        row = df.iloc[i]
        non_null_count = row.notna().sum()
        total_cells = len(row)
        if total_cells == 0:
            continue

        # Header rows should have mostly non-null values
        fill_ratio = non_null_count / total_cells
        if fill_ratio < 0.5:
            continue

        # Check if values look like headers (strings, not too long, some variety)
        string_values = [str(v).strip() for v in row if pd.notna(v)]
        if not string_values:
            continue

        # Headers are typically shorter strings
        avg_len = sum(len(v) for v in string_values) / len(string_values)
        len_score = 1.0 if avg_len <= 40 else 0.3

        # Headers should have variety (not all the same value)
        unique_ratio = len(set(string_values)) / len(string_values) if string_values else 0

        # Penalize rows that look like totals or titles
        row_text = " ".join(string_values).lower()
        # Footer: multiple cells match footer patterns, or the row is mostly footer-like
        footer_cell_count = sum(
            1 for v in string_values
            if any(p.search(v.lower()) for p in FOOTER_PATTERNS)
        )
        is_footer = footer_cell_count >= 2  # At least 2 cells must match to be a footer
        is_title = any(kw in row_text for kw in TITLE_KEYWORDS)
        penalty = 0.0
        if is_footer:
            penalty += 0.5
        if is_title:
            penalty += 0.3

        # Bonus: header row values should match known header keywords
        header_keyword_count = sum(
            1 for v in string_values
            if normalize_column_name(v) in HEADER_KEYWORDS
            or any(kw in normalize_column_name(v) for kw in ["date", "name", "product", "item", "qty", "price", "amount", "cost", "revenue", "invoice", "receipt", "order", "customer", "category", "supplier", "stock", "reorder"])
        )
        keyword_bonus = min(header_keyword_count / max(len(string_values), 1), 1.0) * 1.5

        # Check if the next row has data (non-header-like)
        # A data row typically has numeric values or date-like values.
        # Look ahead up to 3 rows to skip section headers (e.g., "Inventory Asset")
        next_row_has_data = False
        next_row_is_data_like = False
        for j in range(1, min(4, len(df) - i)):
            next_row = df.iloc[i + j]
            next_non_null = next_row.notna().sum()
            if next_non_null / total_cells >= 0.5:
                next_row_has_data = True
                # Check if this row has numeric or date-like values (data-like, not header-like)
                next_values = [v for v in next_row if pd.notna(v)]
                numeric_count = 0
                for v in next_values:
                    s = str(v).strip()
                    try:
                        float(s.replace(",", "").replace("$", "").replace("€", "").replace("£", ""))
                        numeric_count += 1
                    except (ValueError, TypeError):
                        pass
                if len(next_values) > 0 and numeric_count / len(next_values) >= 0.3:
                    next_row_is_data_like = True
                break  # Found the first data row, stop looking

        # Check if current row is all strings (header-like) vs mixed (data-like)
        all_strings = all(isinstance(v, str) or pd.isna(v) for v in row)
        has_numeric = any(
            isinstance(v, (int, float)) and not pd.isna(v) for v in row
        )
        # Header rows should not have numeric values
        if has_numeric:
            penalty += 0.3

        score = (
            fill_ratio * 0.15
            + len_score * 0.15
            + unique_ratio * 0.15
            + (0.2 if next_row_has_data else 0)
            + (0.2 if next_row_is_data_like else 0)
            + keyword_bonus
            - penalty
        )

        if score > best_score:
            best_score = score
            best_row = i

    return best_row


def is_footer_row(row: pd.Series) -> bool:
    """Check if a row looks like a summary/subtotal/total row."""
    row_text = " ".join(str(v) for v in row if pd.notna(v)).strip()
    if not row_text:
        return False
    return any(p.search(row_text) for p in FOOTER_PATTERNS)


def is_mostly_empty(row: pd.Series, threshold: float = None) -> bool:
    """Check if a row is mostly empty/null."""
    if threshold is None:
        threshold = EMPTY_THRESHOLD
    non_null = row.notna().sum()
    return (non_null / len(row)) < (1 - threshold) if len(row) > 0 else True


def is_repeated_header(row: pd.Series, header_values: list[str]) -> bool:
    """Check if a row repeats the header values."""
    row_values = [str(v).strip().lower() for v in row if pd.notna(v)]
    header_set = set(v.lower() for v in header_values)
    if not row_values or not header_set:
        return False
    matches = sum(1 for v in row_values if v in header_set)
    return matches / len(row_values) >= 0.7


def inspect_table(table: LoadedTable) -> LoadedTable:
    """Inspect and structurally clean a table: detect headers, remove junk rows."""
    df = table.df.copy()
    notes = list(table.notes)

    if df.empty:
        table.notes.append("Table is empty.")
        return table

    # Step 1: Detect header row
    header_idx = detect_header_row(df)
    if header_idx > 0:
        notes.append(f"Header row detected at row {header_idx + 1} (0-indexed: {header_idx}).")
        df.columns = df.iloc[header_idx].astype(str).str.strip()
        df = df.drop(index=header_idx).reset_index(drop=True)
    else:
        # Use the first row as headers if they look like strings
        first_row = df.iloc[0]
        if all(isinstance(v, str) or pd.isna(v) for v in first_row):
            df.columns = [str(v).strip() if pd.notna(v) else f"unnamed_{i}" for i, v in enumerate(first_row)]
            df = df.drop(index=0).reset_index(drop=True)
            notes.append("First row used as header.")

    # Give unnamed columns a placeholder and deduplicate column names
    seen_names = {}
    new_cols = []
    for i, c in enumerate(df.columns):
        col = str(c).strip() if str(c).strip() else f"unnamed_{i}"
        if col in seen_names:
            seen_names[col] += 1
            col = f"{col}_{seen_names[col]}"
        else:
            seen_names[col] = 0
        new_cols.append(col)
    df.columns = new_cols

    # Step 2: Remove empty rows
    before_empty = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    # Also remove rows that are mostly empty (only 1 non-null value)
    mostly_empty_mask = df.apply(lambda r: r.notna().sum() <= 1, axis=1)
    df = df[~mostly_empty_mask].reset_index(drop=True)
    removed_empty = before_empty - len(df)
    if removed_empty > 0:
        notes.append(f"Removed {removed_empty} empty or near-empty rows.")

    # Step 3: Remove footer/summary rows
    before_footer = len(df)
    footer_mask = df.apply(is_footer_row, axis=1)
    df = df[~footer_mask].reset_index(drop=True)
    removed_footer = before_footer - len(df)
    if removed_footer > 0:
        notes.append(f"Removed {removed_footer} summary/footer/total rows.")

    # Step 4: Remove repeated header rows
    header_values = [str(c).strip() for c in df.columns]
    before_repeat = len(df)
    repeat_mask = df.apply(lambda r: is_repeated_header(r, header_values), axis=1)
    df = df[~repeat_mask].reset_index(drop=True)
    removed_repeat = before_repeat - len(df)
    if removed_repeat > 0:
        notes.append(f"Removed {removed_repeat} repeated header rows.")

    # Step 5: Remove completely empty columns
    before_cols = len(df.columns)
    df = df.dropna(axis=1, how="all")
    # Remove columns that are all the same value (likely index columns)
    removed_cols = before_cols - len(df.columns)
    if removed_cols > 0:
        notes.append(f"Removed {removed_cols} empty columns.")

    table.df = df
    table.notes = notes
    return table
