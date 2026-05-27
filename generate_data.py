"""
generate_data.py
OrderFlow Analytics Pipeline — Fake E-Commerce Dataset Generator

Generates 6 CSV files:
  - customers.csv       (300 rows)
  - products.csv        (100 rows)
  - orders.csv          (500 rows)
  - order_items.csv     (1,000 rows)
  - returns.csv         (80 rows)
  - shipping_events.csv (500 rows)

Run:
    pip install faker pandas
    python generate_data.py
"""

import random
import pandas as pd
from faker import Faker
from datetime import timedelta

fake = Faker()
Faker.seed(42)
random.seed(42)

OUTPUT_DIR = "data/raw"

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 1. CUSTOMERS (300 rows) ───────────────────────────────────────────────────
print("Generating customers...")

STATES = ["VA", "MD", "DC", "NY", "CA", "TX", "FL", "GA", "IL", "WA"]
SEGMENTS = ["Consumer", "Business", "Enterprise"]

customers = []
for i in range(1, 301):
    customers.append({
        "customer_id":   f"CUST-{i:04d}",
        "first_name":    fake.first_name(),
        "last_name":     fake.last_name(),
        "email":         fake.email(),
        "phone":         fake.phone_number(),
        "city":          fake.city(),
        "state":         random.choice(STATES),
        "zip_code":      fake.zipcode(),
        "segment":       random.choice(SEGMENTS),
        "created_at":    fake.date_between(start_date="-3y", end_date="-6m"),
    })

# Inject ~5 duplicate emails for data quality checks
for i in range(5):
    dup = customers[i].copy()
    dup["customer_id"] = f"CUST-{900 + i:04d}"
    dup["first_name"]  = fake.first_name()
    customers.append(dup)

customers_df = pd.DataFrame(customers)
customers_df.to_csv(f"{OUTPUT_DIR}/customers.csv", index=False)
print(f"  ✓ customers.csv — {len(customers_df)} rows")


# ── 2. PRODUCTS (100 rows) ────────────────────────────────────────────────────
print("Generating products...")

CATEGORIES   = ["Electronics", "Clothing", "Home & Kitchen", "Sports", "Books", "Beauty", "Toys", "Automotive"]
PRODUCT_NAMES = {
    "Electronics":    ["Wireless Earbuds", "USB-C Hub", "Laptop Stand", "Mechanical Keyboard", "Webcam", "Monitor"],
    "Clothing":       ["Running Shoes", "Denim Jacket", "Polo Shirt", "Yoga Pants", "Winter Coat", "Sneakers"],
    "Home & Kitchen": ["Air Fryer", "Coffee Maker", "Blender", "Cutting Board", "Knife Set", "Toaster"],
    "Sports":         ["Resistance Bands", "Yoga Mat", "Dumbbell Set", "Jump Rope", "Water Bottle", "Foam Roller"],
    "Books":          ["Data Engineering Fundamentals", "SQL Cookbook", "Python for Data Analysis", "Clean Code", "Designing Data-Intensive Applications"],
    "Beauty":         ["Face Serum", "Moisturizer", "Shampoo", "Lip Balm", "Sunscreen"],
    "Toys":           ["LEGO Set", "Board Game", "Puzzle", "RC Car", "Action Figure"],
    "Automotive":     ["Car Phone Mount", "Dash Cam", "Tire Inflator", "Car Vacuum", "Seat Covers"],
}

products = []
product_id = 1
for category, names in PRODUCT_NAMES.items():
    for name in names:
        price = round(random.uniform(9.99, 299.99), 2)
        products.append({
            "product_id":    f"PROD-{product_id:04d}",
            "product_name":  name,
            "category":      category,
            "unit_price":    price,
            "cost_price":    round(price * random.uniform(0.4, 0.65), 2),
            "stock_qty":     random.randint(0, 500),
            "is_active":     random.choice([True, True, True, False]),  # ~25% inactive
        })
        product_id += 1

# Pad to 100 rows
while len(products) < 100:
    cat = random.choice(CATEGORIES)
    price = round(random.uniform(9.99, 199.99), 2)
    products.append({
        "product_id":  f"PROD-{product_id:04d}",
        "product_name": fake.catch_phrase()[:40],
        "category":    cat,
        "unit_price":  price,
        "cost_price":  round(price * random.uniform(0.4, 0.65), 2),
        "stock_qty":   random.randint(0, 300),
        "is_active":   True,
    })
    product_id += 1

products_df = pd.DataFrame(products[:100])
products_df.to_csv(f"{OUTPUT_DIR}/products.csv", index=False)
print(f"  ✓ products.csv — {len(products_df)} rows")


# ── 3. ORDERS (500 rows) ──────────────────────────────────────────────────────
print("Generating orders...")

STATUSES    = ["completed", "completed", "completed", "shipped", "processing", "cancelled"]
CHANNELS    = ["web", "web", "mobile", "mobile", "in-store", "referral"]
PAYMENT_METHODS = ["credit_card", "debit_card", "paypal", "apple_pay", "gift_card"]

customer_ids = customers_df["customer_id"].tolist()

orders = []
for i in range(1, 501):
    order_date = fake.date_between(start_date="-2y", end_date="today")
    orders.append({
        "order_id":       f"ORD-{i:05d}",
        "customer_id":    random.choice(customer_ids),
        "order_date":     order_date,
        "status":         random.choice(STATUSES),
        "channel":        random.choice(CHANNELS),
        "payment_method": random.choice(PAYMENT_METHODS),
        "discount_pct":   random.choice([0, 0, 0, 5, 10, 15, 20]),
        "order_total":    None,  # will be filled after order_items
    })

# Inject ~5 orders with NULL customer_id for data quality checks
for i in range(5):
    orders[random.randint(0, 499)]["customer_id"] = None

# Inject ~3 duplicate order_ids for data quality checks
for i in range(3):
    dup = orders[i].copy()
    orders.append(dup)

orders_df = pd.DataFrame(orders)
orders_df.to_csv(f"{OUTPUT_DIR}/orders.csv", index=False)
print(f"  ✓ orders.csv — {len(orders_df)} rows")


# ── 4. ORDER ITEMS (1,000 rows) ───────────────────────────────────────────────
print("Generating order_items...")

product_ids    = products_df["product_id"].tolist()
product_prices = dict(zip(products_df["product_id"], products_df["unit_price"]))
order_ids      = [o["order_id"] for o in orders[:500]]  # use non-duplicate orders

order_items = []
item_id = 1

# Distribute ~1,000 items across 500 orders (avg 2 items per order)
for order_id in order_ids:
    num_items = random.choices([1, 2, 3, 4], weights=[40, 35, 15, 10])[0]
    chosen_products = random.sample(product_ids, min(num_items, len(product_ids)))
    for prod_id in chosen_products:
        qty        = random.randint(1, 4)
        unit_price = product_prices[prod_id]
        order_items.append({
            "item_id":    f"ITEM-{item_id:05d}",
            "order_id":   order_id,
            "product_id": prod_id,
            "quantity":   qty,
            "unit_price": unit_price,
            "line_total":  round(qty * unit_price, 2),
        })
        item_id += 1
        if item_id > 1001:
            break
    if item_id > 1001:
        break

# Inject a few items with no matching order (orphan records for DQ checks)
for i in range(4):
    order_items.append({
        "item_id":    f"ITEM-{item_id:05d}",
        "order_id":   f"ORD-GHOST-{i}",   # order that doesn't exist
        "product_id": random.choice(product_ids),
        "quantity":   1,
        "unit_price": 19.99,
        "line_total":  19.99,
    })
    item_id += 1

order_items_df = pd.DataFrame(order_items)
order_items_df.to_csv(f"{OUTPUT_DIR}/order_items.csv", index=False)
print(f"  ✓ order_items.csv — {len(order_items_df)} rows")

# Back-fill order_total in orders from line totals
totals = order_items_df.groupby("order_id")["line_total"].sum().to_dict()
orders_df["order_total"] = orders_df["order_id"].map(totals).round(2)
orders_df.to_csv(f"{OUTPUT_DIR}/orders.csv", index=False)  # overwrite with totals


# ── 5. RETURNS (80 rows) ──────────────────────────────────────────────────────
print("Generating returns...")

RETURN_REASONS = [
    "Defective product", "Wrong item shipped", "Changed mind",
    "Does not fit", "Better price found", "Arrived too late",
    "Not as described", "Duplicate order",
]
RETURN_STATUSES = ["approved", "approved", "pending", "rejected"]

completed_orders = [o["order_id"] for o in orders[:500] if o["status"] == "completed"]
sampled_return_orders = random.sample(completed_orders, min(75, len(completed_orders)))

returns = []
for i, order_id in enumerate(sampled_return_orders):
    order_row   = orders_df[orders_df["order_id"] == order_id].iloc[0]
    return_date = pd.to_datetime(order_row["order_date"]) + timedelta(days=random.randint(3, 30))
    returns.append({
        "return_id":     f"RET-{i+1:04d}",
        "order_id":      order_id,
        "return_date":   return_date.date(),
        "reason":        random.choice(RETURN_REASONS),
        "status":        random.choice(RETURN_STATUSES),
        "refund_amount": round(float(order_row["order_total"]) * random.uniform(0.3, 1.0), 2)
                         if pd.notna(order_row["order_total"]) else None,
    })

# Inject ~5 returns with no matching order (orphan records)
for i in range(5):
    returns.append({
        "return_id":    f"RET-{900+i:04d}",
        "order_id":     f"ORD-MISSING-{i}",
        "return_date":  fake.date_between(start_date="-1y", end_date="today"),
        "reason":       "Defective product",
        "status":       "pending",
        "refund_amount": round(random.uniform(10, 100), 2),
    })

returns_df = pd.DataFrame(returns)
returns_df.to_csv(f"{OUTPUT_DIR}/returns.csv", index=False)
print(f"  ✓ returns.csv — {len(returns_df)} rows")


# ── 6. SHIPPING EVENTS (500 rows) ─────────────────────────────────────────────
print("Generating shipping_events...")

CARRIERS   = ["UPS", "FedEx", "USPS", "DHL", "Amazon Logistics"]
SHIP_STATUS = ["delivered", "delivered", "delivered", "in_transit", "out_for_delivery", "delayed", "lost"]
WAREHOUSES  = ["Dulles-VA", "Baltimore-MD", "Richmond-VA", "Charlotte-NC", "Atlanta-GA"]

shipped_orders = [o["order_id"] for o in orders[:500]
                  if o["status"] in ("completed", "shipped")]
sampled_ship   = random.sample(shipped_orders, min(490, len(shipped_orders)))

shipping_events = []
for i, order_id in enumerate(sampled_ship):
    order_row    = orders_df[orders_df["order_id"] == order_id].iloc[0]
    ship_date    = pd.to_datetime(order_row["order_date"]) + timedelta(days=random.randint(1, 3))
    deliver_days = random.randint(1, 10)
    delivered_at = ship_date + timedelta(days=deliver_days)
    shipping_events.append({
        "shipment_id":     f"SHIP-{i+1:05d}",
        "order_id":        order_id,
        "carrier":         random.choice(CARRIERS),
        "warehouse":       random.choice(WAREHOUSES),
        "ship_date":       ship_date.date(),
        "estimated_delivery": (ship_date + timedelta(days=random.randint(3, 7))).date(),
        "actual_delivery": delivered_at.date() if random.random() > 0.1 else None,
        "status":          random.choice(SHIP_STATUS),
        "tracking_number": fake.bothify(text="??##########??"),
    })

# Inject ~10 shipments with invalid dates (ship_date AFTER delivered_at)
for i in range(10):
    base = fake.date_between(start_date="-1y", end_date="-1m")
    shipping_events.append({
        "shipment_id":        f"SHIP-{9000+i:05d}",
        "order_id":           random.choice(shipped_orders),
        "carrier":            random.choice(CARRIERS),
        "warehouse":          random.choice(WAREHOUSES),
        "ship_date":          base + timedelta(days=5),   # ship AFTER delivery — bad data
        "estimated_delivery": base + timedelta(days=3),
        "actual_delivery":    base,
        "status":             "delivered",
        "tracking_number":    fake.bothify(text="??##########??"),
    })

shipping_events_df = pd.DataFrame(shipping_events)
shipping_events_df.to_csv(f"{OUTPUT_DIR}/shipping_events.csv", index=False)
print(f"  ✓ shipping_events.csv — {len(shipping_events_df)} rows")


# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("\n✅ All files saved to data/raw/\n")
print("─" * 45)
print(f"{'Table':<22} {'Rows':>6}  {'File'}")
print("─" * 45)
for name, df in [
    ("customers",       customers_df),
    ("products",        products_df),
    ("orders",          orders_df),
    ("order_items",     order_items_df),
    ("returns",         returns_df),
    ("shipping_events", shipping_events_df),
]:
    path = f"{OUTPUT_DIR}/{name}.csv"
    size = os.path.getsize(path)
    print(f"  {name:<20} {len(df):>6}  {path}  ({size/1024:.1f} KB)")
print("─" * 45)
print("\nData quality issues injected (for your pipeline to catch):")
print("  • ~5 duplicate emails in customers")
print("  • ~5 NULL customer_id in orders")
print("  • ~3 duplicate order_ids in orders")
print("  • ~4 orphan order_items (no matching order)")
print("  • ~5 orphan returns (no matching order)")
print("  • ~10 invalid ship dates (ship_date > actual_delivery)")