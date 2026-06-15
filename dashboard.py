"""
dashboard.py
OrderFlow Analytics Pipeline — Streamlit Dashboard

Reads from Gold tables in PostgreSQL and displays business metrics.

Run:
    pip install streamlit plotly
    streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine

# ── CONFIG ────────────────────────────────────────────────────
DB_USER    = "georgebvp"
DB_HOST    = "127.0.0.1"
DB_PORT    = "5432"
DB_NAME    = "orderflow"
CONNECTION = f"postgresql+psycopg2://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

st.set_page_config(
    page_title = "OrderFlow Analytics",
    page_icon  = "📦",
    layout     = "wide",
)

# ── DATA LOADING ──────────────────────────────────────────────
@st.cache_data
def load(query):
    engine = create_engine(CONNECTION)
    return pd.read_sql(query, engine)

# ── HEADER ────────────────────────────────────────────────────
st.title("📦 OrderFlow Analytics Dashboard")
st.caption("End-to-end e-commerce analytics pipeline · Bronze → Silver → Gold · Built by George Parrilla")
st.divider()

# ── LOAD ALL GOLD DATA ────────────────────────────────────────
revenue_df     = load("SELECT * FROM gold_revenue_by_category")
monthly_df     = load("SELECT * FROM gold_monthly_order_summary ORDER BY month_label")
returns_df     = load("SELECT * FROM gold_return_rate_by_product")
ltv_df         = load("SELECT * FROM gold_customer_lifetime_value")
fulfillment_df = load("SELECT * FROM gold_fulfillment_summary")
dq_df          = load("SELECT * FROM dq_quality_log ORDER BY run_time DESC")

# ── KPI ROW ───────────────────────────────────────────────────
st.subheader("Key Metrics")
k1, k2, k3, k4, k5 = st.columns(5)

total_revenue  = monthly_df["total_revenue"].sum()
total_orders   = monthly_df["total_orders"].sum()
avg_aov        = monthly_df["avg_order_value"].mean()
total_returned = returns_df["times_returned"].sum()
total_sold     = returns_df["times_sold"].sum()
overall_return = round(total_returned / total_sold * 100, 1) if total_sold > 0 else 0

k1.metric("Total Revenue",       f"${total_revenue:,.0f}")
k2.metric("Total Orders",        f"{total_orders:,}")
k3.metric("Avg Order Value",     f"${avg_aov:,.2f}")
k4.metric("Overall Return Rate", f"{overall_return}%")
k5.metric("Unique Customers",    f"{ltv_df['customer_id'].nunique():,}")

st.divider()

# ── ROW 1: Revenue + Monthly Trend ───────────────────────────
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Revenue by Category")
    fig = px.bar(
        revenue_df.sort_values("total_revenue"),
        x          = "total_revenue",
        y          = "category",
        orientation= "h",
        color      = "gross_margin_pct",
        color_continuous_scale = "Blues",
        labels     = {"total_revenue": "Revenue ($)", "category": "", "gross_margin_pct": "Margin %"},
        text       = "total_revenue",
    )
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="inside", insidetextanchor="end")
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="inside", insidetextanchor="end")
    fig.update_layout(height=380, margin=dict(l=0, r=80, t=10, b=0), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Monthly Revenue Trend")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x    = monthly_df["month_label"],
        y    = monthly_df["total_revenue"],
        name = "Revenue",
        marker_color = "#2563EB",
        opacity = 0.85,
    ))
    fig.add_trace(go.Scatter(
        x    = monthly_df["month_label"],
        y    = monthly_df["avg_order_value"],
        name = "Avg Order Value",
        yaxis= "y2",
        mode = "lines+markers",
        line = dict(color="#F59E0B", width=2),
        marker = dict(size=5),
    ))
    fig.update_layout(
        height  = 380,
        yaxis   = dict(title="Revenue ($)"),
        yaxis2  = dict(title="AOV ($)", overlaying="y", side="right"),
        legend  = dict(orientation="h", y=1.08),
        margin  = dict(l=0, r=0, t=10, b=0),
        xaxis   = dict(tickangle=-45),
    )
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── ROW 2: Top Customers + Return Rate ───────────────────────
col3, col4 = st.columns([1, 1])

with col3:
    st.subheader("Top 10 Customers by Lifetime Value")
    top10 = ltv_df.nlargest(10, "total_spent")[
        ["first_name", "last_name", "segment", "total_orders", "total_spent", "value_tier"]
    ].copy()
    top10["customer"] = top10["first_name"] + " " + top10["last_name"]
    fig = px.bar(
        top10.sort_values("total_spent"),
        x          = "total_spent",
        y          = "customer",
        orientation= "h",
        color      = "value_tier",
        color_discrete_map = {
            "High Value": "#1D4ED8",
            "Mid Value":  "#60A5FA",
            "Low Value":  "#BFDBFE",
        },
        labels = {"total_spent": "Total Spent ($)", "customer": ""},
        text   = "total_spent",
    )
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="inside", insidetextanchor="end")
    fig.update_traces(texttemplate="$%{text:,.0f}", textposition="inside", insidetextanchor="end")
    fig.update_layout(height=380, margin=dict(l=0, r=80, t=10, b=0), showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

with col4:
    st.subheader("Return Rate by Product Category")
    returns_by_cat = (
        returns_df.groupby(
            returns_df["category"]
        ).agg(
            times_returned = ("times_returned", "sum"),
            times_sold     = ("times_sold",     "sum"),
        ).reset_index()
    )
    returns_by_cat["return_rate_pct"] = (
        returns_by_cat["times_returned"] / returns_by_cat["times_sold"] * 100
    ).round(1)
    returns_by_cat = returns_by_cat.sort_values("return_rate_pct", ascending=False)

    fig = px.bar(
        returns_by_cat,
        x     = "category",
        y     = "return_rate_pct",
        color = "return_rate_pct",
        color_continuous_scale = "Reds",
        labels = {"return_rate_pct": "Return Rate (%)", "category": ""},
        text  = "return_rate_pct",
    )
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── ROW 3: Fulfillment + Order Channels ───────────────────────
col5, col6 = st.columns([1, 1])

with col5:
    st.subheader("Fulfillment Speed by Carrier")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name = "Avg Days to Deliver",
        x    = fulfillment_df["carrier"],
        y    = fulfillment_df["avg_days_to_deliver"],
        marker_color = "#2563EB",
        text = fulfillment_df["avg_days_to_deliver"],
        texttemplate = "%{text}d",
        textposition = "outside",
    ))
    fig.add_trace(go.Scatter(
        name = "On-Time Rate %",
        x    = fulfillment_df["carrier"],
        y    = fulfillment_df["on_time_rate_pct"],
        mode = "lines+markers",
        yaxis= "y2",
        line = dict(color="#10B981", width=2),
        marker = dict(size=8),
    ))
    fig.update_layout(
        height  = 340,
        yaxis   = dict(title="Avg Days"),
        yaxis2  = dict(title="On-Time %", overlaying="y", side="right", range=[0, 110]),
        legend  = dict(orientation="h", y=1.08),
        margin  = dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

with col6:
    st.subheader("Orders by Channel")
    channel_data = monthly_df[["web_orders", "mobile_orders", "instore_orders"]].sum()
    fig = px.pie(
        values = channel_data.values,
        names  = ["Web", "Mobile", "In-Store"],
        color_discrete_sequence = ["#2563EB", "#60A5FA", "#93C5FD"],
        hole   = 0.45,
    )
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=30), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── ROW 4: Data Quality Summary ───────────────────────────────
st.subheader("🔍 Data Quality Summary")

latest_run = dq_df["run_time"].max()
latest_dq  = dq_df[dq_df["run_time"] == latest_run]

dq1, dq2, dq3, dq4 = st.columns(4)
passed = (latest_dq["status"] == "PASS").sum()
failed = (latest_dq["status"] == "FAIL").sum()
total_issues = latest_dq["issue_count"].clip(lower=0).sum()

dq1.metric("Checks Run",    len(latest_dq))
dq2.metric("Passed ✅",     passed)
dq3.metric("Failed ⚠️",     failed)
dq4.metric("Total Issues",  int(total_issues))

st.dataframe(
    latest_dq[["check_id", "check_name", "category", "status", "issue_count"]].rename(columns={
        "check_id":    "ID",
        "check_name":  "Check",
        "category":    "Category",
        "status":      "Status",
        "issue_count": "Issues Found",
    }),
    use_container_width = True,
    hide_index          = True,
)

st.caption(f"Last pipeline run: {latest_run}")

st.divider()

# ── FOOTER ────────────────────────────────────────────────────
st.caption(
    "OrderFlow Analytics Pipeline · Built with Python, PostgreSQL, SQLAlchemy, and Streamlit · "
    "George Bernard Parrilla · CS @ George Mason University"
)
