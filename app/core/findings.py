"""Findings engine: converts calculated metrics into structured, evidence-based findings.

Each finding includes:
- metric: the specific KPI or measure being reported
- value: the numeric value
- comparison: how it compares to other items, periods, or thresholds
- explanation: why it matters (business impact)
- recommended_action: suggested investigation or action

Findings are entity-specific: customer findings reference customers, product findings
reference products, inventory findings reference inventory items. No generic industry
benchmarks are used unless explicitly sourced.
"""

from __future__ import annotations

from app.core.models import AnalysisResult, Finding, FindingSeverity, FindingType


def build_findings(results: list[AnalysisResult]) -> list[Finding]:
    """Generate findings from all analysis results.

    Merges vertical-specific findings (already in result.findings) with
    generic findings generated here. Deduplicates by title.
    """
    findings = []
    seen_titles = set()

    for result in results:
        # Include vertical-specific findings first
        for f in result.findings:
            if f.title not in seen_titles:
                findings.append(f)
                seen_titles.add(f.title)

        if not result.available:
            if result.skip_reason:
                title = f"{result.entity_type.title()} analysis skipped"
                if title not in seen_titles:
                    findings.append(Finding(
                        type=FindingType.DATA_QUALITY,
                        severity=FindingSeverity.INFO,
                        title=title,
                        explanation=result.skip_reason,
                    ))
                    seen_titles.add(title)
            continue

        # Generic findings (deduplicated against vertical findings)
        generic = (
            _sales_findings(result)
            + _profitability_findings(result)
            + _product_findings(result)
            + _customer_findings(result)
            + _inventory_findings(result)
            + _trend_findings(result)
        )
        # Anomaly findings need to see existing findings for entity-level dedup
        anomaly_findings = _anomaly_findings(result, findings + generic)
        generic = generic + anomaly_findings
        for f in generic:
            if f.title not in seen_titles:
                findings.append(f)
                seen_titles.add(f.title)

    return findings


def _sales_findings(result: AnalysisResult) -> list[Finding]:
    """Generate sales-level findings with revenue context."""
    findings = []
    kpis = result.kpis

    if "total_revenue" in kpis:
        revenue = kpis["total_revenue"]
        txn_count = kpis.get("transaction_count", kpis.get("order_count", 0))
        avg_val = kpis.get("avg_transaction_value", kpis.get("avg_order_value", kpis.get("avg_basket_value")))

        evidence_parts = [f"Total revenue: {revenue:,.2f}"]
        if txn_count:
            evidence_parts.append(f"across {txn_count} transactions")
        if avg_val:
            evidence_parts.append(f"avg {avg_val:,.2f} per transaction")

        findings.append(Finding(
            type=FindingType.SALES,
            severity=FindingSeverity.INFO,
            title="Revenue summary",
            metric="total_revenue",
            value=revenue,
            comparison=f"Across {txn_count} transactions" if txn_count else "",
            explanation=f"Total revenue for this period is {revenue:,.2f}.",
            evidence="; ".join(evidence_parts),
            recommended_action=f"Compare revenue of {revenue:,.2f} against prior periods and targets to assess performance.",
        ))

    return findings


def _profitability_findings(result: AnalysisResult) -> list[Finding]:
    """Generate profitability findings based on computed margins.

    No unsourced industry benchmarks are used. Findings are based on the data itself:
    overall margin, negative-margin records, and margin variance.
    """
    findings = []
    profit = result.profitability
    if not profit:
        return findings

    margin = profit.get("gross_margin_pct")
    total_revenue = profit.get("total_revenue", 0)
    total_cost = profit.get("total_cost", 0)
    gross_profit = profit.get("gross_profit", 0)
    neg_count = profit.get("negative_margin_count", 0)
    avg_margin = profit.get("avg_margin_pct")

    if margin is not None:
        # Check if vertical findings already cover margin
        already_covered = any(
            f.type == FindingType.MARGIN and "margin" in f.title.lower()
            for f in result.findings
        )
        if not already_covered:
            # Report the overall margin with full evidence
            comparison = ""
            if avg_margin is not None and abs(avg_margin - margin) > 5:
                comparison = f"Average per-record margin is {avg_margin:.1f}% (vs overall {margin:.1f}%)"

            findings.append(Finding(
                type=FindingType.MARGIN,
                severity=FindingSeverity.INFO,
                title="Gross margin analysis",
                metric="gross_margin_pct",
                value=margin,
                comparison=comparison,
                explanation=f"Overall gross margin is {margin:.1f}% (revenue {total_revenue:,.2f}, cost {total_cost:,.2f}, profit {gross_profit:,.2f}).",
                evidence=f"Revenue: {total_revenue:,.2f}, Cost: {total_cost:,.2f}, Gross profit: {gross_profit:,.2f}",
                recommended_action=f"Review pricing strategy and supplier costs if margin of {margin:.1f}% is below expectations.",
            ))

    # Negative margin records
    if neg_count and neg_count > 0:
        findings.append(Finding(
            type=FindingType.MARGIN,
            severity=FindingSeverity.HIGH if neg_count > 5 else FindingSeverity.MEDIUM,
            title=f"{neg_count} records with negative margin",
            metric="negative_margin_count",
            value=neg_count,
            comparison=f"Out of {result.kpis.get('transaction_count', 0)} total records",
            explanation=f"{neg_count} records show revenue below cost (selling price less than cost). This may indicate pricing errors, deep discounts, or data entry issues.",
            evidence=f"Negative margin records: {neg_count}",
            recommended_action="Investigate affected records for pricing errors or review discount policies.",
        ))

    return findings


def _product_findings(result: AnalysisResult) -> list[Finding]:
    """Generate product-specific findings from product_analysis data.

    Product findings reference actual product names and their specific metrics.
    """
    findings = []
    product_data = result.product_analysis
    if not product_data:
        # Fallback to category_analysis if it has product dimension
        cat = result.category_analysis
        if cat and cat.get("dimension") == "product":
            product_data = cat

    if not product_data:
        return findings

    top = product_data.get("top", [])
    if not top:
        return findings

    total_value = product_data.get("total_value", 0)

    # Top product concentration
    top_product = top[0]
    if top_product["pct"] >= 20:
        # Check if already mentioned in vertical findings
        already_mentioned = any(
            top_product["name"] in f.title for f in result.findings
            if f.type == FindingType.PRODUCT
        )
        if not already_mentioned:
            findings.append(Finding(
                type=FindingType.PRODUCT,
                severity=FindingSeverity.MEDIUM if top_product["pct"] >= 30 else FindingSeverity.LOW,
                title=f"High product concentration: {top_product['name']}",
                metric="top_product_share",
                value=top_product["pct"],
                comparison=f"{top_product['name']} accounts for {top_product['pct']}% of total revenue ({top_product['value']:,.2f} of {total_value:,.2f})",
                explanation=f"Product '{top_product['name']}' is the top revenue contributor at {top_product['pct']}% of total. High concentration in a single product increases risk if demand shifts or supply is disrupted.",
                evidence=f"Top product '{top_product['name']}': {top_product['value']:,.2f} ({top_product['pct']}% of {total_value:,.2f} total)",
                recommended_action=f"Ensure reliable supply for '{top_product['name']}' and develop alternative products to reduce concentration risk.",
            ))

    # Check for weak products (bottom of the top list)
    if len(top) >= 5:
        last = top[-1]
        if last["pct"] < 5:
            # Check if this product is already mentioned in vertical findings
            already_mentioned = any(
                last["name"] in f.title for f in result.findings
                if f.type == FindingType.PRODUCT
            )
            if not already_mentioned:
                findings.append(Finding(
                    type=FindingType.PRODUCT,
                    severity=FindingSeverity.LOW,
                    title=f"Underperforming product: {last['name']}",
                    metric="product_share",
                    value=last["pct"],
                    comparison=f"{last['name']} generates only {last['pct']}% of revenue ({last['value']:,.2f} of {total_value:,.2f}), the lowest among top products",
                    explanation=f"Product '{last['name']}' contributes minimally to revenue. This may indicate low demand, pricing issues, or need for repositioning.",
                    evidence=f"Bottom product '{last['name']}': {last['value']:,.2f} ({last['pct']}% of total)",
                    recommended_action=f"Review pricing, placement, and demand for '{last['name']}'. Consider discontinuation if performance does not improve.",
                ))

    return findings


def _customer_findings(result: AnalysisResult) -> list[Finding]:
    """Generate customer-specific findings from customer analysis data.

    Customer findings reference actual customer names and their specific metrics.
    """
    findings = []
    cat = result.category_analysis
    if not cat:
        return findings

    # Only generate customer findings if the dimension is customer
    dimension = cat.get("dimension", "")
    if dimension != "customer":
        return findings

    total_value = cat.get("total_value", 0)

    # Customer concentration
    conc = cat.get("top3_concentration")
    if conc and conc >= 40:
        # Check if vertical findings already cover customer concentration
        already_covered = any(
            f.type == FindingType.CUSTOMER and "concentration" in f.title.lower()
            for f in result.findings
        )
        if not already_covered:
            top_customers = cat.get("top", [])[:3]
            names = ", ".join(c["name"] for c in top_customers)
            findings.append(Finding(
                type=FindingType.CUSTOMER,
                severity=FindingSeverity.HIGH if conc >= 60 else FindingSeverity.MEDIUM,
                title=f"Customer concentration risk ({conc:.1f}%)",
                metric="top3_concentration",
                value=conc,
                comparison=f"Top 3 customers ({names}) account for {conc:.1f}% of total revenue ({total_value:,.2f})",
                explanation=f"High customer concentration means a significant portion of revenue depends on a few customers. Losing one of the top customers would have a material impact on revenue.",
                evidence=f"Top 3 customer share: {conc:.1f}% of {total_value:,.2f} total revenue",
                recommended_action="Develop strategies to diversify the customer base and reduce dependency on top customers.",
            ))

    # Individual customer concentration (single customer > 25%)
    top = cat.get("top", [])
    for item in top[:3]:
        if item["pct"] >= 25:
            findings.append(Finding(
                type=FindingType.CUSTOMER,
                severity=FindingSeverity.HIGH if item["pct"] >= 35 else FindingSeverity.MEDIUM,
                title=f"Single customer dominance: {item['name']}",
                metric="customer_share",
                value=item["pct"],
                comparison=f"{item['name']} represents {item['pct']:.1f}% of total revenue ({item['value']:,.2f} of {total_value:,.2f})",
                explanation=f"Customer '{item['name']}' alone accounts for {item['pct']:.1f}% of revenue. This level of dependency creates significant business risk if this customer reduces orders or switches suppliers.",
                evidence=f"Customer '{item['name']}': {item['value']:,.2f} ({item['pct']:.1f}% of total)",
                recommended_action=f"Strengthen relationship with '{item['name']}' while actively developing new customer accounts to reduce dependency.",
            ))
            break  # Only report the most dominant customer individually

    return findings


def _inventory_findings(result: AnalysisResult) -> list[Finding]:
    """Generate inventory-specific findings. Most are generated in vertical analysis."""
    return []


def _trend_findings(result: AnalysisResult) -> list[Finding]:
    """Generate trend findings based on time series analysis."""
    findings = []
    time = result.time_analysis
    if not time:
        return findings

    direction = time.get("trend_direction")
    slope = time.get("trend_slope")
    total = time.get("total", 0)
    avg_daily = time.get("avg_daily", 0)

    if direction == "decreasing":
        # Check if vertical findings already cover declining trend
        already_covered = any(
            f.type == FindingType.TREND and "declin" in f.title.lower()
            for f in result.findings
        )
        if not already_covered:
            entity_ctx = f" ({result.entity_type})" if result.entity_type else ""
            findings.append(Finding(
                type=FindingType.TREND,
                severity=FindingSeverity.MEDIUM,
                title=f"Declining revenue trend{entity_ctx}",
                metric="trend_slope",
                value=slope,
                comparison=f"Daily revenue trend slope: {slope:.2f} per day (average daily: {avg_daily:,.2f})",
                explanation=f"Revenue shows a declining trend over the analyzed period for {result.entity_type}. A negative trend slope indicates that daily revenue is decreasing over time.",
                evidence=f"Trend slope: {slope:.2f}, Average daily revenue: {avg_daily:,.2f}, Total: {total:,.2f}",
                recommended_action=f"Investigate causes of declining revenue (slope: {slope:.2f}/day, avg {avg_daily:,.2f}/day). Check for seasonality, competition, or pricing issues.",
            ))
    elif direction == "increasing":
        entity_ctx = f" ({result.entity_type})" if result.entity_type else ""
        findings.append(Finding(
            type=FindingType.TREND,
            severity=FindingSeverity.INFO,
            title=f"Growing revenue trend{entity_ctx}",
            metric="trend_slope",
            value=slope,
            comparison=f"Daily revenue trend slope: {slope:.2f} per day (average daily: {avg_daily:,.2f})",
            explanation=f"Revenue shows a growth trend over the analyzed period for {result.entity_type}. A positive trend slope indicates that daily revenue is increasing over time.",
            evidence=f"Trend slope: {slope:.2f}, Average daily revenue: {avg_daily:,.2f}, Total: {total:,.2f}",
            recommended_action="Capitalize on growth by ensuring adequate inventory and staffing to meet increasing demand.",
        ))

    # Month-over-month significant change
    mom = time.get("mom_change_pct")
    if mom is not None and abs(mom) > 20:
        latest = time.get("latest_month", 0)
        prev = time.get("previous_month", 0)
        findings.append(Finding(
            type=FindingType.TREND,
            severity=FindingSeverity.MEDIUM,
            title=f"Significant month-over-month change ({mom:+.1f}%)",
            metric="mom_change_pct",
            value=mom,
            comparison=f"Latest month: {latest:,.2f} vs previous month: {prev:,.2f} ({mom:+.1f}%)",
            explanation=f"Revenue {'increased' if mom > 0 else 'decreased'} by {abs(mom):.1f}% compared to the previous month. Changes above 20% warrant investigation.",
            evidence=f"Previous month: {prev:,.2f}, Current month: {latest:,.2f}, Change: {mom:+.1f}%",
            recommended_action=f"Investigate factors behind the {mom:+.1f}% month-over-month change and assess whether it is seasonal or structural.",
        ))

    return findings


def _anomaly_findings(result: AnalysisResult, existing_findings: list[Finding] | None = None) -> list[Finding]:
    """Generate findings from detected anomalies.

    Anomaly findings are entity-aware: trend anomalies reference time periods,
    concentration anomalies reference the correct entity type (customer, product, supplier).
    Uses existing_findings for entity-level dedup to avoid duplicate concentration findings.
    """
    findings = []
    existing_findings = existing_findings or []
    for anomaly in result.anomalies:
        # Trend anomalies (revenue surges/drops)
        if anomaly.get("direction") in ("surge", "drop"):
            findings.append(Finding(
                type=FindingType.ANOMALY,
                severity=FindingSeverity.MEDIUM,
                title=f"Revenue {anomaly['direction']} in {anomaly['period']}",
                metric="monthly_change",
                value=anomaly.get("change_pct"),
                comparison=f"{anomaly['change_pct']:+.1f}% vs previous period ({anomaly.get('previous_period', '')})",
                explanation=f"Revenue {anomaly['direction']}d by {abs(anomaly['change_pct']):.1f}% in {anomaly['period']}. This exceeds the 30% threshold for notable changes.",
                evidence=f"Previous period ({anomaly.get('previous_period', '')}): {anomaly.get('previous_value', 0):,.2f}, Current: {anomaly.get('value', 0):,.2f}",
                recommended_action="Investigate the cause of this revenue anomaly and assess whether it is seasonal, one-time, or structural.",
            ))
        # Concentration anomalies — determine entity type from the data source that generated them
        elif "share_pct" in anomaly:
            # Check product_analysis first (preferred source), then category_analysis
            cat = result.product_analysis or result.category_analysis
            dimension = cat.get("dimension", "") if cat else ""
            entity_label = dimension if dimension else "entity"
            entity_name = anomaly.get("entity", "Unknown")

            # Skip if this entity is already mentioned in existing findings
            already_mentioned = any(
                entity_name in f.title for f in existing_findings + findings
            )
            if already_mentioned:
                continue

            findings.append(Finding(
                type=FindingType.CUSTOMER if dimension == "customer" else FindingType.PRODUCT if dimension == "product" else FindingType.SUPPLIER if dimension == "supplier" else FindingType.ANOMALY,
                severity=FindingSeverity.HIGH if anomaly.get("risk_level") == "high" else FindingSeverity.MEDIUM,
                title=f"{entity_label.title()} concentration: {anomaly.get('entity', 'Unknown')}",
                metric=f"{entity_label}_share",
                value=anomaly.get("share_pct"),
                comparison=f"{anomaly.get('entity', 'Unknown')} accounts for {anomaly.get('share_pct', 0):.1f}% of total",
                explanation=anomaly.get("description", ""),
                evidence=f"{entity_label.title()} share: {anomaly.get('share_pct', 0):.1f}%",
                recommended_action=f"Reduce dependency on {anomaly.get('entity', 'this entity')} by diversifying the {entity_label} base.",
            ))

    return findings
