# pages/04_Safety_Analytics.py
import os
from datetime import datetime, timezone, timedelta

import boto3
import pandas as pd
import streamlit as st
import altair as alt
from decimal import Decimal
from botocore.exceptions import ClientError

# -----------------------
# Page config
# -----------------------
st.set_page_config(
    page_title="Safety Analytics",
    page_icon="📊",
    layout="wide",
)

# -----------------------
# Global PPE styling (soft orange theme)
# -----------------------
st.markdown("""
<style>
  /* Soft PPE orange gradient background */
  .stApp {
    background: linear-gradient(180deg, #fff7ed 0%, #fff 28%);
  }
  footer { visibility: hidden; }

  /* Headings & subheaders subtle tweak */
  h1, h2, h3, h4 { color: #0f172a; }

  /* KPI metric labels -> safety orange */
  div[data-testid="stMetric"] div[data-testid="stMetricLabel"] {
      color: #ea580c !important; /* orange-600 */
  }

  /* Sidebar controls: borders & focus rings in orange */
  section[data-testid="stSidebar"] .stMultiSelect,
  section[data-testid="stSidebar"] .stSelectbox,
  section[data-testid="stSidebar"] .stSlider,
  section[data-testid="stSidebar"] .stTextInput {
    --ring-color: #fb923c22;
  }
  section[data-testid="stSidebar"] .stTextInput input,
  section[data-testid="stSidebar"] .stMultiSelect > div > div,
  section[data-testid="stSidebar"] .stSelectbox > div > div {
    border: 1px solid #fed7aa !important;   /* orange-200 */
    box-shadow: 0 0 0 0px #fff inset !important;
  }
  section[data-testid="stSidebar"] .stTextInput input:focus,
  section[data-testid="stSidebar"] .stMultiSelect:focus-within > div > div,
  section[data-testid="stSidebar"] .stSelectbox:focus-within > div > div {
    border: 1px solid #fb923c !important;   /* orange-400 */
    box-shadow: 0 0 0 3px #fed7aa55 !important;
  }

  /* Tables: header bar with orange hint */
  .orange-table thead tr th {
    background: #fff7ed !important;        /* orange-50 */
    border-bottom: 1px solid #fed7aa !important;
  }

  /* Section dividers a bit softer */
  hr { border: none; border-top: 1px solid #e2e8f0; }

</style>
""", unsafe_allow_html=True)

st.title("Safety Analytics")
st.caption("Operational insights across employees and PPE violations (DynamoDB: employee_master & violation_master).")

# -----------------------
# Altair PPE theme (orange accents)
# -----------------------
def ppe_theme():
    return {
        "config": {
            "view": {"continuousWidth": 400, "continuousHeight": 300, "strokeWidth": 0},
            "axis": {
                "labelColor": "#0f172a",
                "titleColor": "#0f172a",
                "gridColor": "#e2e8f0",
                "domain": False
            },
            "legend": {"labelColor": "#0f172a", "titleColor": "#0f172a"},
            "range": {
                # Bars/lines default palette (safety orange forward)
                "category": [
                    "#ea580c", "#fb923c", "#f97316", "#f59e0b",
                    "#d97706", "#fdba74", "#fed7aa", "#78350f"
                ]
            },
            "bar": {"cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4},
            "area": {"line": True, "point": False},
        }
    }

alt.themes.register("ppe", ppe_theme)
alt.themes.enable("ppe")

def _theme_chart(chart):
    return chart.properties(width="container", height=320).configure_view(strokeWidth=0)

# -----------------------
# AWS config (same style as other pages)
# -----------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

EMPLOYEE_TABLE   = "employee_master"
VIOLATION_TABLE  = "violation_master"

# -----------------------
# Helpers
# -----------------------
def ddb_resource():
    return boto3.resource(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
    )

def ddb_table(name: str):
    return ddb_resource().Table(name)

def _to_native(v):
    if isinstance(v, Decimal):
        return int(v) if v % 1 == 0 else float(v)
    return v

def _scan_table_all(tbl_name: str) -> list[dict]:
    """Full table scan with pagination. Fine for small/medium tables."""
    try:
        tbl = ddb_table(tbl_name)
        items, start_key = [], None
        while True:
            if start_key:
                resp = tbl.scan(ExclusiveStartKey=start_key)
            else:
                resp = tbl.scan()
            items.extend(resp.get("Items", []))
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
        return items
    except ClientError as e:
        st.error(f"Failed to scan {tbl_name}: {e.response.get('Error',{}).get('Message','')}")
        return []

# -----------------------
# Data loading
# -----------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    # Employees
    emp_items = _scan_table_all(EMPLOYEE_TABLE)
    for it in emp_items:
        it["EmployeeID"] = str(it.get("EmployeeID", ""))
        it["name"]       = it.get("name")
        it["department"] = it.get("department")
        it["site"]       = it.get("site")
        it["line"]       = it.get("line")
        it["job_title"]  = it.get("job_title")
        it["status"]     = it.get("status", "Active")
        it["created_at"] = it.get("created_at")
    emp_df = pd.DataFrame(emp_items)

    # Violations
    vio_items = _scan_table_all(VIOLATION_TABLE)
    for it in vio_items:
        it["EmployeeID"]     = str(it.get("EmployeeID", ""))
        it["violations"]     = int(_to_native(it.get("violations", 0)))
        it["last_missing"]   = it.get("last_missing", "")
        it["last_image_key"] = it.get("last_image_key", "")
        it["last_updated"]   = it.get("last_updated", "")
    vio_df = pd.DataFrame(vio_items)

    # Join (left join employees with violations)
    if not emp_df.empty and not vio_df.empty:
        df = emp_df.merge(vio_df, on="EmployeeID", how="left")
    else:
        df = emp_df.copy()
        if not df.empty and "violations" not in df.columns:
            df["violations"] = 0
        if "last_updated" not in df.columns:
            df["last_updated"] = None
        if "last_missing" not in df.columns:
            df["last_missing"] = None

    # Normalize time
    if "last_updated" in df.columns and not df["last_updated"].empty:
        def _to_dt(x):
            if pd.isna(x) or x in ("", None):
                return pd.NaT
            try:
                return pd.to_datetime(str(x).replace("Z", "+00:00"))
            except Exception:
                return pd.NaT
        df["last_updated_dt"] = df["last_updated"].apply(_to_dt)

    # Convenience: choose "line" if present; else fallback to site
    df["line_or_site"] = df["line"].fillna(df.get("site"))

    # Safety defaults
    if "violations" not in df.columns:
        df["violations"] = 0
    df["violations"] = pd.to_numeric(df["violations"], errors="coerce").fillna(0).astype(int)

    return emp_df, vio_df, df

emp_df, vio_df, df = load_data()

# Graceful empty-state
if emp_df.empty:
    st.info("No employees found in `employee_master` yet.")
if vio_df.empty:
    st.info("No records in `violation_master` yet.")

# -----------------------
# Filters (sidebar)
# -----------------------
with st.sidebar:
    st.header("Filters")
    dept_options = sorted([d for d in df.get("department", pd.Series(dtype=str)).dropna().unique()])
    site_options = sorted([s for s in df.get("site", pd.Series(dtype=str)).dropna().unique()])
    job_options  = sorted([j for j in df.get("job_title", pd.Series(dtype=str)).dropna().unique()])

    selected_depts = st.multiselect("Department", dept_options, default=dept_options[:5] if len(dept_options) > 5 else dept_options)
    selected_sites = st.multiselect("Site / Plant", site_options, default=site_options)
    selected_jobs  = st.multiselect("Job Title / Position", job_options, default=job_options)

    days_back = st.slider("Lookback (days) for time chart", min_value=7, max_value=90, value=30, step=1)

view = df.copy()
if selected_depts:
    view = view[view["department"].isin(selected_depts)]
if selected_sites:
    view = view[view["site"].isin(selected_sites)]
if selected_jobs:
    view = view[view["job_title"].isin(selected_jobs)]

# -----------------------
# KPIs
# -----------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Employees", int(emp_df.shape[0]))
k2.metric("Employees (filtered)", int(view.shape[0]))
k3.metric("Total violations", int(view["violations"].sum()))
k4.metric("Median violations / employee", float(view["violations"].median()) if not view.empty else 0)

st.divider()

# -----------------------
# Charts
# -----------------------
# 1) Violations by Department
st.subheader("Violations by Department")
if not view.empty and "department" in view.columns:
    dept = (
        view.groupby("department", dropna=False)["violations"]
        .sum()
        .reset_index()
        .sort_values("violations", ascending=False)
    )
    c1 = alt.Chart(dept).mark_bar().encode(
        x=alt.X("violations:Q", title="Violations"),
        y=alt.Y("department:N", sort="-x", title="Department"),
        tooltip=["department", "violations"]
    )
    st.altair_chart(_theme_chart(c1), use_container_width=True)
else:
    st.info("No department data available.")

st.divider()

# 2) Violations by Site / Plant (or Line if you store it)
st.subheader("Violations by Site / Plant")
if not view.empty and "site" in view.columns:
    site = (
        view.groupby("site", dropna=False)["violations"]
        .sum()
        .reset_index()
        .sort_values("violations", ascending=False)
    )
    c2 = alt.Chart(site).mark_bar().encode(
        x=alt.X("violations:Q", title="Violations"),
        y=alt.Y("site:N", sort="-x", title="Site / Plant"),
        tooltip=["site", "violations"]
    )
    st.altair_chart(_theme_chart(c2), use_container_width=True)
else:
    st.info("No site/plant data available.")

st.divider()

# 3) Violations by Job Title / Position
st.subheader("Violations by Job Title / Position")
if not view.empty and "job_title" in view.columns:
    job = (
        view.groupby("job_title", dropna=False)["violations"]
        .sum()
        .reset_index()
        .sort_values("violations", ascending=False)
        .head(15)
    )
    c3 = alt.Chart(job).mark_bar().encode(
        x=alt.X("violations:Q", title="Violations"),
        y=alt.Y("job_title:N", sort="-x", title="Job Title / Position"),
        tooltip=["job_title", "violations"]
    )
    st.altair_chart(_theme_chart(c3), use_container_width=True)
else:
    st.info("No job title data available.")

st.divider()

# 4) Violations over Time (last_updated)
st.subheader(f"Violations over Time (last {days_back} days)")
if not view.empty and "last_updated_dt" in view.columns:
    since = pd.Timestamp.utcnow() - pd.Timedelta(days=days_back)
    time_view = view.dropna(subset=["last_updated_dt"])
    time_view = time_view[time_view["last_updated_dt"] >= since]
    if time_view.empty:
        st.info("No violation updates in the selected window.")
    else:
        time_series = (
            time_view
            .assign(date=time_view["last_updated_dt"].dt.date)
            .groupby("date", as_index=False)["violations"]
            .sum()
        )
        c4 = alt.Chart(time_series).mark_area(opacity=0.85).encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("violations:Q", title="Violations (sum)"),
            tooltip=[alt.Tooltip("date:T", title="Date"), alt.Tooltip("violations:Q", title="Violations")]
        )
        st.altair_chart(_theme_chart(c4), use_container_width=True)
else:
    st.info("No timestamp data available for time chart.")

st.divider()

# 5) Top Offenders (employees with most violations)
st.subheader("Top Employees by Violation Count")
if not view.empty:
    top = (
        view[["EmployeeID", "name", "department", "site", "violations"]]
        .sort_values("violations", ascending=False)
        .head(10)
    )
    c5 = alt.Chart(top).mark_bar().encode(
        x=alt.X("violations:Q", title="Violations"),
        y=alt.Y("EmployeeID:N", sort="-x", title="EmployeeID"),
        color=alt.Color("department:N", title="Department"),
        tooltip=["EmployeeID", "name", "department", "site", "violations"]
    )
    st.altair_chart(_theme_chart(c5), use_container_width=True)

    # Table with orange header hint
    st.markdown('<div class="orange-table">', unsafe_allow_html=True)
    st.dataframe(top.reset_index(drop=True), use_container_width=True, hide_index=True)
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("No employee data available for ranking.")

st.divider()

# 6) Distribution (Histogram) of Violations across Employees
st.subheader("Distribution of Violations per Employee")
if not view.empty:
    hist = alt.Chart(view).mark_bar().encode(
        x=alt.X("violations:Q", bin=alt.Bin(maxbins=20), title="Violations"),
        y=alt.Y("count():Q", title="Employees"),
        tooltip=[alt.Tooltip("count():Q", title="Employees")]
    )
    st.altair_chart(_theme_chart(hist), use_container_width=True)

# -----------------------
# Notes / Guidance
# -----------------------
st.caption(
    "Tip: To tighten these charts for very large datasets, consider adding a DynamoDB GSI on `last_updated` "
    "or pre-aggregated materialized views. These visuals honor the filters in the sidebar."
)
