"""
bronze.py
OrderFlow Analytics Pipeline — Bronze Layer

Loads raw CSVs into the database as-is with an ingest timestamp.
No cleaning. No transformations. Raw data exactly as received.

Run:
    python bronze.py
"""

import os
import time
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ── CONFIG ────────────────────────────────────────────────────
DB_USER      = "georgebvp"
DB_HOST      = "127.0.0.1"
DB_PORT      = "5432"
DB_NAME      = "orderflow"
RAW_DATA_DIR = "data/raw"
CONNECTION   = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

TABLES = [
    "customers",
    "products",
    "orders",
    "order_items",
    "returns",
    "shipping_events",
]

def log(msg):
    print(msg)

def main():
    log("=" * 55)
    log("  OrderFlow — Bronze Layer")
    log(f"  Ingest timestamp: {datetime.now()}")
    log("=" * 55)

    engine = create_engine(CONNECTION)
    ingest_ts = datetime.now()
    total_rows = 0

    for table in TABLES:
        path = os.path.join(RAW_DATA_DIR, f"{table}.csv")
        if not os.path.exists(path):
            log(f"  ✗ SKIPPED  {table:<22} file not found")
            continue

        start = time.time()
        df = pd.read_csv(path)

        # Add ingest metadata columns
        df["_ingest_timestamp"] = ingest_ts
        df["_source_file"]      = f"{table}.csv"
        df["_row_count"]        = len(df)

        df.to_sql(
            name      = f"bronze_{table}",
            con       = engine,
            if_exists = "replace",
            index     = False,
        )

        elapsed = round(time.time() - start, 2)
        log(f"  ✓ bronze_{table:<22} {len(df):>6} rows  ({elapsed}s)")
        total_rows += len(df)

    log("-" * 55)
    log(f"  TOTAL: {total_rows} rows loaded into Bronze")
    log("=" * 55)

    # Verify
    log("\n  Verifying Bronze tables...")
    with engine.connect() as conn:
        for table in TABLES:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM bronze_{table}")).scalar()
                log(f"  bronze_{table:<22} {count:>6} rows")
            except Exception as e:
                log(f"  bronze_{table:<22} ERROR — {e}")
    log("\n  Bronze layer complete.\n")

if __name__ == "__main__":
    main()
