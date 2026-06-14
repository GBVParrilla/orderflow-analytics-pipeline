"""
ingest.py
OrderFlow Analytics Pipeline — Data Ingestion Script

Reads 6 CSV files from data/raw/ and loads them into PostgreSQL.
Logs row counts and timing for each table.

Usage:
    pip install pandas sqlalchemy psycopg2-binary
    python ingest.py
"""

import os
import time
import pandas as pd
from sqlalchemy import create_engine, text

# ── CONFIG ────────────────────────────────────────────────────────────────────
DB_USER     = "georgebvp"
DB_PASSWORD = ""           # blank — we set auth=trust during setup
DB_HOST     = "127.0.0.1"
DB_PORT     = "5432"
DB_NAME     = "orderflow"

RAW_DATA_DIR = "data/raw"

# ── CONNECTION ─────────────────────────────────────────────────────────────────
CONNECTION_STRING = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ── TABLES TO LOAD (order matters — respect foreign keys) ─────────────────────
TABLES = [
    "customers",
    "products",
    "orders",
    "order_items",
    "returns",
    "shipping_events",
]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(msg):
    print(msg)

def load_table(engine, table_name):
    path = os.path.join(RAW_DATA_DIR, f"{table_name}.csv")

    if not os.path.exists(path):
        log(f"  ✗ SKIPPED  {table_name:<22} — file not found at {path}")
        return 0

    start   = time.time()
    df      = pd.read_csv(path)
    rows_in = len(df)

    # Load into PostgreSQL — replace table if it already exists
    df.to_sql(
        name      = table_name,
        con       = engine,
        if_exists = "replace",   # drop and recreate on each run
        index     = False,
    )

    elapsed = round(time.time() - start, 2)
    log(f"  ✓ LOADED   {table_name:<22} {rows_in:>6} rows   ({elapsed}s)")
    return rows_in


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    log("=" * 55)
    log("  OrderFlow Ingestion Pipeline")
    log("=" * 55)
    log(f"  Database : {DB_NAME} @ {DB_HOST}:{DB_PORT}")
    log(f"  Source   : {RAW_DATA_DIR}/")
    log("-" * 55)

    # Connect
    try:
        engine = create_engine(CONNECTION_STRING)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log("  ✓ Connected to PostgreSQL\n")
    except Exception as e:
        log(f"  ✗ Could not connect to database: {e}")
        log("  Make sure PostgreSQL is running:")
        log("    pg_ctl -D /opt/homebrew/var/postgresql@15 start")
        return

    # Load each table
    total_rows  = 0
    start_total = time.time()

    for table in TABLES:
        rows      = load_table(engine, table)
        total_rows += rows

    elapsed_total = round(time.time() - start_total, 2)

    log("-" * 55)
    log(f"  TOTAL: {total_rows} rows loaded in {elapsed_total}s")
    log("=" * 55)

    # Quick row count verification
    log("\n  Verifying row counts in database...")
    log("-" * 55)
    with engine.connect() as conn:
        for table in TABLES:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count  = result.scalar()
                log(f"  {table:<22} {count:>6} rows in DB")
            except Exception as e:
                log(f"  {table:<22} ERROR — {e}")
    log("=" * 55)
    log("\n  Done. Your data is in PostgreSQL and ready to query.")
    log("  Connect with:  psql orderflow\n")


if __name__ == "__main__":
    main()