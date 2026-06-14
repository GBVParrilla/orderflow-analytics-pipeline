"""
gold.py
OrderFlow Analytics Pipeline — Gold Layer

Reads from Silver tables, applies SQL transformations using CTEs,
and writes reporting-ready Gold tables.

Gold tables produced:
  gold_revenue_by_category     — total revenue, units sold, avg price by product category
  gold_monthly_order_summary   — monthly order counts, revenue, AOV, channel breakdown
  gold_return_rate_by_product  — return rate per product, total returns, refund amounts
  gold_customer_lifetime_value — total spent, order count, avg order value per customer
  gold_fulfillment_summary     — avg delivery days, on-time rate, delay rate by carrier

Run:
    python gold.py
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

# ── GOLD QUERIES (all use CTEs) ───────────────────────────────

GOLD_QUERIES = {

"gold_revenue_by_category": """
WITH order_items_with_product AS (
    -- Join order items to products to get category
    SELECT
        oi.item_id,
        oi.order_id,
        oi.quantity,
        oi.unit_price,
        oi.line_total,
        p.product_id,
        p.product_name,
        p.category,
        p.cost_price
    FROM silver_order_items oi
    JOIN silver_products p ON oi.product_id = p.product_id
),
completed_orders AS (
    -- Only count completed or shipped orders
    SELECT order_id
    FROM silver_orders
    WHERE status IN ('completed', 'shipped')
),
revenue_base AS (
    SELECT
        oip.category,
        oip.product_id,
        oip.product_name,
        oip.unit_price,
        oip.cost_price,
        oip.quantity,
        oip.line_total,
        (oip.line_total - (oip.cost_price * oip.quantity)) AS gross_profit
    FROM order_items_with_product oip
    JOIN completed_orders co ON oip.order_id = co.order_id
)
SELECT
    category,
    COUNT(DISTINCT product_id)            AS unique_products,
    SUM(quantity)                         AS total_units_sold,
    ROUND(SUM(line_total)::numeric, 2)    AS total_revenue,
    ROUND(AVG(unit_price)::numeric, 2)    AS avg_unit_price,
    ROUND(SUM(gross_profit)::numeric, 2)  AS total_gross_profit,
    ROUND(
        (SUM(gross_profit) / NULLIF(SUM(line_total), 0) * 100)::numeric, 1
    )                                     AS gross_margin_pct
FROM revenue_base
GROUP BY category
ORDER BY total_revenue DESC
""",

"gold_monthly_order_summary": """
WITH orders_with_month AS (
    -- Extract year and month from order date
    SELECT
        order_id,
        customer_id,
        order_date,
        status,
        channel,
        order_total,
        discount_pct,
        DATE_TRUNC('month', order_date)         AS order_month,
        TO_CHAR(order_date, 'YYYY-MM')          AS month_label
    FROM silver_orders
    WHERE order_date IS NOT NULL
      AND order_total IS NOT NULL
),
monthly_base AS (
    SELECT
        month_label,
        order_month,
        COUNT(order_id)                              AS total_orders,
        COUNT(DISTINCT customer_id)                  AS unique_customers,
        SUM(order_total)                             AS total_revenue,
        AVG(order_total)                             AS avg_order_value,
        SUM(CASE WHEN status = 'completed'  THEN 1 ELSE 0 END) AS completed_orders,
        SUM(CASE WHEN status = 'cancelled'  THEN 1 ELSE 0 END) AS cancelled_orders,
        SUM(CASE WHEN channel = 'web'       THEN 1 ELSE 0 END) AS web_orders,
        SUM(CASE WHEN channel = 'mobile'    THEN 1 ELSE 0 END) AS mobile_orders,
        SUM(CASE WHEN channel = 'in-store'  THEN 1 ELSE 0 END) AS instore_orders
    FROM orders_with_month
    GROUP BY month_label, order_month
)
SELECT
    month_label,
    total_orders,
    unique_customers,
    ROUND(total_revenue::numeric, 2)                AS total_revenue,
    ROUND(avg_order_value::numeric, 2)              AS avg_order_value,
    completed_orders,
    cancelled_orders,
    ROUND((cancelled_orders::numeric /
           NULLIF(total_orders, 0) * 100), 1)       AS cancellation_rate_pct,
    web_orders,
    mobile_orders,
    instore_orders
FROM monthly_base
ORDER BY order_month
""",

"gold_return_rate_by_product": """
WITH order_item_detail AS (
    -- Base: every order item with product info
    SELECT
        oi.item_id,
        oi.order_id,
        oi.product_id,
        oi.quantity,
        oi.line_total,
        p.product_name,
        p.category,
        p.unit_price
    FROM silver_order_items oi
    JOIN silver_products p ON oi.product_id = p.product_id
),
returned_orders AS (
    -- Orders that have an approved return
    SELECT DISTINCT order_id
    FROM silver_returns
    WHERE status = 'approved'
),
product_sales AS (
    SELECT
        product_id,
        product_name,
        category,
        unit_price,
        COUNT(item_id)              AS times_sold,
        SUM(quantity)               AS total_units_sold,
        SUM(line_total)             AS total_revenue
    FROM order_item_detail
    GROUP BY product_id, product_name, category, unit_price
),
product_returns AS (
    SELECT
        oid.product_id,
        COUNT(oid.item_id)          AS times_returned,
        SUM(r.refund_amount)        AS total_refunded
    FROM order_item_detail oid
    JOIN returned_orders ro ON oid.order_id = ro.order_id
    JOIN silver_returns r   ON oid.order_id = r.order_id
    GROUP BY oid.product_id
)
SELECT
    ps.product_id,
    ps.product_name,
    ps.category,
    ps.unit_price,
    ps.times_sold,
    ps.total_units_sold,
    ROUND(ps.total_revenue::numeric, 2)             AS total_revenue,
    COALESCE(pr.times_returned, 0)                  AS times_returned,
    ROUND(COALESCE(pr.total_refunded, 0)::numeric, 2) AS total_refunded,
    ROUND(
        (COALESCE(pr.times_returned, 0)::numeric /
         NULLIF(ps.times_sold, 0) * 100), 1
    )                                               AS return_rate_pct
FROM product_sales ps
LEFT JOIN product_returns pr ON ps.product_id = pr.product_id
ORDER BY return_rate_pct DESC NULLS LAST, total_revenue DESC
""",

"gold_customer_lifetime_value": """
WITH customer_orders AS (
    SELECT
        o.customer_id,
        COUNT(o.order_id)               AS total_orders,
        SUM(o.order_total)              AS total_spent,
        AVG(o.order_total)              AS avg_order_value,
        MIN(o.order_date)               AS first_order_date,
        MAX(o.order_date)               AS last_order_date,
        SUM(CASE WHEN o.status = 'completed' THEN 1 ELSE 0 END) AS completed_orders
    FROM silver_orders o
    WHERE o.customer_id IS NOT NULL
      AND o.order_total  IS NOT NULL
    GROUP BY o.customer_id
),
customer_returns AS (
    SELECT
        o.customer_id,
        COUNT(r.return_id)              AS total_returns,
        SUM(r.refund_amount)            AS total_refunded
    FROM silver_returns r
    JOIN silver_orders o ON r.order_id = o.order_id
    WHERE o.customer_id IS NOT NULL
    GROUP BY o.customer_id
)
SELECT
    c.customer_id,
    c.first_name,
    c.last_name,
    c.segment,
    c.state,
    COALESCE(co.total_orders, 0)                     AS total_orders,
    ROUND(COALESCE(co.total_spent, 0)::numeric, 2)   AS total_spent,
    ROUND(COALESCE(co.avg_order_value, 0)::numeric, 2) AS avg_order_value,
    co.first_order_date,
    co.last_order_date,
    COALESCE(cr.total_returns, 0)                    AS total_returns,
    ROUND(COALESCE(cr.total_refunded, 0)::numeric, 2) AS total_refunded,
    CASE
        WHEN COALESCE(co.total_spent, 0) >= 1000 THEN 'High Value'
        WHEN COALESCE(co.total_spent, 0) >= 400  THEN 'Mid Value'
        ELSE 'Low Value'
    END                                              AS value_tier
FROM silver_customers c
LEFT JOIN customer_orders  co ON c.customer_id = co.customer_id
LEFT JOIN customer_returns cr ON c.customer_id = cr.customer_id
ORDER BY total_spent DESC
""",

"gold_fulfillment_summary": """
WITH shipping_with_days AS (
    SELECT
        shipment_id,
        order_id,
        carrier,
        warehouse,
        ship_date,
        actual_delivery,
        estimated_delivery,
        status,
        _invalid_ship_date,
        CASE
            WHEN actual_delivery IS NOT NULL AND ship_date IS NOT NULL
            THEN (actual_delivery - ship_date)
            ELSE NULL
        END AS days_to_deliver,
        CASE
            WHEN actual_delivery IS NOT NULL AND estimated_delivery IS NOT NULL
            THEN actual_delivery <= estimated_delivery
            ELSE NULL
        END AS delivered_on_time
    FROM silver_shipping_events
    WHERE _invalid_ship_date = FALSE
)
SELECT
    carrier,
    COUNT(shipment_id)                              AS total_shipments,
    SUM(CASE WHEN status = 'delivered'   THEN 1 ELSE 0 END) AS delivered,
    SUM(CASE WHEN status = 'delayed'     THEN 1 ELSE 0 END) AS delayed,
    SUM(CASE WHEN status = 'lost'        THEN 1 ELSE 0 END) AS lost,
    ROUND(AVG(days_to_deliver)::numeric, 1)         AS avg_days_to_deliver,
    ROUND(
        (SUM(CASE WHEN delivered_on_time THEN 1 ELSE 0 END)::numeric /
         NULLIF(COUNT(CASE WHEN delivered_on_time IS NOT NULL THEN 1 END), 0) * 100), 1
    )                                               AS on_time_rate_pct,
    ROUND(
        (SUM(CASE WHEN status = 'delayed' THEN 1 ELSE 0 END)::numeric /
         NULLIF(COUNT(shipment_id), 0) * 100), 1
    )                                               AS delay_rate_pct
FROM shipping_with_days
GROUP BY carrier
ORDER BY avg_days_to_deliver
""",
}


def main():
    log("=" * 55)
    log("  OrderFlow — Gold Layer")
    log(f"  Timestamp: {datetime.now()}")
    log("=" * 55)

    engine = create_engine(CONNECTION)
    ts     = datetime.now()

    for table_name, query in GOLD_QUERIES.items():
        log(f"\n  Building: {table_name}")
        start = time.time()
        try:
            df = pd.read_sql(query, engine)
            df["_gold_timestamp"] = ts
            df.to_sql(
                name      = table_name,
                con       = engine,
                if_exists = "replace",
                index     = False,
            )
            log(f"  ✓ {table_name:<38} {len(df):>5} rows  ({round(time.time()-start,2)}s)")
        except Exception as e:
            log(f"  ✗ {table_name} FAILED — {e}")

    log("\n" + "=" * 55)
    log("  Gold layer complete.")
    log("=" * 55)

    log("\n  Sample output — gold_revenue_by_category:")
    log("-" * 55)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT category, total_revenue, total_units_sold, gross_margin_pct "
            "FROM gold_revenue_by_category ORDER BY total_revenue DESC LIMIT 5"
        )).fetchall()
        log(f"  {'Category':<20} {'Revenue':>10} {'Units':>8} {'Margin%':>8}")
        log(f"  {'-'*20} {'-'*10} {'-'*8} {'-'*8}")
        for row in rows:
            log(f"  {str(row[0]):<20} {str(row[1]):>10} {str(row[2]):>8} {str(row[3]):>8}")

    log("\n  Sample output — gold_monthly_order_summary:")
    log("-" * 55)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT month_label, total_orders, total_revenue, avg_order_value "
            "FROM gold_monthly_order_summary ORDER BY month_label DESC LIMIT 5"
        )).fetchall()
        log(f"  {'Month':<12} {'Orders':>8} {'Revenue':>12} {'AOV':>10}")
        log(f"  {'-'*12} {'-'*8} {'-'*12} {'-'*10}")
        for row in rows:
            log(f"  {str(row[0]):<12} {str(row[1]):>8} {str(row[2]):>12} {str(row[3]):>10}")
    log("")

if __name__ == "__main__":
    main()
