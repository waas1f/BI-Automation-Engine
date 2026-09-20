"""Generate realistic synthetic test datasets for the BI engine."""

import os
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SAMPLE_DIR = os.path.join(DATA_DIR, "sample")
TEST_DIR = os.path.join(DATA_DIR, "test")

os.makedirs(SAMPLE_DIR, exist_ok=True)
os.makedirs(TEST_DIR, exist_ok=True)


def generate_clean_dataset():
    """Perfectly structured clean dataset."""
    dates = pd.date_range("2026-01-01", "2026-06-30", freq="D")
    products = ["Widget A", "Widget B", "Widget C", "Gadget X", "Gadget Y"]
    customers = ["Customer Alpha", "Customer Beta", "Customer Gamma", "Customer Delta", "Customer Epsilon"]

    rows = []
    for date in dates:
        n_txns = random.randint(5, 20)
        for _ in range(n_txns):
            product = random.choice(products)
            customer = random.choice(customers)
            qty = random.randint(1, 100)
            unit_price = round(random.uniform(10, 500), 2)
            revenue = round(qty * unit_price, 2)
            cost = round(revenue * random.uniform(0.6, 0.85), 2)
            rows.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Invoice Number": f"INV-{random.randint(10000, 99999)}",
                "Customer": customer,
                "Product": product,
                "Quantity": qty,
                "Unit Price": unit_price,
                "Revenue": revenue,
                "Cost": cost,
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SAMPLE_DIR, "clean_sales.csv"), index=False)
    print(f"Generated clean_sales.csv: {len(df)} rows")


def generate_messy_dataset():
    """Dataset with title rows, blank rows, inconsistent formatting, duplicates, etc."""
    dates = pd.date_range("2026-01-01", "2026-06-30", freq="D")
    products = ["Widget A", "Widget B", "Widget C", "Gadget X", "Gadget Y"]
    customers = ["Customer Alpha", "customer alpha", "CUSTOMER ALPHA", "Customer Beta", "Customer  Gamma "]

    rows = []
    # Title rows
    rows.append(["Monthly Sales Report", "", "", "", "", "", "", ""])
    rows.append(["Generated: 15/09/2026", "", "", "", "", "", "", ""])
    rows.append(["", "", "", "", "", "", "", ""])
    # Header row starts on row 4
    rows.append(["Date", "Invoice #", "Customer Name", "Product", "Qty", "Unit Price", "Amount", "Cost"])

    for date in dates:
        n_txns = random.randint(3, 15)
        for _ in range(n_txns):
            product = random.choice(products)
            customer = random.choice(customers)
            qty = random.randint(1, 100)
            unit_price = round(random.uniform(10, 500), 2)
            # Messy currency formats
            fmt = random.choice(["currency", "plain", "comma", "european"])
            if fmt == "currency":
                revenue_str = f"${qty * unit_price:,.2f}"
            elif fmt == "plain":
                revenue_str = str(round(qty * unit_price, 2))
            elif fmt == "comma":
                revenue_str = f"{qty * unit_price:,.2f}"
            else:
                revenue_str = f"{qty * unit_price:.2f}".replace(".", ",")

            cost_val = round(qty * unit_price * random.uniform(0.6, 0.85), 2)
            # Messy date formats
            date_fmt = random.choice(["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%b %d %Y"])
            date_str = date.strftime(date_fmt)

            rows.append([date_str, f"INV-{random.randint(10000, 99999)}", customer, product, qty, unit_price, revenue_str, cost_val])

    # Add some duplicates
    if len(rows) > 10:
        for _ in range(5):
            rows.append(rows[random.randint(4, len(rows) - 1)])

    # Add summary rows
    rows.append(["", "", "", "", "", "", "TOTAL:", ""])
    rows.append(["", "", "", "", "", "", "", ""])

    # Add a repeated header
    rows.append(["Date", "Invoice #", "Customer Name", "Product", "Qty", "Unit Price", "Amount", "Cost"])

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(TEST_DIR, "messy_sales.csv"), index=False, header=False)
    print(f"Generated messy_sales.csv: {len(df)} rows")


def generate_edge_case_dataset():
    """Dataset with edge cases: empty columns, zero revenue, negative values, etc."""
    dates = pd.date_range("2026-01-01", "2026-03-31", freq="D")
    products = ["Product A", "Product B", "Product C", "Product D"]
    customers = ["Customer 1", "Customer 2", "Customer 3"]

    rows = []
    for date in dates:
        n_txns = random.randint(2, 10)
        for _ in range(n_txns):
            product = random.choice(products)
            customer = random.choice(customers)
            qty = random.randint(1, 50)

            # Edge cases in revenue
            rev_choice = random.random()
            if rev_choice < 0.1:
                revenue = 0  # Zero revenue
            elif rev_choice < 0.15:
                revenue = -round(random.uniform(10, 100), 2)  # Negative (refund)
            elif rev_choice < 0.2:
                revenue = None  # Missing
            else:
                revenue = round(qty * random.uniform(10, 200), 2)

            # Edge cases in cost
            cost_choice = random.random()
            if cost_choice < 0.3:
                cost = None  # Missing cost
            else:
                cost = round(revenue * random.uniform(0.5, 0.9), 2) if revenue and revenue > 0 else 0

            # Sometimes malformed date
            if random.random() < 0.1:
                date_str = "N/A"
            else:
                date_str = date.strftime("%Y-%m-%d")

            # Large numbers sometimes
            if random.random() < 0.05:
                revenue = 9999999.99

            rows.append({
                "Date": date_str,
                "Invoice No": f"INV-{random.randint(10000, 99999)}",
                "Customer": customer,
                "Product": product,
                "Quantity": qty,
                "Revenue": revenue,
                "Cost": cost,
                "Empty Column": None,
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(TEST_DIR, "edge_case_sales.csv"), index=False)
    print(f"Generated edge_case_sales.csv: {len(df)} rows")


def generate_wholesale_dataset():
    """Wholesale dataset with deliberate patterns."""
    dates = pd.date_range("2026-01-01", "2026-08-31", freq="D")

    # Customer concentration: 3 big customers + many small ones
    big_customers = ["MegaMart Corp", "SuperStore Inc", "BigBuy Distribution"]
    small_customers = [f"Small Dealer {i}" for i in range(1, 30)]

    # Products with different patterns
    products = {
        "Premium Widget": {"price": 150, "cost": 120, "low_margin": True, "high_volume": True},
        "Standard Widget": {"price": 80, "cost": 50, "low_margin": False, "high_volume": True},
        "Budget Widget": {"price": 30, "cost": 18, "low_margin": False, "high_volume": False},
        "Declining Product": {"price": 100, "cost": 65, "declining": True},
        "Low Stock Item": {"price": 200, "cost": 130},
        "Gadget Pro": {"price": 250, "cost": 175},
        "Gadget Lite": {"price": 90, "cost": 55},
    }

    rows = []
    for date in dates:
        n_txns = random.randint(10, 40)
        for _ in range(n_txns):
            # Customer concentration: 65% from top 3
            if random.random() < 0.65:
                customer = random.choice(big_customers)
            else:
                customer = random.choice(small_customers)

            product_name = random.choice(list(products.keys()))
            prod = products[product_name]

            # Declining product: decreasing sales over time
            if prod.get("declining"):
                months_elapsed = (date - pd.Timestamp("2026-01-01")).days / 30
                if random.random() < max(0.8 - months_elapsed * 0.1, 0.1):
                    continue

            qty = random.randint(10, 500)
            revenue = round(qty * prod["price"], 2)
            cost = round(qty * prod["cost"], 2)

            rows.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Invoice #": f"INV-{random.randint(100000, 999999)}",
                "Customer Name": customer,
                "Product": product_name,
                "Qty": qty,
                "Unit Price": prod["price"],
                "Amount": revenue,
                "Cost": cost,
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SAMPLE_DIR, "wholesale_sales.csv"), index=False)
    print(f"Generated wholesale_sales.csv: {len(df)} rows")

    # Inventory data
    inv_rows = []
    for prod_name, prod in products.items():
        if prod_name == "Low Stock Item":
            stock = random.randint(1, 5)
            reorder = 20
        else:
            stock = random.randint(50, 500)
            reorder = random.randint(20, 50)

        inv_rows.append({
            "Product": prod_name,
            "Category": "Widgets" if "Widget" in prod_name else "Gadgets",
            "Stock Level": stock,
            "Reorder Level": reorder,
            "Unit Cost": prod["cost"],
        })

    inv_df = pd.DataFrame(inv_rows)
    inv_df.to_csv(os.path.join(SAMPLE_DIR, "wholesale_inventory.csv"), index=False)
    print(f"Generated wholesale_inventory.csv: {len(inv_df)} rows")

    # Purchase data with supplier concentration
    big_suppliers = ["Supplier Alpha", "Supplier Beta"]
    small_suppliers = [f"Vendor {i}" for i in range(1, 15)]
    rows = []
    for date in dates:
        n_purchases = random.randint(2, 8)
        for _ in range(n_purchases):
            if random.random() < 0.70:
                supplier = random.choice(big_suppliers)
            else:
                supplier = random.choice(small_suppliers)
            product = random.choice(list(products.keys()))
            prod = products[product]
            qty = random.randint(20, 200)
            cost = round(qty * prod["cost"], 2)
            rows.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Supplier": supplier,
                "Product": product,
                "Quantity": qty,
                "Total Cost": cost,
            })

    pur_df = pd.DataFrame(rows)
    pur_df.to_csv(os.path.join(SAMPLE_DIR, "wholesale_purchases.csv"), index=False)
    print(f"Generated wholesale_purchases.csv: {len(pur_df)} rows")


def generate_retail_dataset():
    """Retail dataset with fast/slow movers, category margins, etc."""
    dates = pd.date_range("2026-01-01", "2026-08-31", freq="D")

    products = {
        "Bread": {"category": "Bakery", "price": 2.50, "cost": 1.00, "fast": True},
        "Milk": {"category": "Dairy", "price": 1.80, "cost": 1.20, "fast": True},
        "Soda": {"category": "Beverages", "price": 3.00, "cost": 1.00, "fast": True},
        "Chips": {"category": "Snacks", "price": 4.00, "cost": 2.50, "fast": False},
        "Canned Soup": {"category": "Canned Goods", "price": 2.20, "cost": 1.80, "slow": True},
        "Frozen Pizza": {"category": "Frozen", "price": 5.50, "cost": 3.00},
        "Cereal": {"category": "Breakfast", "price": 4.50, "cost": 2.00},
        "Pasta": {"category": "Dry Goods", "price": 1.50, "cost": 0.80},
        "Cooking Oil": {"category": "Pantry", "price": 6.00, "cost": 4.50},
        "Spices": {"category": "Pantry", "price": 3.50, "cost": 1.00},
    }

    rows = []
    for date in dates:
        n_txns = random.randint(50, 200)
        for _ in range(n_txns):
            product_name = random.choice(list(products.keys()))
            prod = products[product_name]

            # Fast movers sell more
            if prod.get("fast"):
                qty = random.randint(5, 30)
            elif prod.get("slow"):
                qty = random.randint(1, 3)
            else:
                qty = random.randint(2, 10)

            revenue = round(qty * prod["price"], 2)
            cost = round(qty * prod["cost"], 2)

            rows.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Receipt No": f"R{random.randint(100000, 999999)}",
                "Product": product_name,
                "Category": prod["category"],
                "Quantity": qty,
                "Unit Price": prod["price"],
                "Amount": revenue,
                "Cost": cost,
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SAMPLE_DIR, "retail_sales.csv"), index=False)
    print(f"Generated retail_sales.csv: {len(df)} rows")

    # Inventory data with excess stock for slow movers
    inv_rows = []
    for prod_name, prod in products.items():
        if prod.get("slow"):
            stock = random.randint(200, 500)  # Excess
        elif prod.get("fast"):
            stock = random.randint(5, 20)  # Low
        else:
            stock = random.randint(30, 100)

        inv_rows.append({
            "Product": prod_name,
            "Category": prod["category"],
            "Stock Level": stock,
            "Reorder Level": 30,
        })

    inv_df = pd.DataFrame(inv_rows)
    inv_df.to_csv(os.path.join(SAMPLE_DIR, "retail_inventory.csv"), index=False)
    print(f"Generated retail_inventory.csv: {len(inv_df)} rows")


def generate_restaurant_dataset():
    """Restaurant dataset with peak days, best sellers, weak items, etc."""
    dates = pd.date_range("2026-01-01", "2026-08-31", freq="D")

    menu = {
        "Margherita Pizza": {"category": "Pizza", "price": 15, "cost": 5, "best": True},
        "Pepperoni Pizza": {"category": "Pizza", "price": 18, "cost": 6},
        "Caesar Salad": {"category": "Salads", "price": 12, "cost": 4},
        "Beef Burger": {"category": "Burgers", "price": 14, "cost": 6},
        "Chicken Wings": {"category": "Appetizers", "price": 10, "cost": 4},
        "French Fries": {"category": "Sides", "price": 5, "cost": 1.50},
        "Soda": {"category": "Drinks", "price": 3, "cost": 0.50},
        "Coffee": {"category": "Drinks", "price": 4, "cost": 1},
        "Tiramisu": {"category": "Desserts", "price": 8, "cost": 3},
        "Bruschetta": {"category": "Appetizers", "price": 7, "cost": 2.50, "weak": True},
    }

    rows = []
    for date in dates:
        day_name = date.strftime("%A")
        # Peak days: Friday, Saturday, Sunday
        if day_name in ("Friday", "Saturday", "Sunday"):
            n_orders = random.randint(80, 150)
        else:
            n_orders = random.randint(30, 60)

        for _ in range(n_orders):
            item = random.choice(list(menu.keys()))
            m = menu[item]

            # Best seller sells more
            if m.get("best"):
                qty = random.randint(2, 5)
            elif m.get("weak"):
                if random.random() < 0.7:  # Often skipped
                    continue
                qty = 1
            else:
                qty = random.randint(1, 3)

            revenue = round(qty * m["price"], 2)
            cost = round(qty * m["cost"], 2)

            rows.append({
                "Date": date.strftime("%Y-%m-%d"),
                "Order ID": f"ORD-{random.randint(10000, 99999)}",
                "Item": item,
                "Category": m["category"],
                "Quantity": qty,
                "Price": m["price"],
                "Amount": revenue,
                "Cost": cost,
            })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(SAMPLE_DIR, "restaurant_sales.csv"), index=False)
    print(f"Generated restaurant_sales.csv: {len(df)} rows")

    # Inventory
    inv_rows = []
    for item, m in menu.items():
        inv_rows.append({
            "Item": item,
            "Category": m["category"],
            "Stock Level": random.randint(10, 100),
            "Reorder Level": 20,
        })

    inv_df = pd.DataFrame(inv_rows)
    inv_df.to_csv(os.path.join(SAMPLE_DIR, "restaurant_inventory.csv"), index=False)
    print(f"Generated restaurant_inventory.csv: {len(inv_df)} rows")


if __name__ == "__main__":
    print("Generating synthetic datasets...")
    generate_clean_dataset()
    generate_messy_dataset()
    generate_edge_case_dataset()
    generate_wholesale_dataset()
    generate_retail_dataset()
    generate_restaurant_dataset()
    print("\nAll datasets generated successfully.")
