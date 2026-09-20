"""Retail-specific analysis: KPIs, product/category analysis, inventory, profitability."""

from __future__ import annotations

import pandas as pd

from app.core.models import AnalysisResult, EntityType, Finding, FindingSeverity, FindingType
from app.core.utils import format_currency, format_percent


def analyze_retail(
    df: pd.DataFrame,
    entity_type: str,
    source: str,
    column_map: dict[str, str],
) -> AnalysisResult:
    """Run retail-specific analysis on a cleaned dataframe."""
    result = AnalysisResult(entity_type=entity_type, source=source)

    if df.empty:
        result.available = False
        result.skip_reason = "No data available."
        return result

    actual = {}
    for canonical, raw in column_map.items():
        if raw in df.columns:
            actual[canonical] = raw

    if entity_type == EntityType.SALES.value or entity_type == "sales":
        result = _analyze_sales(df, actual, source)
    elif entity_type == EntityType.INVENTORY.value or entity_type == "inventory":
        result = _analyze_inventory(df, actual, source)
    elif entity_type == EntityType.PRODUCTS.value or entity_type == "products":
        result = _analyze_products(df, actual, source)
    elif entity_type == EntityType.PURCHASES.value or entity_type == "purchases":
        result = _analyze_purchases(df, actual, source)
    else:
        result.available = False
        result.skip_reason = f"Unknown entity type: {entity_type}"

    return result


def _analyze_sales(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    result = AnalysisResult(entity_type="sales", source=source)

    revenue_col = actual.get("revenue")
    date_col = actual.get("date")
    product_col = actual.get("product")
    category_col = actual.get("category")
    qty_col = actual.get("quantity")
    cost_col = actual.get("cost")
    invoice_col = actual.get("invoice_id")
    payment_col = actual.get("payment_method")

    if not revenue_col and not qty_col:
        result.available = False
        result.skip_reason = "No revenue or quantity column detected. Sales analysis cannot be performed."
        return result

    kpis = {}
    if revenue_col:
        revenue = df[revenue_col].dropna()
        kpis["total_revenue"] = round(float(revenue.sum()), 2)
        kpis["avg_basket_value"] = round(float(revenue.mean()), 2) if len(revenue) > 0 else 0
        kpis["transaction_count"] = int(len(revenue))
    if qty_col:
        kpis["units_sold"] = round(float(df[qty_col].sum()), 2)
    if product_col:
        kpis["unique_products"] = int(df[product_col].nunique())
    if category_col:
        kpis["unique_categories"] = int(df[category_col].nunique())
    if invoice_col:
        kpis["unique_transactions"] = int(df[invoice_col].nunique())

    result.kpis = kpis

    # Time analysis
    if date_col and revenue_col:
        from app.core.analytics import time_series_analysis
        result.time_analysis = time_series_analysis(df, date_col, revenue_col)

    # Product analysis
    if product_col and revenue_col:
        from app.core.analytics import category_analysis
        result.product_analysis = category_analysis(df, product_col, revenue_col, dimension="product")

    # Category analysis
    if category_col and revenue_col:
        cat_analysis = {}
        cat_totals = df.groupby(category_col)[revenue_col].sum().sort_values(ascending=False)
        total = float(cat_totals.sum())
        cat_analysis["top"] = [
            {"name": str(k), "value": round(float(v), 2), "pct": round(float(v / total * 100), 1) if total != 0 else 0}
            for k, v in cat_totals.head(10).items()
        ]
        cat_analysis["total_value"] = round(total, 2)
        cat_analysis["total_categories"] = int(len(cat_totals))
        cat_analysis["dimension"] = "category"
        result.category_analysis = cat_analysis

    # Profitability
    if revenue_col and cost_col:
        from app.core.analytics import profitability_analysis
        unit_cost_col = actual.get("unit_cost")
        if unit_cost_col and unit_cost_col == cost_col:
            cost_type = "unit"
        else:
            cost_type = "total"
        result.profitability = profitability_analysis(df, revenue_col, cost_col, quantity_col=qty_col, cost_type=cost_type)

    # Retail-specific findings
    result.findings = _retail_findings(result, df, actual)
    result.available = True
    return result


def _analyze_inventory(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    result = AnalysisResult(entity_type="inventory", source=source)

    product_col = actual.get("product")
    stock_col = actual.get("stock_level")
    reorder_col = actual.get("reorder_level")

    if not product_col:
        result.available = False
        result.skip_reason = "No product column detected. Inventory analysis cannot be performed."
        return result

    kpis = {"unique_products": int(df[product_col].nunique())}
    if stock_col:
        kpis["total_stock"] = round(float(df[stock_col].sum()), 2)

    # Low stock and excess stock
    low_stock = []
    excess_stock = []
    if stock_col:
        avg_stock = df[stock_col].mean()
        for _, row in df.iterrows():
            product = str(row[product_col])
            stock = row[stock_col]
            if pd.notna(stock):
                if reorder_col and pd.notna(row.get(reorder_col)):
                    if float(stock) <= float(row[reorder_col]):
                        low_stock.append({"product": product, "stock": float(stock)})
                if float(stock) > avg_stock * 3:
                    excess_stock.append({"product": product, "stock": float(stock)})

        kpis["low_stock_count"] = len(low_stock)
        kpis["excess_stock_count"] = len(excess_stock)

    result.kpis = kpis

    for item in low_stock[:5]:
        result.findings.append(Finding(
            type=FindingType.INVENTORY,
            severity=FindingSeverity.MEDIUM,
            title=f"Low stock: {item['product']}",
            metric="stock_level",
            value=item["stock"],
            comparison=f"Stock: {item['stock']:.0f} units vs reorder level",
            explanation=f"Product '{item['product']}' is running low with {item['stock']:.0f} units in stock. This risks a stockout if demand continues.",
            evidence=f"Stock level: {item['stock']:.0f} units",
            recommended_action=f"Reorder '{item['product']}' to avoid stockouts.",
        ))

    for item in excess_stock[:3]:
        result.findings.append(Finding(
            type=FindingType.INVENTORY,
            severity=FindingSeverity.LOW,
            title=f"Excess stock: {item['product']}",
            metric="stock_level",
            value=item["stock"],
            comparison=f"Stock: {item['stock']:.0f} units vs average stock level",
            explanation=f"Product '{item['product']}' has {item['stock']:.0f} units, significantly above the average. This ties up capital in slow-moving inventory.",
            evidence=f"Stock level: {item['stock']:.0f} units (above average)",
            recommended_action=f"Review demand for '{item['product']}' and consider promotions to reduce excess inventory.",
        ))

    result.available = True
    return result


def _analyze_products(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    result = AnalysisResult(entity_type="products", source=source)
    product_col = actual.get("product")
    if not product_col:
        result.available = False
        result.skip_reason = "No product column detected."
        return result
    result.kpis = {"unique_products": int(df[product_col].nunique())}
    category_col = actual.get("category")
    if category_col:
        result.kpis["unique_categories"] = int(df[category_col].nunique())
    result.available = True
    return result


def _analyze_purchases(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    result = AnalysisResult(entity_type="purchases", source=source)
    supplier_col = actual.get("supplier")
    date_col = actual.get("date")
    cost_col = actual.get("cost") or actual.get("total_cost")

    if not supplier_col:
        result.available = False
        result.skip_reason = "No supplier column detected."
        return result

    kpis = {"unique_suppliers": int(df[supplier_col].nunique())}
    if cost_col:
        kpis["total_purchases"] = round(float(df[cost_col].sum()), 2)

    result.kpis = kpis

    if cost_col:
        from app.core.analytics import category_analysis
        result.category_analysis = category_analysis(df, supplier_col, cost_col, dimension="supplier")

    if date_col and cost_col:
        from app.core.analytics import time_series_analysis
        result.time_analysis = time_series_analysis(df, date_col, cost_col)

    result.available = True
    return result


def _retail_findings(result: AnalysisResult, df: pd.DataFrame, actual: dict) -> list[Finding]:
    findings = []

    # Best sellers / slow sellers (from product_analysis, not category_analysis)
    prod = result.product_analysis
    if prod and prod.get("top"):
        top_item = prod["top"][0]
        total_val = prod.get("total_value", 0)
        if top_item["pct"] >= 15:
            findings.append(Finding(
                type=FindingType.PRODUCT,
                severity=FindingSeverity.LOW,
                title=f"Best seller: {top_item['name']}",
                metric="product_share",
                value=top_item["pct"],
                comparison=f"{top_item['name']} generates {top_item['pct']}% of total revenue ({top_item['value']:,.2f} of {total_val:,.2f})",
                explanation=f"Product '{top_item['name']}' is the top revenue contributor. Maintaining its availability and quality is important for sustained revenue.",
                evidence=f"Top product '{top_item['name']}': {top_item['value']:,.2f} ({top_item['pct']}% of {total_val:,.2f} total)",
                recommended_action=f"Ensure consistent stock levels for '{top_item['name']}' and consider expanding the product line.",
            ))

    # Profitability
    prof = result.profitability
    if prof and prof.get("gross_margin_pct") is not None:
        margin = prof["gross_margin_pct"]
        if margin < 15:
            total_rev = prof.get("total_revenue", 0)
            total_cost = prof.get("total_cost", 0)
            findings.append(Finding(
                type=FindingType.MARGIN,
                severity=FindingSeverity.MEDIUM,
                title=f"Low gross margin ({margin:.1f}%)",
                metric="gross_margin_pct",
                value=margin,
                comparison=f"Revenue: {total_rev:,.2f}, Cost: {total_cost:,.2f}, Profit: {prof.get('gross_profit', 0):,.2f}",
                explanation=f"Gross margin is {margin:.1f}%, meaning cost of goods sold consumes {100 - margin:.1f}% of revenue. This leaves limited room for operating expenses.",
                evidence=f"Revenue: {total_rev:,.2f}, Cost: {total_cost:,.2f}, Gross profit: {prof.get('gross_profit', 0):,.2f}",
                recommended_action="Review pricing strategy and supplier costs to improve margins.",
            ))

    # Trend
    time = result.time_analysis
    if time and time.get("trend_direction") == "decreasing":
        slope = time.get("trend_slope", 0)
        findings.append(Finding(
            type=FindingType.TREND,
            severity=FindingSeverity.MEDIUM,
            title="Declining sales trend",
            metric="trend_slope",
            value=slope,
            comparison=f"Daily revenue trend slope: {slope:.2f} per day (average daily: {time.get('avg_daily', 0):,.2f})",
            explanation="Sales show a declining trend over the analyzed period.",
            evidence=f"Trend slope: {slope:.2f}, Average daily revenue: {time.get('avg_daily', 0):,.2f}",
            recommended_action="Investigate causes and implement promotional or pricing strategies.",
        ))

    return findings
