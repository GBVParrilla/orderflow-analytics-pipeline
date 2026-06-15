# OrderFlow Analytics Pipeline

An end-to-end e-commerce analytics pipeline built with Python, SQL, PostgreSQL, and Streamlit. Implements medallion architecture (Bronze → Silver → Gold) with automated data quality checks and a live business dashboard.

Built as a portfolio project demonstrating real-world data engineering patterns — medallion architecture, data quality validation, SQL transformations with CTEs, and business reporting.

---

## Business Impact

This pipeline answers the questions a real e-commerce data team cares about:

- **Which product categories generate the most revenue and margin?**
- **Which customers are highest lifetime value and deserve retention focus?**
- **Which products have the highest return rates — and why does that hurt margin?**
- **Which carriers are slowest? Where are fulfillment bottlenecks?**
- **How clean is our data — and what issues exist in the raw feed?**

Without this pipeline, answering these questions requires manual spreadsheet work. With it, the dashboard updates automatically every time the pipeline runs.

---

## Architecture

Raw CSVs (data/raw/)
     |
     v
[ BRONZE ]  bronze.py
  Raw data + ingest timestamp + source metadata
     |
     v
[ SILVER ]  silver.py
  Clean · Standardize · Flag bad records
     |
     |-----------> [ QUALITY CHECKS ]  quality_checks.py
     |               10 DQ checks
     |               -> dq_quality_log (PostgreSQL)
     |               -> quality_report.csv
     v
[ GOLD ]  gold.py
  CTE-based SQL transforms
  -> 5 reporting tables
     |
     v
[ DASHBOARD ]  dashboard.py
  Streamlit + Plotly
  Live business metrics

---

## Gold Tables (Reporting Layer)

| Table                          | Description                                                        |
|--------------------------------|--------------------------------------------------------------------|
| `gold_revenue_by_category`     | Revenue, units sold, gross margin % by product category            |
| `gold_monthly_order_summary`   | Monthly orders, revenue, AOV, channel breakdown, cancellation rate |
| `gold_return_rate_by_product`  | Return rate per product, total refunds, revenue impact             |
| `gold_customer_lifetime_value` | Total spent, order count, value tier (High/Mid/Low) per customer   |
| `gold_fulfillment_summary`     | Avg delivery days, on-time rate, delay rate per carrier            |

---

## Data Quality Checks

10 named checks run automatically against Silver tables:

| Check  | Category              | What It Catches                    |
|--------|-----------------------|------------------------------------|
| DQ-001 | Uniqueness            | Duplicate order IDs                |
| DQ-002 | Completeness          | Orders missing customer_id         |
| DQ-003 | Referential Integrity | Returns with no matching order     |
| DQ-004 | Completeness          | Orders with no line items          |
| DQ-005 | Validity              | Ship date after delivery date      |
| DQ-006 | Referential Integrity | Order items with no matching order |
| DQ-007 | Uniqueness            | Duplicate customer emails          |
| DQ-008 | Validity              | Products with invalid pricing      |
| DQ-009 | Completeness          | Orders with null total             |
| DQ-010 | Completeness          | Returns with no refund amount      |

Results are saved to `data/quality/quality_report.csv` and the `dq_quality_log` PostgreSQL table on every run.

---

## Dashboard Metrics

Built with Streamlit + Plotly. Reads directly from Gold tables.

- Total revenue, total orders, average order value, overall return rate, unique customers
- Revenue by category (bar chart with gross margin color scale)
- Monthly revenue trend with AOV overlay (dual-axis)
- Top 10 customers by lifetime value
- Return rate by product category
- Fulfillment speed and on-time rate by carrier
- Orders by channel (web / mobile / in-store)
- Data quality summary table (live from last pipeline run)

---

## Tech Stack

| Tool          | Purpose                                             |
|---------------|-----------------------------------------------------|
| Python 3.x    | Pipeline orchestration, data generation, cleaning   |
| pandas        | DataFrame operations, CSV handling, transformations |
| PostgreSQL 15 | Primary database — Bronze, Silver, Gold, DQ log     |
| SQLAlchemy    | Python → PostgreSQL connection                      |
| SQL + CTEs    | Gold layer transformations                          |
| Streamlit     | Business dashboard                                  |
| Plotly        | Interactive charts                                  |
| Faker         | Synthetic dataset generation                        |
| GitHub        | Version control                                     |

---

## Dataset

Fully synthetic data — no real customer or business data used.

| Table           | Rows   | Description                             |
|-----------------|--------|-----------------------------------------|
| customers       | 305    | Name, email, city, state, segment       |
| products        | 100    | Name, category, price, cost             |
| orders          | 503    | Date, status, channel, payment method   |
| order_items     | ~1,000 | Product, quantity, line total per order |
| returns         | 80     | Reason, refund amount, status           |
| shipping_events | 500    | Carrier, warehouse, delivery dates      |

Data quality issues intentionally injected to simulate real-world dirty data:
- Duplicate emails, duplicate order IDs, null customer IDs
- Orphan order items and returns (no matching parent record)
- Invalid shipping dates (ship after delivery)

---

## Project Structure

orderflow-analytics-pipeline/
│
├── bronze.py               # Bronze layer — raw ingest
├── silver.py               # Silver layer — clean & standardize
├── gold.py                 # Gold layer — CTE SQL transforms
├── quality_checks.py       # 10 data quality checks + CSV log
├── run_pipeline.py         # Runs all layers in order
├── dashboard.py            # Streamlit dashboard
├── export_gold_csv.py      # Export Gold tables to CSV (for Power BI)
├── generate_data.py        # Synthetic dataset generator
├── ingest.py               # Initial CSV → PostgreSQL loader
├── requirements.txt        # Python dependencies
│
├── data/
│   ├── raw/                # Source CSV files (Bronze input)
│   ├── gold/               # Exported Gold CSVs (Power BI input)
│   └── quality/            # Data quality reports
│       └── quality_report.csv
│
└── queries/
    └── practice_queries.sql  # SQL practice queries


---

## How to Run

**1. Clone the repo**
```bash
git clone https://github.com/GBVParrilla/orderflow-analytics-pipeline.git
cd orderflow-analytics-pipeline
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Start PostgreSQL and create the database**
```bash
pg_ctl -D /opt/homebrew/var/postgresql@15 start
createdb orderflow
```

**4. Generate fake dataset**
```bash
python generate_data.py
```

**5. Run the full pipeline**
```bash
python run_pipeline.py
```

**6. Launch the dashboard**
```bash
streamlit run dashboard.py
```
Open your browser to `http://localhost:8501`

---

## Author

**George Bernard Parrilla**
CS Student @ George Mason University · Expected May 2028
Focusing on Cloud Computing, Data Engineering, and Solutions Architecture
