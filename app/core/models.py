"""Shared data structures used across the BI engine pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class ColumnType(str, Enum):
    DATE = "date"
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    TEXT = "text"
    IDENTIFIER = "identifier"
    UNKNOWN = "unknown"


class FindingType(str, Enum):
    MARGIN = "margin"
    SALES = "sales"
    CUSTOMER = "customer"
    PRODUCT = "product"
    INVENTORY = "inventory"
    SUPPLIER = "supplier"
    ANOMALY = "anomaly"
    TREND = "trend"
    DATA_QUALITY = "data_quality"
    OPPORTUNITY = "opportunity"
    RISK = "risk"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class EntityType(str, Enum):
    SALES = "sales"
    PRODUCTS = "products"
    CUSTOMERS = "customers"
    INVENTORY = "inventory"
    PURCHASES = "purchases"
    SUPPLIERS = "suppliers"
    MENU = "menu"
    ORDERS = "orders"


@dataclass
class LoadedTable:
    """A single table extracted from a file, after structural cleanup."""

    df: pd.DataFrame
    source: str
    sheet_name: str | None = None
    header_row: int = 0
    original_rows: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.sheet_name:
            return f"{self.source} ({self.sheet_name})"
        return self.source


@dataclass
class ColumnMapping:
    """Result of mapping a raw column to a canonical field."""

    raw_name: str
    canonical: str | None
    confidence: float
    method: str
    notes: str = ""


@dataclass
class DataQualityReport:
    """Summary of what happened during cleaning."""

    rows_before: int = 0
    rows_after: int = 0
    duplicates_detected: int = 0
    duplicates_removed: int = 0
    columns_before: int = 0
    columns_after: int = 0
    missing_values: dict[str, int] = field(default_factory=dict)
    missing_percentage: dict[str, float] = field(default_factory=dict)
    columns_transformed: list[str] = field(default_factory=list)
    date_range: tuple[str | None, str | None] = (None, None)
    numeric_columns: list[str] = field(default_factory=list)
    categorical_columns: list[str] = field(default_factory=list)
    date_columns: list[str] = field(default_factory=list)
    potential_issues: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    column_mappings: list[ColumnMapping] = field(default_factory=list)
    entity_type: str = ""
    source: str = ""


@dataclass
class Finding:
    """A structured, evidence-based business finding."""

    type: FindingType
    severity: FindingSeverity
    title: str
    metric: str = ""
    value: Any = None
    comparison: str = ""
    explanation: str = ""
    evidence: str = ""
    recommended_action: str = ""


@dataclass
class AnalysisResult:
    """Container for all computed analytics for one entity/table."""

    entity_type: str
    source: str
    descriptive_stats: dict[str, dict] = field(default_factory=dict)
    time_analysis: dict = field(default_factory=dict)
    category_analysis: dict = field(default_factory=dict)
    product_analysis: dict = field(default_factory=dict)
    profitability: dict = field(default_factory=dict)
    anomalies: list[dict] = field(default_factory=list)
    kpis: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    available: bool = True
    skip_reason: str = ""


@dataclass
class ReportContext:
    """Everything needed to generate a report."""

    vertical: str
    business_name: str
    reporting_period: str
    quality_reports: list[DataQualityReport]
    analysis_results: list[AnalysisResult]
    findings: list[Finding]
    chart_paths: dict[str, str] = field(default_factory=dict)
    ai_commentary: str = ""
    output_dir: str = "reports"


@dataclass
class ReportResult:
    """Result of the full pipeline run."""

    pdf_path: str
    context: ReportContext
    success: bool = True
    errors: list[str] = field(default_factory=list)
