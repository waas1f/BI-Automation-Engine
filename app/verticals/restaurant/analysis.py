"""Restaurant-specific analysis: KPIs, menu analysis, peak days, profitability."""

from __future__ import annotations

import pandas as pd

from app.core.models import AnalysisResult, EntityType, Finding, FindingSeverity, FindingType
from app.core.utils import format_currency, format_percent


def analyze_restaurant(
    df: pd.DataFrame,
    entity_type: str,
    source: str,
    column_map: dict[str, str],
) -> AnalysisResult:
    """Run restaurant-specific analysis on a cleaned dataframe."""
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
    elif entity_type in (EntityType.MENU.value, "menu", "products"):
        result = _analyze_menu(df, actual, source)
    elif entity_type == EntityType.INVENTORY.value or entity_type == "inventory":
        result = _analyze_inventory(df, actual, source)
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
    time_col = actual.get("order_time")
    waiter_col = actual.get("waiter")
    table_col = actual.get("table_number")

    if not revenue_col:
        result.available = False
        result.skip_reason = "No revenue column detected. Revenue analysis cannot be performed."
        return result

    kpis = {}
    revenue = df[revenue_col].dropna()
    kpis["total_revenue"] = round(float(revenue.sum()), 2)
    kpis["order_count"] = int(len(revenue))
    kpis["avg_order_value"] = round(float(revenue.mean()), 2) if len(revenue) > 0 else 0

    if invoice_col:
        kpis["unique_orders"] = int(df[invoice_col].nunique())
    if product_col:
        kpis["unique_menu_items"] = int(df[product_col].nunique())
    if category_col:
        kpis["unique_categories"] = int(df[category_col].nunique())
    if qty_col:
        kpis["total_items_sold"] = round(float(df[qty_col].sum()), 2)

    result.kpis = kpis

    # Time analysis - daily, weekly, monthly
    if date_col and revenue_col:
        from app.core.analytics import time_series_analysis
        result.time_analysis = time_series_analysis(df, date_col, revenue_col)

        # Peak day analysis
        temp = df[[date_col, revenue_col]].dropna().copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        temp = temp.dropna(subset=[date_col])
        if len(temp) > 0:
            day_totals = temp.groupby(temp[date_col].dt.day_name())[revenue_col].sum()
            if len(day_totals) > 0:
                peak_day = day_totals.idxmax()
                peak_value = day_totals.max()
                kpis["peak_day"] = peak_day
                kpis["peak_day_revenue"] = round(float(peak_value), 2)
                result.findings.append(Finding(
                    type=FindingType.SALES,
                    severity=FindingSeverity.INFO,
                    title=f"Peak sales day: {peak_day}",
                    metric="peak_day_revenue",
                    value=peak_value,
                    comparison=f"{peak_day} revenue: {peak_value:,.2f} (highest of all days)",
                    explanation=f"{peak_day} is the highest-grossing day with {peak_value:,.2f} in revenue. Adequate staffing and inventory are essential on this day.",
                    evidence=f"Peak day: {peak_day}, Revenue: {peak_value:,.2f}",
                    recommended_action="Ensure adequate staffing and inventory on peak days to maximize revenue.",
                ))

    # Menu analysis
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

    # Restaurant-specific findings
    result.findings.extend(_restaurant_findings(result, df, actual))
    result.available = True
    return result


def _analyze_menu(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    result = AnalysisResult(entity_type="menu", source=source)
    product_col = actual.get("product")
    if not product_col:
        result.available = False
        result.skip_reason = "No menu item column detected."
        return result
    result.kpis = {"unique_menu_items": int(df[product_col].nunique())}
    category_col = actual.get("category")
    if category_col:
        result.kpis["unique_categories"] = int(df[category_col].nunique())
    result.available = True
    return result


def _analyze_inventory(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    result = AnalysisResult(entity_type="inventory", source=source)
    product_col = actual.get("product")
    if not product_col:
        result.available = False
        result.skip_reason = "No product column detected."
        return result

    kpis = {"unique_items": int(df[product_col].nunique())}
    stock_col = actual.get("stock_level")
    reorder_col = actual.get("reorder_level")

    if stock_col:
        kpis["total_stock"] = round(float(df[stock_col].sum()), 2)
        low_stock = []
        for _, row in df.iterrows():
            stock = row[stock_col]
            product = str(row[product_col])
            if pd.notna(stock):
                if reorder_col and pd.notna(row.get(reorder_col)):
                    if float(stock) <= float(row[reorder_col]):
                        low_stock.append({"product": product, "stock": float(stock)})
                kpis["low_stock_count"] = len(low_stock)

                for item in low_stock[:5]:
                    result.findings.append(Finding(
                        type=FindingType.INVENTORY,
                        severity=FindingSeverity.MEDIUM,
                        title=f"Low stock: {item['product']}",
                        metric="stock_level",
                        value=item["stock"],
                        comparison=f"Stock: {item['stock']:.0f} units vs reorder level",
                        explanation=f"Item '{item['product']}' is low on stock ({item['stock']:.0f} units). This risks running out during service.",
                        evidence=f"Stock level: {item['stock']:.0f} units",
                        recommended_action=f"Reorder '{item['product']}' to avoid running out during service.",
                    ))

    result.kpis = kpis
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

    result.available = True
    return result


def _restaurant_findings(result: AnalysisResult, df: pd.DataFrame, actual: dict) -> list[Finding]:
    findings = []

    # Best-selling and weak menu items (from product_analysis, not category_analysis)
    prod = result.product_analysis
    if prod and prod.get("top"):
        total_val = prod.get("total_value", 0)
        best = prod["top"][0]
        if best["pct"] >= 15:
            findings.append(Finding(
                type=FindingType.PRODUCT,
                severity=FindingSeverity.INFO,
                title=f"Best-selling item: {best['name']}",
                metric="item_share",
                value=best["pct"],
                comparison=f"{best['name']} generates {best['pct']}% of total revenue ({best['value']:,.2f} of {total_val:,.2f})",
                explanation=f"Menu item '{best['name']}' is the top revenue contributor at {best['pct']}% of total. Consistent quality and availability are critical.",
                evidence=f"Top item '{best['name']}': {best['value']:,.2f} ({best['pct']}% of {total_val:,.2f} total)",
                recommended_action=f"Ensure consistent quality and availability of '{best['name']}'. Consider featuring it in promotions.",
            ))

        # Check for weak items
        if len(prod.get("top", [])) >= 5:
            last = prod["top"][-1]
            if last["pct"] < 3:
                findings.append(Finding(
                    type=FindingType.PRODUCT,
                    severity=FindingSeverity.LOW,
                    title=f"Underperforming item: {last['name']}",
                    metric="item_share",
                    value=last["pct"],
                    comparison=f"{last['name']} generates only {last['pct']}% of revenue ({last['value']:,.2f} of {total_val:,.2f}), the lowest among top items",
                    explanation=f"Menu item '{last['name']}' contributes minimally to revenue. This may indicate low demand, pricing issues, or need for repositioning.",
                    evidence=f"Bottom item '{last['name']}': {last['value']:,.2f} ({last['pct']}% of total)",
                    recommended_action=f"Review pricing, portion size, and presentation of '{last['name']}'. Consider replacing if demand remains low.",
                ))

    # Profitability
    prof = result.profitability
    if prof and prof.get("gross_margin_pct") is not None:
        margin = prof["gross_margin_pct"]
        if margin < 20:
            total_rev = prof.get("total_revenue", 0)
            total_cost = prof.get("total_cost", 0)
            findings.append(Finding(
                type=FindingType.MARGIN,
                severity=FindingSeverity.MEDIUM,
                title=f"Low gross margin ({margin:.1f}%)",
                metric="gross_margin_pct",
                value=margin,
                comparison=f"Revenue: {total_rev:,.2f}, Cost: {total_cost:,.2f}, Profit: {prof.get('gross_profit', 0):,.2f}",
                explanation=f"Gross margin is {margin:.1f}%, meaning cost of goods sold consumes {100 - margin:.1f}% of revenue. This leaves limited room for operating expenses like labor and rent.",
                evidence=f"Revenue: {total_rev:,.2f}, Cost: {total_cost:,.2f}, Gross profit: {prof.get('gross_profit', 0):,.2f}",
                recommended_action="Review portion sizes, supplier costs, and menu pricing to improve margins.",
            ))

    # Trend
    time = result.time_analysis
    if time and time.get("trend_direction") == "decreasing":
        slope = time.get("trend_slope", 0)
        findings.append(Finding(
            type=FindingType.TREND,
            severity=FindingSeverity.MEDIUM,
            title="Declining revenue trend",
            metric="trend_slope",
            value=slope,
            comparison=f"Daily revenue trend slope: {slope:.2f} per day (average daily: {time.get('avg_daily', 0):,.2f})",
            explanation="Revenue shows a declining trend over the analyzed period.",
            evidence=f"Trend slope: {slope:.2f}, Average daily revenue: {time.get('avg_daily', 0):,.2f}",
            recommended_action="Review menu, service quality, and marketing efforts.",
        ))

    return findings
