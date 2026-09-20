"""Retail vertical configuration."""

from __future__ import annotations

from app.core.models import EntityType

RETAIL_ENTITIES = [
    {
        "type": EntityType.SALES,
        "name": "sales",
        "required_columns": ["date", "revenue"],
        "optional_columns": ["invoice_id", "product", "category", "quantity", "unit_price", "cost", "payment_method"],
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
        "type": EntityType.PRODUCTS,
        "name": "products",
        "required_columns": ["product"],
        "optional_columns": ["category", "unit_price", "cost"],
        "description": "Product master data",
    },
    {
        "type": EntityType.PURCHASES,
        "name": "purchases",
        "required_columns": ["date"],
        "optional_columns": ["supplier", "product", "quantity", "cost", "total_cost"],
        "description": "Purchase/supplier data",
    },
]

RETAIL_REPORT_SECTIONS = [
    "Executive Summary",
    "Sales Performance",
    "Product Performance",
    "Category Performance",
    "Inventory Intelligence",
    "Profitability",
    "Supplier Analysis",
    "Data Quality",
    "Key Findings",
    "Opportunities",
    "Risks",
    "Recommended Actions",
]
