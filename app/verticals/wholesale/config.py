"""Wholesale vertical configuration: entities, KPIs, column aliases, report sections."""

from __future__ import annotations

from app.core.models import EntityType

WHOLESALE_ENTITIES = [
    {
        "type": EntityType.SALES,
        "name": "sales",
        "required_columns": ["date", "revenue"],
        "optional_columns": ["invoice_id", "customer", "product", "quantity", "unit_price", "cost", "discount", "category"],
        "description": "Sales/transaction data",
    },
    {
        "type": EntityType.INVENTORY,
        "name": "inventory",
        "required_columns": ["product"],
        "optional_columns": ["stock_level", "reorder_level", "category", "cost", "unit_price"],
        "description": "Inventory/stock data",
    },
    {
        "type": EntityType.PURCHASES,
        "name": "purchases",
        "required_columns": ["date"],
        "optional_columns": ["supplier", "product", "quantity", "cost", "total_cost"],
        "description": "Purchase/supplier data",
    },
    {
        "type": EntityType.PRODUCTS,
        "name": "products",
        "required_columns": ["product"],
        "optional_columns": ["category", "unit_price", "cost"],
        "description": "Product master data",
    },
    {
        "type": EntityType.CUSTOMERS,
        "name": "customers",
        "required_columns": ["customer"],
        "optional_columns": ["customer_id"],
        "description": "Customer master data",
    },
]

WHOLESALE_KPIS = [
    "total_revenue",
    "units_sold",
    "transaction_count",
    "avg_transaction_value",
    "unique_customers",
    "unique_products",
    "gross_margin",
]

WHOLESALE_REPORT_SECTIONS = [
    "Executive Summary",
    "Business Performance",
    "Sales Analysis",
    "Product Performance",
    "Customer Analysis",
    "Profitability",
    "Inventory Analysis",
    "Purchase/Supplier Analysis",
    "Data Quality",
    "Key Findings",
    "Opportunities",
    "Risks / Warnings",
    "Recommended Actions",
]

WHOLESALE_FINDING_TYPES = [
    "customer_concentration",
    "low_margin_product",
    "declining_product",
    "low_stock",
    "excess_inventory",
    "supplier_concentration",
    "revenue_trend",
]
