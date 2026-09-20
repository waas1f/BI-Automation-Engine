"""Generic analytics engine: descriptive stats, time-series, category analysis, profitability."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from app.core.models import AnalysisResult
from app.core.utils import logger, safe_float


def descriptive_stats(series: pd.Series) -> dict:
    """Compute descriptive statistics for a numeric series."""
    clean = series.dropna()
    if len(clean) == 0:
        return {}
    return {
        "count": int(clean.count()),
        "sum": round(float(clean.sum()), 2),
        "mean": round(float(clean.mean()), 2),
        "median": round(float(clean.median()), 2),
        "min": round(float(clean.min()), 2),
        "max": round(float(clean.max()), 2),
        "std": round(float(clean.std()), 2) if len(clean) > 1 else 0.0,
        "q25": round(float(clean.quantile(0.25)), 2),
        "q75": round(float(clean.quantile(0.75)), 2),
    }


def time_series_analysis(df: pd.DataFrame, date_col: str, value_col: str) -> dict:
    """Compute time-based aggregations and trends."""
    result = {}
    if date_col not in df.columns or value_col not in df.columns:
        return result

    temp = df[[date_col, value_col]].dropna().copy()
    if temp.empty:
        return result

    temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
    temp = temp.dropna(subset=[date_col])

    if temp.empty:
        return result

    # Daily totals
    daily = temp.groupby(temp[date_col].dt.date)[value_col].sum()
    result["daily_totals"] = {str(k): round(float(v), 2) for k, v in daily.items()}

    # Monthly totals
    monthly = temp.groupby(temp[date_col].dt.to_period("M"))[value_col].sum()
    result["monthly_totals"] = {str(k): round(float(v), 2) for k, v in monthly.items()}

    # Weekly totals
    weekly = temp.groupby(temp[date_col].dt.to_period("W"))[value_col].sum()
    result["weekly_totals"] = {str(k): round(float(v), 2) for k, v in weekly.items()}

    # Period-over-period change
    if len(monthly) >= 2:
        latest = float(monthly.iloc[-1])
        prev = float(monthly.iloc[-2])
        if prev != 0:
            change_pct = ((latest - prev) / abs(prev)) * 100
            result["latest_month"] = round(latest, 2)
            result["previous_month"] = round(prev, 2)
            result["mom_change_pct"] = round(change_pct, 1)
        else:
            result["latest_month"] = round(latest, 2)
            result["previous_month"] = round(prev, 2)
            result["mom_change_pct"] = None

    # Overall trend (linear regression slope)
    if len(daily) >= 3:
        daily_values = daily.values.astype(float)
        x = np.arange(len(daily_values))
        try:
            slope = np.polyfit(x, daily_values, 1)[0]
            result["trend_slope"] = round(float(slope), 2)
            if slope > 0:
                result["trend_direction"] = "increasing"
            elif slope < 0:
                result["trend_direction"] = "decreasing"
            else:
                result["trend_direction"] = "stable"
        except Exception:
            pass

    # Peak day
    if len(daily) > 0:
        peak_day = daily.idxmax()
        peak_value = daily.max()
        result["peak_day"] = str(peak_day)
        result["peak_value"] = round(float(peak_value), 2)

    result["total"] = round(float(temp[value_col].sum()), 2)
    result["avg_daily"] = round(float(daily.mean()), 2) if len(daily) > 0 else 0

    return result


def category_analysis(df: pd.DataFrame, category_col: str, value_col: str, top_n: int = 10, dimension: str = "") -> dict:
    """Compute category-based breakdowns and concentration."""
    result = {}
    if category_col not in df.columns or value_col not in df.columns:
        return result

    temp = df[[category_col, value_col]].dropna().copy()
    if temp.empty:
        return result

    totals = temp.groupby(category_col)[value_col].sum().sort_values(ascending=False)
    total_sum = float(totals.sum())

    top = totals.head(top_n)
    result["top"] = [
        {"name": str(k), "value": round(float(v), 2), "pct": round(float(v / total_sum * 100), 1) if total_sum != 0 else 0}
        for k, v in top.items()
    ]

    result["dimension"] = dimension

    result["total_categories"] = int(len(totals))
    result["total_value"] = round(total_sum, 2)

    # Concentration: top 3 share
    if len(totals) >= 3:
        top3_share = float(totals.head(3).sum() / total_sum * 100) if total_sum != 0 else 0
        result["top3_concentration"] = round(top3_share, 1)

    # HHI (Herfindahl-Hirschman Index) for concentration
    if total_sum != 0 and len(totals) > 0:
        shares = (totals / total_sum) ** 2
        hhi = float(shares.sum())
        result["concentration_hhi"] = round(hhi, 4)
        if hhi > 0.25:
            result["concentration_level"] = "high"
        elif hhi > 0.15:
            result["concentration_level"] = "moderate"
        else:
            result["concentration_level"] = "low"

    return result


def profitability_analysis(
    df: pd.DataFrame,
    revenue_col: str,
    cost_col: str,
    quantity_col: str | None = None,
    cost_type: str = "total",
) -> dict:
    """Compute profitability metrics if revenue and cost data are available.

    Args:
        cost_type: "total" if cost_col is already a line-item total cost,
                   "unit" if cost_col is a per-unit cost (requires quantity_col
                   to compute total cost).
    """
    result = {}
    if revenue_col not in df.columns or cost_col not in df.columns:
        return result

    temp = df[[revenue_col, cost_col]].dropna().copy()
    if temp.empty:
        return result

    # Compute total cost based on cost_type
    if cost_type == "unit" and quantity_col and quantity_col in df.columns:
        temp[quantity_col] = df[quantity_col]
        temp = temp.dropna(subset=[quantity_col])
        temp["total_cost"] = temp[cost_col] * temp[quantity_col]
        cost_values = temp["total_cost"]
        result["cost_basis"] = "unit_cost_x_quantity"
    else:
        cost_values = temp[cost_col]
        result["cost_basis"] = "total_cost"

    total_revenue = float(temp[revenue_col].sum())
    total_cost = float(cost_values.sum())
    gross_profit = total_revenue - total_cost
    gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else None

    result["total_revenue"] = round(total_revenue, 2)
    result["total_cost"] = round(total_cost, 2)
    result["gross_profit"] = round(gross_profit, 2)
    result["gross_margin_pct"] = round(gross_margin, 1) if gross_margin is not None else None

    # Per-record margins (use total cost for accuracy)
    if cost_type == "unit" and quantity_col and quantity_col in temp.columns:
        temp["profit"] = temp[revenue_col] - temp["total_cost"]
    else:
        temp["profit"] = temp[revenue_col] - temp[cost_col]
    temp["margin_pct"] = temp.apply(
        lambda r: (r["profit"] / r[revenue_col] * 100) if r[revenue_col] > 0 else None, axis=1
    )

    result["avg_margin_pct"] = round(float(temp["margin_pct"].mean()), 1) if temp["margin_pct"].notna().any() else None
    result["negative_margin_count"] = int((temp["profit"] < 0).sum())

    return result


def compute_analytics(
    df: pd.DataFrame,
    entity_type: str,
    source: str,
    column_map: dict[str, str] | None = None,
) -> AnalysisResult:
    """Run generic analytics on a cleaned dataframe.

    column_map maps canonical names to actual column names in df.
    """
    result = AnalysisResult(entity_type=entity_type, source=source)
    if df.empty:
        result.available = False
        result.skip_reason = "No data available after cleaning."
        return result

    col_map = column_map or {}
    # Build reverse map: canonical -> actual column name in df
    actual = {}
    for canonical, raw_name in col_map.items():
        if raw_name in df.columns:
            actual[canonical] = raw_name

    # Descriptive stats for all numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        result.descriptive_stats[col] = descriptive_stats(df[col])

    # Time analysis
    date_col = actual.get("date")
    value_col = actual.get("revenue") or actual.get("quantity")
    if date_col and value_col:
        result.time_analysis = time_series_analysis(df, date_col, value_col)

    # Category analysis
    cat_col = actual.get("product") or actual.get("category") or actual.get("customer")
    if cat_col and value_col:
        # Determine dimension from which column was found
        if actual.get("customer") and cat_col == actual["customer"]:
            dim = "customer"
        elif actual.get("product") and cat_col == actual["product"]:
            dim = "product"
        elif actual.get("supplier") and cat_col == actual["supplier"]:
            dim = "supplier"
        else:
            dim = "category"
        result.category_analysis = category_analysis(df, cat_col, value_col, dimension=dim)

    # Profitability
    revenue_col = actual.get("revenue")
    cost_col = actual.get("cost") or actual.get("total_cost") or actual.get("unit_cost")
    qty_col = actual.get("quantity")
    if revenue_col and cost_col:
        # Determine cost type from which canonical field was used
        unit_cost_col = actual.get("unit_cost")
        if unit_cost_col and unit_cost_col == cost_col:
            cost_type = "unit"
        else:
            cost_type = "total"
        result.profitability = profitability_analysis(df, revenue_col, cost_col, quantity_col=qty_col, cost_type=cost_type)

    # KPIs
    result.kpis = _compute_kpis(df, actual, result)

    return result


def _compute_kpis(df: pd.DataFrame, actual: dict, result: AnalysisResult) -> dict:
    """Compute standard KPIs from available data."""
    kpis = {}

    if "revenue" in actual:
        revenue = df[actual["revenue"]].dropna()
        if len(revenue) > 0:
            kpis["total_revenue"] = round(float(revenue.sum()), 2)
            kpis["avg_transaction_value"] = round(float(revenue.mean()), 2)
            kpis["transaction_count"] = int(len(revenue))

    if "quantity" in actual:
        qty = df[actual["quantity"]].dropna()
        if len(qty) > 0:
            kpis["total_units"] = round(float(qty.sum()), 2)

    if "invoice_id" in actual:
        kpis["unique_invoices"] = int(df[actual["invoice_id"]].nunique())

    if "customer" in actual:
        kpis["unique_customers"] = int(df[actual["customer"]].nunique())

    if "product" in actual:
        kpis["unique_products"] = int(df[actual["product"]].nunique())

    if result.profitability:
        kpis["gross_margin"] = result.profitability.get("gross_margin_pct")

    return kpis
