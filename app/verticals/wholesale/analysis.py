"""Wholesale-specific analysis: KPIs, product/customer analysis, inventory, findings."""

from __future__ import annotations

import pandas as pd

from app.core.models import AnalysisResult, EntityType, Finding, FindingSeverity, FindingType
from app.core.utils import logger, format_currency, format_percent
from app.verticals.wholesale.config import WHOLESALE_ENTITIES


def analyze_wholesale(
    df: pd.DataFrame,
    entity_type: str,
    source: str,
    column_map: dict[str, str],
) -> AnalysisResult:
    """Run wholesale-specific analysis on a cleaned dataframe."""
    result = AnalysisResult(entity_type=entity_type, source=source)

    if df.empty:
        result.available = False
        result.skip_reason = "No data available."
        return result

    # Build actual column lookup
    actual = {}
    for canonical, raw in column_map.items():
        if raw in df.columns:
            actual[canonical] = raw

    if entity_type == EntityType.SALES.value or entity_type == "sales":
        result = _analyze_sales(df, actual, source)
    elif entity_type == EntityType.INVENTORY.value or entity_type == "inventory":
        result = _analyze_inventory(df, actual, source)
    elif entity_type == EntityType.PURCHASES.value or entity_type == "purchases":
        result = _analyze_purchases(df, actual, source)
    elif entity_type == EntityType.PRODUCTS.value or entity_type == "products":
        result = _analyze_products(df, actual, source)
    elif entity_type == EntityType.CUSTOMERS.value or entity_type == "customers":
        result = _analyze_customers(df, actual, source)
    else:
        result.available = False
        result.skip_reason = f"Unknown entity type: {entity_type}"

    return result


def _analyze_sales(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    """Analyze sales data for wholesale."""
    result = AnalysisResult(entity_type="sales", source=source)

    revenue_col = actual.get("revenue")
    date_col = actual.get("date")
    product_col = actual.get("product")
    customer_col = actual.get("customer")
    qty_col = actual.get("quantity")
    cost_col = actual.get("cost")
    invoice_col = actual.get("invoice_id")

    if not revenue_col and not qty_col:
        result.available = False
        result.skip_reason = "No revenue or quantity column detected. Sales analysis cannot be performed."
        return result

    # KPIs
    kpis = {}
    if revenue_col:
        revenue = df[revenue_col].dropna()
        kpis["total_revenue"] = round(float(revenue.sum()), 2)
        kpis["avg_transaction_value"] = round(float(revenue.mean()), 2) if len(revenue) > 0 else 0
        kpis["transaction_count"] = int(len(revenue))
    if qty_col:
        kpis["units_sold"] = round(float(df[qty_col].sum()), 2)
    if customer_col:
        kpis["unique_customers"] = int(df[customer_col].nunique())
    if product_col:
        kpis["unique_products"] = int(df[product_col].nunique())
    if invoice_col:
        kpis["unique_invoices"] = int(df[invoice_col].nunique())

    result.kpis = kpis

    # Time analysis
    if date_col and revenue_col:
        from app.core.analytics import time_series_analysis
        result.time_analysis = time_series_analysis(df, date_col, revenue_col)

    # Product analysis
    if product_col and revenue_col:
        from app.core.analytics import category_analysis
        result.product_analysis = category_analysis(df, product_col, revenue_col, dimension="product")

    # Customer analysis
    if customer_col and revenue_col:
        customer_analysis = {}
        customer_totals = df.groupby(customer_col)[revenue_col].sum().sort_values(ascending=False)
        total = float(customer_totals.sum())
        top_customers = customer_totals.head(10)
        customer_analysis["top"] = [
            {"name": str(k), "value": round(float(v), 2), "pct": round(float(v / total * 100), 1) if total != 0 else 0}
            for k, v in top_customers.items()
        ]
        customer_analysis["total_value"] = round(total, 2)
        customer_analysis["total_categories"] = int(len(customer_totals))
        customer_analysis["dimension"] = "customer"
        if len(customer_totals) >= 3:
            top3 = float(customer_totals.head(3).sum() / total * 100) if total != 0 else 0
            customer_analysis["top3_concentration"] = round(top3, 1)
            if top3 >= 50:
                customer_analysis["concentration_level"] = "high"
            elif top3 >= 30:
                customer_analysis["concentration_level"] = "moderate"
            else:
                customer_analysis["concentration_level"] = "low"
        result.kpis["customer_concentration"] = customer_analysis.get("top3_concentration")

    # Profitability
    if revenue_col and cost_col:
        from app.core.analytics import profitability_analysis
        # Determine cost type: if cost column was mapped as unit_cost, it's per-unit
        unit_cost_col = actual.get("unit_cost")
        if unit_cost_col and unit_cost_col == cost_col:
            cost_type = "unit"
        else:
            cost_type = "total"
        result.profitability = profitability_analysis(df, revenue_col, cost_col, quantity_col=qty_col, cost_type=cost_type)

    # Wholesale-specific findings
    result.findings = _wholesale_findings(result, df, actual)
    result.available = True
    return result


def _analyze_inventory(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    """Analyze inventory data."""
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
        kpis["avg_stock_per_product"] = round(float(df[stock_col].mean()), 2)

    # Low stock detection
    low_stock = []
    if stock_col and reorder_col:
        for _, row in df.iterrows():
            stock = row[stock_col]
            reorder = row[reorder_col]
            if pd.notna(stock) and pd.notna(reorder) and float(stock) <= float(reorder):
                low_stock.append({
                    "product": str(row[product_col]),
                    "stock": float(stock),
                    "reorder_level": float(reorder),
                })
        kpis["low_stock_count"] = len(low_stock)
    elif stock_col:
        # Use mean as a heuristic reorder level
        avg_stock = df[stock_col].mean()
        for _, row in df.iterrows():
            stock = row[stock_col]
            if pd.notna(stock) and float(stock) < avg_stock * 0.3:
                low_stock.append({
                    "product": str(row[product_col]),
                    "stock": float(stock),
                    "reorder_level": round(float(avg_stock * 0.3), 2),
                })
        kpis["low_stock_count"] = len(low_stock)

    result.kpis = kpis

    # Inventory findings
    for item in low_stock[:5]:
        result.findings.append(Finding(
            type=FindingType.INVENTORY,
            severity=FindingSeverity.MEDIUM,
            title=f"Low stock: {item['product']}",
            metric="stock_level",
            value=item["stock"],
            comparison=f"Stock: {item['stock']:.0f} units vs reorder level: {item['reorder_level']:.0f} units",
            explanation=f"Product '{item['product']}' has {item['stock']:.0f} units in stock, at or below the reorder level of {item['reorder_level']:.0f}. This risks a stockout if demand continues.",
            evidence=f"Stock level: {item['stock']:.0f}, Reorder level: {item['reorder_level']:.0f}",
            recommended_action=f"Reorder '{item['product']}' immediately — stock at {item['stock']:.0f} units (reorder level: {item['reorder_level']:.0f}).",
        ))

    # Always produce a summary finding so inventory analysis has at least one finding
    if not result.findings:
        unique_count = kpis.get("unique_products", 0)
        total_stock_val = kpis.get("total_stock", 0)
        if total_stock_val > 0:
            result.findings.append(Finding(
                type=FindingType.INVENTORY,
                severity=FindingSeverity.INFO,
                title="Inventory summary",
                metric="total_stock",
                value=total_stock_val,
                comparison=f"{unique_count} unique products, total stock: {total_stock_val:,.2f}",
                explanation=f"Inventory contains {unique_count} products with a total stock value of {total_stock_val:,.2f}. No items are below reorder level.",
                evidence=f"Unique products: {unique_count}, Total stock: {total_stock_val:,.2f}, Low stock items: 0",
                recommended_action=f"Monitor stock levels regularly for {unique_count} products. Current total stock: {total_stock_val:,.2f}.",
            ))
        else:
            result.findings.append(Finding(
                type=FindingType.INVENTORY,
                severity=FindingSeverity.INFO,
                title="Inventory summary",
                metric="unique_products",
                value=unique_count,
                comparison=f"{unique_count} unique products detected",
                explanation=f"Inventory contains {unique_count} products. No stock level data available for deeper analysis.",
                evidence=f"Unique products: {unique_count}, Stock data: not available",
                recommended_action=f"Add stock level data to enable low-stock alerts for {unique_count} inventory products.",
            ))

    result.available = True
    return result


def _analyze_purchases(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    """Analyze purchase/supplier data.

    Handles accounting exports where 'Amount' maps to 'revenue' but represents
    purchase cost. Uses product analysis if no supplier column is available.
    """
    result = AnalysisResult(entity_type="purchases", source=source)

    supplier_col = actual.get("supplier")
    date_col = actual.get("date")
    product_col = actual.get("product")
    # For purchases, 'revenue' column actually represents purchase cost
    cost_col = actual.get("cost") or actual.get("total_cost") or actual.get("revenue")

    # Don't require supplier — analyze by product if needed
    if not cost_col and not supplier_col:
        result.available = False
        result.skip_reason = "No cost or supplier column detected. Purchase analysis cannot be performed."
        return result

    kpis = {}
    if supplier_col:
        kpis["unique_suppliers"] = int(df[supplier_col].nunique())
    if product_col:
        kpis["unique_products"] = int(df[product_col].nunique())
    if cost_col:
        kpis["total_purchases"] = round(float(df[cost_col].sum()), 2)
        kpis["avg_purchase_value"] = round(float(df[cost_col].mean()), 2)
        kpis["transaction_count"] = int(len(df[cost_col].dropna()))

    result.kpis = kpis

    # Supplier concentration (if supplier column exists)
    if supplier_col and cost_col:
        from app.core.analytics import category_analysis
        result.category_analysis = category_analysis(df, supplier_col, cost_col, dimension="supplier")
    elif product_col and cost_col:
        # No supplier — analyze by product instead
        from app.core.analytics import category_analysis
        result.category_analysis = category_analysis(df, product_col, cost_col, dimension="product")

    # Time analysis
    if date_col and cost_col:
        from app.core.analytics import time_series_analysis
        result.time_analysis = time_series_analysis(df, date_col, cost_col)

    # Supplier concentration findings
    if result.category_analysis and result.category_analysis.get("top3_concentration"):
        conc = result.category_analysis["top3_concentration"]
        if conc >= 40:
            total_val = result.category_analysis.get("total_value", 0)
            top_items = result.category_analysis.get("top", [])[:3]
            names = ", ".join(s["name"] for s in top_items)
            dim_label = "suppliers" if supplier_col else "products"
            result.findings.append(Finding(
                type=FindingType.SUPPLIER if supplier_col else FindingType.PRODUCT,
                severity=FindingSeverity.HIGH if conc >= 60 else FindingSeverity.MEDIUM,
                title=f"{dim_label.title()} concentration risk ({conc:.1f}%)",
                metric="supplier_concentration" if supplier_col else "product_concentration",
                value=conc,
                comparison=f"Top 3 {dim_label} ({names}) account for {conc:.1f}% of total purchases ({total_val:,.2f})",
                explanation=f"High {dim_label} concentration means {conc:.1f}% of purchases depend on three {dim_label}. Disruption to any one could impact operations.",
                evidence=f"Top 3 {dim_label} share: {conc:.1f}% of {total_val:,.2f} total purchases",
                recommended_action=f"Diversify {dim_label} base to reduce supply chain risk. Top 3 ({names}) represent {conc:.1f}% of purchases.",
            ))

    result.available = True
    return result


def _analyze_products(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    """Analyze product master data."""
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


def _analyze_customers(df: pd.DataFrame, actual: dict, source: str) -> AnalysisResult:
    """Analyze customer master data."""
    result = AnalysisResult(entity_type="customers", source=source)
    customer_col = actual.get("customer")

    if not customer_col:
        result.available = False
        result.skip_reason = "No customer column detected."
        return result

    result.kpis = {"unique_customers": int(df[customer_col].nunique())}
    result.available = True
    return result


def _wholesale_findings(result: AnalysisResult, df: pd.DataFrame, actual: dict) -> list[Finding]:
    """Generate wholesale-specific findings."""
    findings = []

    # Customer concentration
    cat = result.category_analysis
    if cat and cat.get("top3_concentration") and cat["top3_concentration"] >= 40:
        top_customers = cat.get("top", [])[:3]
        names = ", ".join(c["name"] for c in top_customers)
        conc = cat["top3_concentration"]
        total_val = cat.get("total_value", 0)
        findings.append(Finding(
            type=FindingType.CUSTOMER,
            severity=FindingSeverity.HIGH if conc >= 60 else FindingSeverity.MEDIUM,
            title=f"Customer concentration risk ({conc:.1f}%)",
            metric="top3_concentration",
            value=conc,
            comparison=f"Top 3 customers ({names}) account for {conc:.1f}% of total revenue ({total_val:,.2f})",
            explanation=f"High customer concentration means {conc:.1f}% of revenue depends on just three customers. Losing one would have a material impact.",
            evidence=f"Top 3 customer share: {conc:.1f}% of {total_val:,.2f} total revenue",
            recommended_action=f"Develop new customer accounts to reduce dependency on {names} who represent {conc:.1f}% of revenue ({total_val:,.2f}).",
        ))

    # Low margin
    prof = result.profitability
    if prof and prof.get("gross_margin_pct") is not None:
        margin = prof["gross_margin_pct"]
        if margin < 10:
            total_rev = prof.get("total_revenue", 0)
            total_cost = prof.get("total_cost", 0)
            findings.append(Finding(
                type=FindingType.MARGIN,
                severity=FindingSeverity.HIGH,
                title=f"Low gross margin ({margin:.1f}%)",
                metric="gross_margin_pct",
                value=margin,
                comparison=f"Revenue: {total_rev:,.2f}, Cost: {total_cost:,.2f}, Profit: {prof.get('gross_profit', 0):,.2f}",
                explanation=f"Overall gross margin is {margin:.1f}%, meaning cost of goods sold consumes {100 - margin:.1f}% of revenue. This leaves limited room for operating expenses.",
                evidence=f"Revenue: {total_rev:,.2f}, Cost: {total_cost:,.2f}, Gross profit: {prof.get('gross_profit', 0):,.2f}",
                recommended_action=f"Review supplier pricing and selling prices — margin of {margin:.1f}% (revenue {total_rev:,.2f} vs cost {total_cost:,.2f}) is critically low.",
            ))

    # Declining revenue trend
    time = result.time_analysis
    if time and time.get("trend_direction") == "decreasing":
        slope = time.get("trend_slope", 0)
        avg_daily = time.get("avg_daily", 0)
        total = time.get("total", 0)
        findings.append(Finding(
            type=FindingType.TREND,
            severity=FindingSeverity.MEDIUM,
            title="Declining revenue trend",
            metric="trend_slope",
            value=slope,
            comparison=f"Daily revenue trend slope: {slope:.2f} per day (average daily: {avg_daily:,.2f})",
            explanation=f"Revenue shows a declining trend (slope: {slope:.2f}/day). Average daily revenue is {avg_daily:,.2f} and total is {total:,.2f}.",
            evidence=f"Trend slope: {slope:.2f}, Average daily revenue: {avg_daily:,.2f}, Total: {total:,.2f}",
            recommended_action=f"Investigate declining revenue trend (slope: {slope:.2f}/day, avg {avg_daily:,.2f}/day). Check for seasonality, competition, or pricing issues.",
        ))

    return findings
