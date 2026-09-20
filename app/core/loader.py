"""File loading and sheet discovery for CSV, XLS, and XLSX files."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from app.core.models import LoadedTable
from app.core.utils import logger

SUPPORTED_EXTENSIONS = {".csv", ".xls", ".xlsx", ".xlsm"}


def is_supported(path: str) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def load_file(path: str) -> list[LoadedTable]:
    """Load a file and return one or more LoadedTable objects.

    For Excel files, each sheet becomes a separate table.
    For CSV, a single table is returned.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = p.suffix.lower()
    source_name = p.name

    if ext == ".csv":
        return [_load_csv(path, source_name)]
    elif ext in (".xls", ".xlsx", ".xlsm"):
        return _load_excel(path, source_name)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _load_csv(path: str, source: str) -> LoadedTable:
    """Load a CSV file with robust parsing. Always loads with header=None so the
    inspector can detect the actual header row consistently."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]
    separators = [None, ",", ";", "\t", "|"]

    last_error = None
    for enc in encodings:
        for sep in separators:
            try:
                read_kwargs = {"encoding": enc, "header": None, "dtype": object}
                if sep:
                    read_kwargs["sep"] = sep
                else:
                    read_kwargs["sep"] = None
                    read_kwargs["engine"] = "python"
                df = pd.read_csv(path, **read_kwargs)
                if df is not None and len(df.columns) > 1:
                    return LoadedTable(
                        df=df,
                        source=source,
                        original_rows=len(df),
                        notes=[f"Loaded with encoding={enc}, separator auto-detected"],
                    )
            except Exception as e:
                last_error = e
                continue

    # Last resort: basic read
    try:
        df = pd.read_csv(path, encoding="latin-1", header=None, dtype=object)
        return LoadedTable(
            df=df,
            source=source,
            original_rows=len(df),
            notes=["Loaded with fallback encoding=latin-1"],
        )
    except Exception as e:
        raise ValueError(f"Could not parse CSV file {source}: {e}") from e


def _load_excel(path: str, source: str) -> list[LoadedTable]:
    """Load all sheets from an Excel file."""
    try:
        xl = pd.ExcelFile(path, engine="openpyxl" if path.endswith("xlsx") else None)
    except Exception:
        try:
            xl = pd.ExcelFile(path)
        except Exception as e:
            raise ValueError(f"Could not open Excel file {source}: {e}") from e

    tables = []
    for sheet_name in xl.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=object)
            if df.empty or df.shape[0] == 0:
                logger.info(f"Sheet '{sheet_name}' in {source} is empty, skipping.")
                continue
            tables.append(
                LoadedTable(
                    df=df,
                    source=source,
                    sheet_name=sheet_name,
                    original_rows=len(df),
                )
            )
        except Exception as e:
            logger.warning(f"Could not read sheet '{sheet_name}' in {source}: {e}")
    return tables


def load_files(paths: list[str]) -> list[LoadedTable]:
    """Load multiple files and return all tables."""
    all_tables = []
    for path in paths:
        try:
            tables = load_file(path)
            all_tables.extend(tables)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
    return all_tables
