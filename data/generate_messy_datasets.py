"""Generate genuinely difficult messy datasets for stress-testing the BI engine.

Each dataset is built from a small clean seed with known expected totals, then
deliberately dirtied with real-world messiness:
- Title/blank rows
- Arbitrary/unnamed/duplicate column headers
- Repeated headers mid-file
- Subtotals/totals/footers
- Duplicate records
- Inconsistent names/spelling/capitalization
- Mixed date formats
- Currency symbols and different number formats
- Numeric strings, percentages, negatives/parentheses
- Null-like values
- Irrelevant columns
- Malformed rows
- Multiple Excel sheets (for xlsx)
- Missing/optional columns
"""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from openpyxl import Workbook

random.seed(42)
np.random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
MESSY_DIR = os.path.join(DATA_DIR, "messy")
os.makedirs(MESSY_DIR, exist_ok=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

NULL_LIKES = ["", "N/A", "null", "NULL", "none", "NONE", "-", "--", "n/a", "NA", "nan"]

DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
    "%d.%m.%Y", "%Y/%m/%d", "%d %b %Y", "%b %d, %Y",
    "%d/%m/%y", "%m/%d/%y",
]

CURRENCY_SYMBOLS = ["$", "€", "£", "₺"]


def random_null_like():
    return random.choice(NULL_LIKES)


def format_number_messy(value):
    """Return a number in a random messy format."""
    fmt = random.choice([
        "plain", "comma_thousands", "currency", "european",
        "parentheses_neg", "percent", "space_thousands", "suffix",
    ])
    if fmt == "plain":
        return str(round(value, 2))
    elif fmt == "comma_thousands":
        return f"{value:,.2f}"
    elif fmt == "currency":
        sym = random.choice(CURRENCY_SYMBOLS)
        return f"{sym}{value:,.2f}"
    elif fmt == "european":
        s = f"{value:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    elif fmt == "parentheses_neg" and value < 0:
        return f"({abs(value):,.2f})"
    elif fmt == "parentheses_neg":
        return f"{value:,.2f}"
    elif fmt == "percent":
        return f"{value:.1f}%"
    elif fmt == "space_thousands":
        return f"{value:,.2f}".replace(",", " ")
    elif fmt == "suffix":
        suffix = random.choice(["USD", "EUR", "TRY"])
        return f"{value:,.2f} {suffix}"
    return str(round(value, 2))


def format_date_messy(dt):
    """Return a date in a random format, sometimes malformed."""
    if random.random() < 0.05:
        return random_null_like()
    fmt = random.choice(DATE_FORMATS)
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)


def messy_name(name):
    """Return a name with random casing/spacing variations."""
    variants = [
        name,
        name.upper(),
        name.lower(),
        name.title(),
        "  " + name + "  ",
        name.replace(" ", "  "),
        name + " ",
    ]
    return random.choice(variants)


def write_messy_csv(filepath, rows):
    """Write rows to CSV without header (header is embedded in data)."""
    df = pd.DataFrame(rows)
    df.to_csv(filepath, index=False, header=False)


def write_messy_xlsx(filepath, sheets):
    """Write multiple sheets to an xlsx file with raw data (no pandas header)."""
    wb = Workbook()
    # Remove default sheet
    wb.remove(wb.active)
    for sheet_name, rows in sheets.items():
        ws = wb.create_sheet(title=sheet_name)
        for row in rows:
            ws.append(row)
    wb.save(filepath)


# ── Wholesale messy dataset ───────────────────────────────────────────────────

def generate_messy_wholesale():
    """Messy wholesale export with sales, inventory, and purchases."""
    dates = pd.date_range("2026-01-01", "2026-06-30", freq="D")
    products = ["Premium Widget", "Standard Widget", "Budget Widget", "Gadget Pro", "Gadget Lite"]
    customers = ["MegaMart Corp", "SuperStore Inc", "BigBuy Distribution", "Small Dealer Co"]

    # ── Sales sheet ──
    sales_rows = []
    # Title rows
    sales_rows.append(["WHOLESALE SALES REPORT", "", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["Period: Jan-Jun 2026", "", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["", "", "", "", "", "", "", "", "", "", ""])
    # Header with unnamed column and duplicate column
    sales_rows.append(["Date", "Invoice #", "Customer Name", "Product", "Qty", "Unit Price", "Amount", "Cost", "", "Notes", "Amount"])
    # Subtotal row after header (sneaky)
    sales_rows.append(["", "", "", "", "", "", "Subtotal:", "", "", "", ""])

    expected_revenue = 0
    expected_cost = 0
    expected_qty = 0

    for date in dates:
        n_txns = random.randint(3, 12)
        for _ in range(n_txns):
            product = random.choice(products)
            customer = random.choice(customers)
            qty = random.randint(10, 200)
            unit_price = round(random.uniform(20, 300), 2)
            revenue = round(qty * unit_price, 2)
            cost = round(revenue * random.uniform(0.6, 0.85), 2)
            expected_revenue += revenue
            expected_cost += cost
            expected_qty += qty

            # Sometimes use messy names
            cust_name = messy_name(customer) if random.random() < 0.3 else customer
            prod_name = messy_name(product) if random.random() < 0.3 else product

            # Messy number formats
            rev_str = format_number_messy(revenue) if random.random() < 0.5 else revenue
            cost_str = format_number_messy(cost) if random.random() < 0.5 else cost
            qty_val = qty if random.random() < 0.7 else str(qty)

            # Sometimes null-like values
            if random.random() < 0.05:
                rev_str = random_null_like()
            if random.random() < 0.05:
                cost_str = random_null_like()

            # Irrelevant column data
            note = random.choice(["", "VIP", "", "", "rush order", "", "", "", random_null_like()])

            sales_rows.append([
                format_date_messy(date),
                f"INV-{random.randint(100000, 999999)}",
                cust_name, prod_name, qty_val, unit_price, rev_str, cost_str, "", note, rev_str
            ])

    # Duplicate records
    if len(sales_rows) > 20:
        for _ in range(8):
            sales_rows.append(sales_rows[random.randint(4, len(sales_rows) - 1)])

    # Footer rows
    sales_rows.append(["", "", "", "", "", "", "TOTAL:", "", "", "", ""])
    sales_rows.append(["", "", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["End of Report", "", "", "", "", "", "", "", "", "", ""])
    # Repeated header
    sales_rows.append(["Date", "Invoice #", "Customer Name", "Product", "Qty", "Unit Price", "Amount", "Cost", "", "Notes", "Amount"])

    # ── Inventory sheet ──
    inv_rows = []
    inv_rows.append(["INVENTORY STATUS", "", "", "", "", ""])
    inv_rows.append(["As of 30/06/2026", "", "", "", "", ""])
    inv_rows.append(["", "", "", "", "", ""])
    inv_rows.append(["Product Name", "Category", "Stock Level", "Reorder Level", "Unit Cost", ""])

    for prod in products:
        if prod == "Budget Widget":
            stock = random.randint(1, 5)
        else:
            stock = random.randint(50, 500)
        reorder = random.randint(20, 50)
        unit_cost = round(random.uniform(10, 200), 2)
        stock_val = format_number_messy(stock) if random.random() < 0.4 else stock
        inv_rows.append([messy_name(prod), "Widgets" if "Widget" in prod else "Gadgets", stock_val, reorder, unit_cost, ""])

    # Malformed row
    inv_rows.append(["", "", "", "", "", ""])
    inv_rows.append(["TOTAL STOCK", "", "", "", "", ""])

    # ── Purchases sheet ──
    pur_rows = []
    pur_rows.append(["PURCHASES LOG", "", "", "", "", ""])
    pur_rows.append(["", "", "", "", "", ""])
    pur_rows.append(["Supplier", "Date", "Product", "Quantity", "Total Cost", ""])

    suppliers = ["Supplier Alpha", "Supplier Beta", "Vendor 1", "Vendor 2"]
    for date in dates[::3]:  # Every 3rd day
        supplier = random.choice(suppliers)
        product = random.choice(products)
        qty = random.randint(20, 150)
        cost = round(qty * random.uniform(10, 200), 2)
        pur_rows.append([
            messy_name(supplier) if random.random() < 0.3 else supplier,
            format_date_messy(date),
            product, qty,
            format_number_messy(cost) if random.random() < 0.5 else cost,
            ""
        ])

    # Footer
    pur_rows.append(["", "", "", "", "", ""])
    pur_rows.append(["GRAND TOTAL", "", "", "", "", ""])

    write_messy_xlsx(os.path.join(MESSY_DIR, "messy_wholesale.xlsx"), {
        "Sales": sales_rows,
        "Inventory": inv_rows,
        "Purchases": pur_rows,
    })

    # Also write sales as CSV
    write_messy_csv(os.path.join(MESSY_DIR, "messy_wholesale_sales.csv"), sales_rows)

    # Save expected values for test verification
    return {
        "expected_revenue": round(expected_revenue, 2),
        "expected_cost": round(expected_cost, 2),
        "expected_qty": expected_qty,
    }


# ── Retail messy dataset ──────────────────────────────────────────────────────

def generate_messy_retail():
    """Messy retail export with sales and inventory."""
    dates = pd.date_range("2026-01-01", "2026-06-30", freq="D")
    products = ["Bread", "Milk", "Soda", "Chips", "Canned Soup", "Frozen Pizza", "Cereal"]
    categories = ["Bakery", "Dairy", "Beverages", "Snacks", "Canned Goods", "Frozen", "Breakfast"]

    # ── Sales ──
    sales_rows = []
    # Title and metadata
    sales_rows.append(["RETAIL STORE DAILY SALES", "", "", "", "", "", "", "", ""])
    sales_rows.append(["Store #12345", "", "", "", "", "", "", "", ""])
    sales_rows.append(["Generated: 2026-07-01", "", "", "", "", "", "", "", ""])
    sales_rows.append(["", "", "", "", "", "", "", "", ""])
    # Header with arbitrary names
    sales_rows.append(["Date", "Receipt", "Product Name", "Category", "Qty", "Price", "Total Amount", "Cost", "Payment"])

    expected_revenue = 0
    expected_cost = 0

    for date in dates:
        n_txns = random.randint(20, 80)
        for _ in range(n_txns):
            idx = random.randint(0, len(products) - 1)
            product = products[idx]
            category = categories[idx]
            qty = random.randint(1, 20)
            price = round(random.uniform(1, 10), 2)
            revenue = round(qty * price, 2)
            cost = round(revenue * random.uniform(0.5, 0.8), 2)
            expected_revenue += revenue
            expected_cost += cost

            # Messy formats
            rev_str = format_number_messy(revenue) if random.random() < 0.4 else revenue
            price_str = format_number_messy(price) if random.random() < 0.3 else price
            cost_str = format_number_messy(cost) if random.random() < 0.4 else cost

            # Null-like values
            if random.random() < 0.03:
                rev_str = random_null_like()
            if random.random() < 0.03:
                cost_str = random_null_like()

            payment = random.choice(["Cash", "Card", "CASH", "card", "", "Mobile", random_null_like()])

            sales_rows.append([
                format_date_messy(date),
                f"R{random.randint(100000, 999999)}",
                messy_name(product) if random.random() < 0.2 else product,
                category, qty, price_str, rev_str, cost_str, payment
            ])

    # Duplicate records
    for _ in range(15):
        sales_rows.append(sales_rows[random.randint(5, len(sales_rows) - 1)])

    # Subtotal row
    sales_rows.append(["", "", "", "", "", "", "SUBTOTAL", "", ""])
    # Blank row
    sales_rows.append(["", "", "", "", "", "", "", "", ""])
    # Footer
    sales_rows.append(["End of Daily Sales Report", "", "", "", "", "", "", "", ""])
    # Repeated header
    sales_rows.append(["Date", "Receipt", "Product Name", "Category", "Qty", "Price", "Total Amount", "Cost", "Payment"])

    # ── Inventory ──
    inv_rows = []
    inv_rows.append(["INVENTORY CHECK", "", "", "", ""])
    inv_rows.append(["", "", "", "", ""])
    inv_rows.append(["Product", "Category", "Stock", "Reorder Point", ""])
    for i, prod in enumerate(products):
        stock = random.randint(5, 300)
        reorder = 30
        inv_rows.append([
            messy_name(prod) if random.random() < 0.3 else prod,
            categories[i],
            format_number_messy(stock) if random.random() < 0.3 else stock,
            reorder, ""
        ])
    inv_rows.append(["", "", "", "", ""])
    inv_rows.append(["TOTAL", "", "", "", ""])

    write_messy_xlsx(os.path.join(MESSY_DIR, "messy_retail.xlsx"), {
        "Sales": sales_rows,
        "Inventory": inv_rows,
    })
    write_messy_csv(os.path.join(MESSY_DIR, "messy_retail_sales.csv"), sales_rows)

    return {
        "expected_revenue": round(expected_revenue, 2),
        "expected_cost": round(expected_cost, 2),
    }


# ── Restaurant messy dataset ─────────────────────────────────────────────────

def generate_messy_restaurant():
    """Messy restaurant export with sales and inventory."""
    dates = pd.date_range("2026-01-01", "2026-06-30", freq="D")
    menu = [
        ("Margherita Pizza", "Pizza", 15, 5),
        ("Pepperoni Pizza", "Pizza", 18, 6),
        ("Caesar Salad", "Salads", 12, 4),
        ("Beef Burger", "Burgers", 14, 6),
        ("Chicken Wings", "Appetizers", 10, 4),
        ("French Fries", "Sides", 5, 1.5),
        ("Soda", "Drinks", 3, 0.5),
        ("Coffee", "Drinks", 4, 1),
        ("Tiramisu", "Desserts", 8, 3),
        ("Bruschetta", "Appetizers", 7, 2.5),
    ]

    # ── Sales ──
    sales_rows = []
    sales_rows.append(["RESTAURANT SALES REPORT", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["La Bella Cucina", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["Q1-Q2 2026", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["", "", "", "", "", "", "", "", "", ""])
    # Header with different naming
    sales_rows.append(["Date", "Order ID", "Item Name", "Category", "Qty", "Price", "Amount", "Cost", "Waiter", "Table"])

    expected_revenue = 0
    expected_cost = 0

    for date in dates:
        day_name = date.strftime("%A")
        if day_name in ("Friday", "Saturday", "Sunday"):
            n_orders = random.randint(40, 100)
        else:
            n_orders = random.randint(15, 50)

        for _ in range(n_orders):
            item, cat, price, cost_per = random.choice(menu)
            qty = random.randint(1, 3)
            revenue = round(qty * price, 2)
            cost = round(qty * cost_per, 2)
            expected_revenue += revenue
            expected_cost += cost

            # Messy formats
            rev_str = format_number_messy(revenue) if random.random() < 0.4 else revenue
            cost_str = format_number_messy(cost) if random.random() < 0.4 else cost

            # Null-like
            if random.random() < 0.04:
                rev_str = random_null_like()
            if random.random() < 0.04:
                cost_str = random_null_like()

            waiter = random.choice(["John", "MARY", "john", "Sarah", "sarah", "", random_null_like()])
            table = random.choice(["T1", "T2", "T5", "", "t3", random_null_like()])

            sales_rows.append([
                format_date_messy(date),
                f"ORD-{random.randint(10000, 99999)}",
                messy_name(item) if random.random() < 0.2 else item,
                cat, qty, price, rev_str, cost_str, waiter, table
            ])

    # Duplicate records
    for _ in range(10):
        sales_rows.append(sales_rows[random.randint(5, len(sales_rows) - 1)])

    # Subtotal and footer
    sales_rows.append(["", "", "", "", "", "", "SUBTOTAL", "", "", ""])
    sales_rows.append(["", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["GRAND TOTAL", "", "", "", "", "", "", "", "", ""])
    sales_rows.append(["", "", "", "", "", "", "", "", "", ""])
    # Repeated header
    sales_rows.append(["Date", "Order ID", "Item Name", "Category", "Qty", "Price", "Amount", "Cost", "Waiter", "Table"])

    # ── Inventory ──
    inv_rows = []
    inv_rows.append(["KITCHEN INVENTORY", "", "", "", ""])
    inv_rows.append(["", "", "", "", ""])
    inv_rows.append(["Menu Item", "Category", "Stock Level", "Reorder Level", ""])
    for item, cat, _, _ in menu:
        stock = random.randint(10, 100)
        reorder = 20
        inv_rows.append([
            messy_name(item) if random.random() < 0.3 else item,
            cat,
            format_number_messy(stock) if random.random() < 0.3 else stock,
            reorder, ""
        ])
    inv_rows.append(["", "", "", "", ""])
    inv_rows.append(["TOTAL", "", "", "", ""])

    write_messy_xlsx(os.path.join(MESSY_DIR, "messy_restaurant.xlsx"), {
        "Sales": sales_rows,
        "Inventory": inv_rows,
    })
    write_messy_csv(os.path.join(MESSY_DIR, "messy_restaurant_sales.csv"), sales_rows)

    return {
        "expected_revenue": round(expected_revenue, 2),
        "expected_cost": round(expected_cost, 2),
    }


if __name__ == "__main__":
    print("Generating messy test datasets...")
    w = generate_messy_wholesale()
    print(f"  messy_wholesale.xlsx: expected revenue={w['expected_revenue']}, cost={w['expected_cost']}, qty={w['expected_qty']}")
    r = generate_messy_retail()
    print(f"  messy_retail.xlsx: expected revenue={r['expected_revenue']}, cost={r['expected_cost']}")
    rest = generate_messy_restaurant()
    print(f"  messy_restaurant.xlsx: expected revenue={rest['expected_revenue']}, cost={rest['expected_cost']}")
    print("\nAll messy datasets generated successfully.")
