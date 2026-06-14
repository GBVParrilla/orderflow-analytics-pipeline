"""
silver.py
OrderFlow Analytics Pipeline — Silver Layer

Reads from Bronze tables, cleans and standardizes, writes to Silver tables.

Cleaning rules applied:
  customers     — strip whitespace, lowercase email, fill null segment
  products      — strip whitespace, fill null stock_qty with 0
  orders        — parse dates, fill null discount_pct with 0, flag null customer_id
  order_items   — cast numeric types, drop rows with null order_id or product_id
  returns       — parse dates, fill null refund_amount with 0
  shipping_events — parse dates, flag invalid dates (ship_date > actual_delivery)

Run:
    python silver.py
"""

import time
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ── CONFIG ────────────────────────────────────────────────────
DB_USER    = "georgebvp"
DB_HOST    = "127.0.0.1"
DB_PORT    = "5432"
DB_NAME    = "orderflow"
CONNECTION = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def log(msg):
    print(msg)

def load_bronze(engine, table):
    return pd.read_sql(f"SELECT * FROM bronze_{table}", engine)

def write_silver(engine, table, df):
    df["_silver_timestamp"] = datetime.now()
    df.to_sql(
        name      = f"silver_{table}",
        con       = engine,
        if_exists = "replace",
        index     = False,
    )

# ── CLEANING FUNCTIONS ────────────────────────────────────────
def clean_customers(df):
    before = len(df)
    # Strip whitespace from string columns
    for col in ["first_name", "last_name", "city", "state", "zip_code", "segment"]:
        df[col] = df[col].astype(str).str.strip()
    # Lowercase and strip email
    df["email"] = df["email"].astype(str).str.strip().str.lower()
    # Fill null segment
    df["segment"] = df["segment"].fillna("Unknown")
    # Parse created_at
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    # Flag duplicate emails
    df["_is_duplicate_email"] = df.duplicated(subset=["email"], keep=False)
    log(f"    Duplicate emails flagged : {df['_is_duplicate_email'].sum()}")
    log(f"    Rows in: {before}  Rows out: {len(df)}")
    return df

def clean_products(df):
    before = len(df)
    for col in ["product_name", "category"]:
        df[col] = df[col].astype(str).str.strip()
    df["stock_qty"]  = df["stock_qty"].fillna(0).astype(int)
    df["is_active"]  = df["is_active"].fillna(True)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["cost_price"] = pd.to_numeric(df["cost_price"], errors="coerce")
    log(f"    Rows in: {before}  Rows out: {len(df)}")
    return df

def clean_orders(df):
    before = len(df)
    df["order_date"]    = pd.to_datetime(df["order_date"],  errors="coerce")
    df["discount_pct"]  = pd.to_numeric(df["discount_pct"], errors="coerce").fillna(0)
    df["order_total"]   = pd.to_numeric(df["order_total"],  errors="coerce")
    df["channel"]       = df["channel"].astype(str).str.strip().str.lower()
    df["status"]        = df["status"].astype(str).str.strip().str.lower()
    df["payment_method"]= df["payment_method"].astype(str).str.strip().str.lower()
    # Flag missing customer_id
    df["_missing_customer_id"] = df["customer_id"].isna()
    # Flag duplicate order_ids
    df["_is_duplicate_order"] = df.duplicated(subset=["order_id"], keep=False)
    log(f"    Missing customer_id      : {df['_missing_customer_id'].sum()}")
    log(f"    Duplicate order_ids      : {df['_is_duplicate_order'].sum()}")
    log(f"    Rows in: {before}  Rows out: {len(df)}")
    return df

def clean_order_items(df):
    before = len(df)
    df["quantity"]   = pd.to_numeric(df["quantity"],   errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df["line_total"] = pd.to_numeric(df["line_total"], errors="coerce")
    # Drop rows with no order_id or product_id (cannot be linked)
    dropped = df[df["order_id"].isna() | df["product_id"].isna()]
    if len(dropped) > 0:
        log(f"    Dropped unlinked rows    : {len(dropped)}")
    df = df.dropna(subset=["order_id", "product_id"])
    log(f"    Rows in: {before}  Rows out: {len(df)}")
    return df

def clean_returns(df):
    before = len(df)
    df["return_date"]    = pd.to_datetime(df["return_date"], errors="coerce")
    df["refund_amount"]  = pd.to_numeric(df["refund_amount"], errors="coerce").fillna(0)
    df["status"]         = df["status"].astype(str).str.strip().str.lower()
    df["reason"]         = df["reason"].astype(str).str.strip()
    log(f"    Rows in: {before}  Rows out: {len(df)}")
    return df

def clean_shipping_events(df):
    before = len(df)
    df["ship_date"]            = pd.to_datetime(df["ship_date"],            errors="coerce")
    df["estimated_delivery"]   = pd.to_datetime(df["estimated_delivery"],   errors="coerce")
    df["actual_delivery"]      = pd.to_datetime(df["actual_delivery"],      errors="coerce")
    df["carrier"]              = df["carrier"].astype(str).str.strip()
    df["status"]               = df["status"].astype(str).str.strip().str.lower()
    # Flag invalid dates: ship_date AFTER actual_delivery
    df["_invalid_ship_date"] = (
        df["ship_date"].notna() &
        df["actual_delivery"].notna() &
        (df["ship_date"] > df["actual_delivery"])
    )
    log(f"    Invalid ship dates flagged: {df['_invalid_ship_date'].sum()}")
    log(f"    Rows in: {before}  Rows out: {len(df)}")
    return df

# ── MAIN ──────────────────────────────────────────────────────
CLEANERS = {
    "customers":       clean_customers,
    "products":        clean_products,
    "orders":          clean_orders,
    "order_items":     clean_order_items,
    "returns":         clean_returns,
    "shipping_events": clean_shipping_events,
}

def main():
    log("=" * 55)
    log("  OrderFlow — Silver Layer")
    log(f"  Timestamp: {datetime.now()}")
    log("=" * 55)

    engine = create_engine(CONNECTION)

    for table, cleaner in CLEANERS.items():
        log(f"\n  Cleaning: {table}")
        start = time.time()
        df    = load_bronze(engine, table)
        df    = cleaner(df)
        write_silver(engine, table, df)
        log(f"  ✓ silver_{table} written  ({round(time.time()-start, 2)}s)")

    log("\n" + "=" * 55)
    log("  Silver layer complete.")
    log("=" * 55)

    log("\n  Verifying Silver tables...")
    with engine.connect() as conn:
        for table in CLEANERS:
            count = conn.execute(text(f"SELECT COUNT(*) FROM silver_{table}")).scalar()
            log(f"  silver_{table:<22} {count:>6} rows")
    log()

if __name__ == "__main__":
    main()
