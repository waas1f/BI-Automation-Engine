"""Restaurant vertical configuration."""

from __future__ import annotations

from app.core.models import EntityType

RESTAURANT_ENTITIES = [
    {
        "type": EntityType.SALES,
        "name": "sales",
        "required_columns": ["date", "revenue"],
        "optional_columns": ["invoice_id", "product", "category", "quantity", "unit_price", "cost", "order_time", "waiter", "table_number"],
        "description": "Sales/order data",
    },
    {
        "type": EntityType.MENU,
        "name": "menu",
        "required_columns": ["product"],
        "optional_columns": ["category", "unit_price", "cost"],
        "description": "Menu item data",
    },
    {
        "type": EntityType.INVENTORY,
        "name": "inventory",
        "required_columns": ["product"],
        "optional_columns": ["stock_level", "reorder_level", "category", "cost"],
        "description": "Inventory/stock data",
    },
    {
        "type": EntityType.PURCHASES,
        "name": "purchases",
        "required_columns": ["date"],
        "optional_columns": ["supplier", "product", "quantity", "cost", "total_cost"],
        "description": "Purchase/supplier data",
    },
]

RESTAURANT_REPORT_SECTIONS = [
    "Executive Summary",
    "Revenue & Order Performance",
    "Menu Performance",
    "Category Performance",
    "Profitability",
    "Inventory",
    "Customer/Order Behavior",
    "Data Quality",
    "Key Findings",
    "Opportunities",
    "Risks",
    "Recommended Actions",
]
