"""Shared utility functions for the BI engine."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger("bi_engine")


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    bi_logger = logging.getLogger("bi_engine")
    bi_logger.handlers.clear()
    bi_logger.addHandler(handler)
    bi_logger.setLevel(level)
    return bi_logger


def normalize_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value.strip())


def normalize_column_name(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def is_null_like(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "nan", "null", "none", "n/a", "na", "-", "--"}
    return False


def safe_float(value) -> float | None:
    if is_null_like(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def format_currency(value: float | None, symbol: str = "") -> str:
    if value is None:
        return "N/A"
    return f"{symbol}{value:,.2f}"


def format_number(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}"


def format_percent(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
