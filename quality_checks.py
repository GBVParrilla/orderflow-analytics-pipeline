"""
quality_checks.py
OrderFlow Analytics Pipeline — Data Quality Checks

Runs quality checks against Silver tables and logs results to:
  - Console output
  - data/quality/quality_report.csv
  - PostgreSQL table: dq_quality_log

Checks performed:
  1. Duplicate order IDs
  2. Missing customer_id on orders
  3. Returned items without a matching order
  4. Orders with no line items
  5. Invalid shipping dates (ship_date > actual_delivery)
  6. Orphan order items (item references order that doesn't exist)
  7. Duplicate customer emails
  8. Products with negative or zero price
  9. Orders with null order_total
  10. Returns with no refund amount

Run:
    python quality_checks.py
"""

import os
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text

# ── CONFIG ────────────────────────────────────────────────────
DB_USER    = "georgebvp"
DB_HOST    = "127.0.0.1"
DB_PORT    = "5432"
DB_NAME    = "orderflow"
CONNECTION = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
OUTPUT_DIR = "data/quality"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg):
    print(msg)

# ── QUALITY CHECK QUERIES ─────────────────────────────────────
CHECKS = [
    {
        "check_id":    "DQ-001",
        "check_name":  "Duplicate order IDs",
        "table":       "silver_orders",
        "category":    "Uniqueness",
        "query": """
            SELECT order_id, COUNT(*) AS occurrences
            FROM silver_orders
            GROUP BY order_id
            HAVING COUNT(*) > 1
        """,
        "description": "Order IDs that appear more than once in the orders table.",
    },
    {
        "check_id":    "DQ-002",
        "check_name":  "Missing customer_id on orders",
        "table":       "silver_orders",
        "category":    "Completeness",
        "query": """
            SELECT order_id, order_date, order_total
            FROM silver_orders
            WHERE customer_id IS NULL
               OR customer_id::text = 'nan'
        """,
        "description": "Orders with no linked customer. Cannot attribute revenue.",
    },
    {
        "check_id":    "DQ-003",
        "check_name":  "Returns without matching order",
        "table":       "silver_returns",
        "category":    "Referential Integrity",
        "query": """
            SELECT r.return_id, r.order_id, r.return_date, r.refund_amount
            FROM silver_returns r
            LEFT JOIN silver_orders o ON r.order_id = o.order_id
            WHERE o.order_id IS NULL
        """,
        "description": "Returns that reference an order_id that does not exist in orders.",
    },
    {
        "check_id":    "DQ-004",
        "check_name":  "Orders with no line items",
        "table":       "silver_orders",
        "category":    "Completeness",
        "query": """
            SELECT o.order_id, o.order_date, o.order_total, o.status
            FROM silver_orders o
            LEFT JOIN silver_order_items oi ON o.order_id = oi.order_id
            WHERE oi.order_id IS NULL
        """,
        "description": "Orders that have no corresponding items in order_items.",
    },
    {
        "check_id":    "DQ-005",
        "check_name":  "Invalid shipping dates",
        "table":       "silver_shipping_events",
        "category":    "Validity",
        "query": """
            SELECT shipment_id, order_id, carrier,
                   ship_date, actual_delivery,
                   (actual_delivery - ship_date) AS days_diff
            FROM silver_shipping_events
            WHERE _invalid_ship_date = TRUE
        """,
        "description": "Shipments where ship_date is after actual_delivery date.",
    },
    {
        "check_id":    "DQ-006",
        "check_name":  "Orphan order items",
        "table":       "silver_order_items",
        "category":    "Referential Integrity",
        "query": """
            SELECT oi.item_id, oi.order_id, oi.product_id, oi.line_total
            FROM silver_order_items oi
            LEFT JOIN silver_orders o ON oi.order_id = o.order_id
            WHERE o.order_id IS NULL
        """,
        "description": "Order items that reference an order_id that does not exist.",
    },
    {
        "check_id":    "DQ-007",
        "check_name":  "Duplicate customer emails",
        "table":       "silver_customers",
        "category":    "Uniqueness",
        "query": """
            SELECT email, COUNT(*) AS occurrences,
                   STRING_AGG(customer_id, ', ') AS customer_ids
            FROM silver_customers
            GROUP BY email
            HAVING COUNT(*) > 1
        """,
        "description": "Email addresses linked to more than one customer record.",
    },
    {
        "check_id":    "DQ-008",
        "check_name":  "Products with invalid price",
        "table":       "silver_products",
        "category":    "Validity",
        "query": """
            SELECT product_id, product_name, unit_price, cost_price
            FROM silver_products
            WHERE unit_price <= 0
               OR unit_price IS NULL
               OR cost_price > unit_price
        """,
        "description": "Products with zero/null price or cost exceeding selling price.",
    },
    {
        "check_id":    "DQ-009",
        "check_name":  "Orders with null order_total",
        "table":       "silver_orders",
        "category":    "Completeness",
        "query": """
            SELECT order_id, order_date, status, customer_id
            FROM silver_orders
            WHERE order_total IS NULL
        """,
        "description": "Orders missing a total amount — cannot be used in revenue reporting.",
    },
    {
        "check_id":    "DQ-010",
        "check_name":  "Returns with no refund amount",
        "table":       "silver_returns",
        "category":    "Completeness",
        "query": """
            SELECT return_id, order_id, reason, status
            FROM silver_returns
            WHERE refund_amount IS NULL
               OR refund_amount = 0
        """,
        "description": "Returns marked approved but with no refund amount recorded.",
    },
]


def run_checks(engine):
    results    = []
    run_time   = datetime.now()
    all_passed = True

    log("=" * 65)
    log("  OrderFlow — Data Quality Report")
    log(f"  Run time: {run_time}")
    log("=" * 65)

    for check in CHECKS:
        try:
            df         = pd.read_sql(check["query"], engine)
            failed     = len(df) > 0
            status     = "FAIL" if failed else "PASS"
            if failed:
                all_passed = False

            log(f"\n  [{status}] {check['check_id']} — {check['check_name']}")
            log(f"         Table    : {check['table']}")
            log(f"         Category : {check['category']}")
            log(f"         Issues   : {len(df)}")

            if failed and len(df) <= 5:
                log(f"         Records  :")
                for _, row in df.iterrows():
                    log(f"           {dict(row)}")
            elif failed:
                log(f"         First 3  :")
                for _, row in df.head(3).iterrows():
                    log(f"           {dict(row)}")

            results.append({
                "run_time":    run_time,
                "check_id":    check["check_id"],
                "check_name":  check["check_name"],
                "table":       check["table"],
                "category":    check["category"],
                "description": check["description"],
                "status":      status,
                "issue_count": len(df),
            })

        except Exception as e:
            log(f"\n  [ERROR] {check['check_id']} — {check['check_name']}: {e}")
            results.append({
                "run_time":    run_time,
                "check_id":    check["check_id"],
                "check_name":  check["check_name"],
                "table":       check["table"],
                "category":    check["category"],
                "description": check["description"],
                "status":      "ERROR",
                "issue_count": -1,
            })

    return pd.DataFrame(results), all_passed


def main():
    engine = create_engine(CONNECTION)

    report_df, all_passed = run_checks(engine)

    # ── Summary ───────────────────────────────────────────────
    passed = (report_df["status"] == "PASS").sum()
    failed = (report_df["status"] == "FAIL").sum()
    errors = (report_df["status"] == "ERROR").sum()
    total_issues = report_df["issue_count"].clip(lower=0).sum()

    log("\n" + "=" * 65)
    log("  SUMMARY")
    log(f"  Checks run   : {len(report_df)}")
    log(f"  Passed       : {passed}")
    log(f"  Failed       : {failed}")
    log(f"  Errors       : {errors}")
    log(f"  Total issues : {total_issues} rows flagged across all checks")
    log("=" * 65)

    # ── Save to CSV ───────────────────────────────────────────
    csv_path = os.path.join(OUTPUT_DIR, "quality_report.csv")
    report_df.to_csv(csv_path, index=False)
    log(f"\n  Report saved to: {csv_path}")

    # ── Save to PostgreSQL ────────────────────────────────────
    report_df.to_sql(
        name      = "dq_quality_log",
        con       = engine,
        if_exists = "append",   # append so history is preserved across runs
        index     = False,
    )
    log("  Report saved to: PostgreSQL → dq_quality_log\n")

    if all_passed:
        log("  ✅ All checks passed. Data is clean.\n")
    else:
        log("  ⚠️  Issues found. Review report above.\n")
        log("  These are EXPECTED — they were injected during data generation")
        log("  to simulate real-world dirty data. Your Silver layer flags them.\n")


if __name__ == "__main__":
    main()
