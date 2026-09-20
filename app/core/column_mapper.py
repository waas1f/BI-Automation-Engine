"""Column mapping: detect and map raw columns to canonical field names."""

from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from app.core.models import ColumnMapping, ColumnType
from app.core.schema_detector import infer_column_type
from app.core.utils import normalize_column_name

# Canonical field definitions with aliases
CANONICAL_FIELDS = {
    # Sales/transaction fields
    "date": {
        "aliases": ["date", "transaction_date", "invoice_date", "order_date", "sales_date", "doc_date", "posting_date", "trx_date"],
        "type": ColumnType.DATE,
    },
    "invoice_id": {
        "aliases": ["invoice_no", "invoice_number", "invoice_id", "invoice", "inv_no", "inv_id", "order_id", "order_number", "transaction_id", "trx_id", "receipt_no", "receipt_number", "doc_no", "document_no", "document_number", "bill_no", "bill_number", "num", "voucher_no", "voucher_number", "txn_no", "entry_no"],
        "type": ColumnType.IDENTIFIER,
    },
    "customer": {
        "aliases": ["customer", "customer_name", "client", "client_name", "customer_id", "account", "account_name", "buyer", "buyer_name", "party", "party_name", "name"],
        "type": ColumnType.CATEGORICAL,
    },
    "customer_id": {
        "aliases": ["customer_id", "customer_code", "client_id", "client_code", "account_id", "account_code", "customer_no"],
        "type": ColumnType.IDENTIFIER,
    },
    "product": {
        "aliases": ["product", "product_name", "item", "item_name", "description", "product_description", "item_description", "sku_name", "menu_item", "dish", "dish_name"],
        "type": ColumnType.CATEGORICAL,
    },
    "product_id": {
        "aliases": ["product_id", "product_code", "item_id", "item_code", "sku", "sku_code", "barcode", "upc", "gtin"],
        "type": ColumnType.IDENTIFIER,
    },
    "category": {
        "aliases": ["category", "product_category", "item_category", "category_name", "group", "product_group", "department", "dept", "type", "menu_category", "cuisine"],
        "type": ColumnType.CATEGORICAL,
    },
    "quantity": {
        "aliases": ["qty", "quantity", "units", "units_sold", "qty_sold", "amount_sold", "count", "volume", "cases", "packs", "qty_ordered", "quantity_sold", "order_qty", "sales_qty", "no_of_units", "number_of_units", "pieces", "qty_purchased", "sold_qty", "ordered_qty", "number_of_items", "item_count", "qty_delivered", "delivered_qty"],
        "type": ColumnType.NUMERIC,
    },
    "unit_price": {
        "aliases": ["unit_price", "price", "price_per_unit", "rate", "selling_price", "unit_rate", "price_each", "unit_cost_price"],
        "type": ColumnType.NUMERIC,
    },
    "revenue": {
        "aliases": ["amount", "revenue", "sales", "sales_amount", "total_amount", "total", "net_amount", "gross_amount", "line_total", "subtotal", "net_sales", "value", "sales_value", "billing_amount", "invoice_amount", "total_sales", "sale_amount", "total_sale_amount", "gross_sales", "net_revenue", "grand_total", "final_amount", "bill_amount", "total_value", "turnover", "revenue_amount", "amount_paid", "total_bill", "order_value", "sale_value", "total_price", "price_total", "sales_total", "amount_due", "total_income", "income", "receipt_amount", "transaction_amount"],
        "type": ColumnType.NUMERIC,
    },
    "cost": {
        "aliases": ["total_cost", "cost_amount", "line_cost", "extended_cost", "total_purchase", "cost", "cogs", "cost_of_goods", "debit", "purchase_amount"],
        "type": ColumnType.NUMERIC,
    },
    "unit_cost": {
        "aliases": ["unit_cost", "cost_price", "purchase_price", "unit_cost_price", "landed_cost", "cost_per_unit"],
        "type": ColumnType.NUMERIC,
    },
    "total_cost": {
        "aliases": ["total_cost", "cost_amount", "line_cost", "extended_cost", "total_purchase"],
        "type": ColumnType.NUMERIC,
    },
    "discount": {
        "aliases": ["discount", "discount_amount", "discount_value", "rebate", "discount_given"],
        "type": ColumnType.NUMERIC,
    },
    "supplier": {
        "aliases": ["supplier", "supplier_name", "vendor", "vendor_name", "supplier_id", "vendor_id"],
        "type": ColumnType.CATEGORICAL,
    },
    "stock_level": {
        "aliases": ["stock", "stock_level", "current_stock", "on_hand", "quantity_on_hand", "stock_qty", "available_stock", "inventory_level", "qty_in_stock"],
        "type": ColumnType.NUMERIC,
    },
    "reorder_level": {
        "aliases": ["reorder_level", "reorder_point", "min_stock", "minimum_stock", "reorder_qty", "min_level", "safety_stock"],
        "type": ColumnType.NUMERIC,
    },
    "payment_method": {
        "aliases": ["payment_method", "payment_type", "payment", "payment_mode", "tender", "tender_type"],
        "type": ColumnType.CATEGORICAL,
    },
    "order_time": {
        "aliases": ["time", "order_time", "transaction_time", "time_of_sale", "sale_time"],
        "type": ColumnType.TEXT,
    },
    "waiter": {
        "aliases": ["waiter", "server", "staff", "employee", "employee_name", "server_name", "attendant"],
        "type": ColumnType.CATEGORICAL,
    },
    "table_number": {
        "aliases": ["table", "table_number", "table_no", "table_id"],
        "type": ColumnType.CATEGORICAL,
    },
}

# Build a lookup from normalized alias -> canonical field
_ALIAS_INDEX: dict[str, str] = {}
for canonical, info in CANONICAL_FIELDS.items():
    for alias in info["aliases"]:
        norm = normalize_column_name(alias)
        _ALIAS_INDEX[norm] = canonical
    _ALIAS_INDEX[normalize_column_name(canonical)] = canonical


def _fuzzy_match(raw_norm: str, threshold: float = 0.85) -> tuple[str | None, float]:
    """Find the best fuzzy match for a normalized column name."""
    best_match = None
    best_score = 0.0
    for alias_norm, canonical in _ALIAS_INDEX.items():
        score = SequenceMatcher(None, raw_norm, alias_norm).ratio()
        if score > best_score:
            best_score = score
            best_match = canonical
    if best_score >= threshold:
        return best_match, best_score
    return None, 0.0


def map_columns(df: pd.DataFrame) -> list[ColumnMapping]:
    """Map raw column names to canonical fields.

    Uses exact alias matching first, then fuzzy matching with confidence scoring.
    """
    mappings = []
    used_canonical = set()

    # First pass: exact alias matches
    for col in df.columns:
        raw_norm = normalize_column_name(str(col))
        if raw_norm in _ALIAS_INDEX:
            canonical = _ALIAS_INDEX[raw_norm]
            if canonical not in used_canonical:
                mappings.append(
                    ColumnMapping(
                        raw_name=str(col),
                        canonical=canonical,
                        confidence=1.0,
                        method="exact_alias",
                    )
                )
                used_canonical.add(canonical)
            else:
                mappings.append(
                    ColumnMapping(
                        raw_name=str(col),
                        canonical=None,
                        confidence=0.0,
                        method="skipped_duplicate",
                        notes=f"Canonical field '{canonical}' already mapped",
                    )
                )
        else:
            mappings.append(
                ColumnMapping(raw_name=str(col), canonical=None, confidence=0.0, method="unmapped")
            )

    # Second pass: fuzzy matching for unmapped columns
    for i, mapping in enumerate(mappings):
        if mapping.canonical is not None:
            continue
        raw_norm = normalize_column_name(mapping.raw_name)
        match, score = _fuzzy_match(raw_norm, threshold=0.85)
        if match and match not in used_canonical:
            # Verify type compatibility
            expected_type = CANONICAL_FIELDS[match]["type"]
            actual_type = infer_column_type(df[mapping.raw_name], mapping.raw_name)
            type_compatible = (
                expected_type == actual_type
                or (expected_type == ColumnType.NUMERIC and actual_type == ColumnType.NUMERIC)
                or (expected_type in (ColumnType.CATEGORICAL, ColumnType.TEXT) and actual_type in (ColumnType.CATEGORICAL, ColumnType.TEXT))
            )
            if type_compatible or score >= 0.9:
                mappings[i] = ColumnMapping(
                    raw_name=mapping.raw_name,
                    canonical=match,
                    confidence=round(score, 2),
                    method="fuzzy",
                    notes=f"Fuzzy match (score={score:.2f})",
                )
                used_canonical.add(match)

    return mappings


def apply_column_mappings(df: pd.DataFrame, mappings: list[ColumnMapping]) -> pd.DataFrame:
    """Rename columns based on the mapping results. Keeps original names for unmapped columns."""
    rename_map = {}
    for m in mappings:
        if m.canonical:
            rename_map[m.raw_name] = m.canonical
    return df.rename(columns=rename_map)


def get_mapped_columns(mappings: list[ColumnMapping]) -> dict[str, str]:
    """Return a dict of canonical -> raw_name for successfully mapped columns."""
    result = {}
    for m in mappings:
        if m.canonical:
            result[m.canonical] = m.raw_name
    return result
