# pages/03_Violations.py
import streamlit as st
import pandas as pd

# --- Make sure /utils is importable from inside /pages on Streamlit Cloud ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- AWS / general imports
import importlib
import boto3
from datetime import datetime, timezone
from decimal import Decimal
from botocore.exceptions import ClientError

# ---------- Robust import of utils.data (kept for compatibility) ----------
_missing = []
try:
    data_mod = importlib.import_module("utils.data")
except Exception as e:
    st.set_page_config(page_title="Violations", page_icon="⚠️", layout="wide")
    st.error(
        "Couldn't import `utils.data`. Make sure the repo has a `utils/` folder "
        "with `__init__.py` and `data.py` in it. Error: {}".format(e)
    )
    st.stop()

def _require(name, *aliases):
    for n in (name, *aliases):
        if hasattr(data_mod, n):
            return getattr(data_mod, n)
    _missing.append(name if not aliases else f"{name} (aliases tried: {', '.join(aliases)})")
    return None

# Kept so nothing else breaks if referenced elsewhere
load_employees_from_dynamodb = _require("load_employees_from_dynamodb", "load_employees", "get_employees")
update_employee_violations   = _require("update_employee_violations", "update_employee", "set_employee_violations")
upsert_employee              = _require("upsert_employee", "put_employee", "create_or_update_employee")

# ---------- Page UI ----------
st.set_page_config(page_title="Violations", page_icon="⚠️", layout="wide")
st.title("⚠Violations")
st.caption("View and edit aggregated PPE violations (DynamoDB: violation_master). Uploads to S3 (uploads/) will update this table via Lambda.")

# ---------- AWS config ----------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

EMPLOYEE_TABLE  = "employee_master"
VIOLATION_TABLE = "violation_master"

# ---------- AWS helpers ----------
def ddb_resource():
    return boto3.resource(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
    )

def ddb_table(name:str):
    return ddb_resource().Table(name)

def _to_native(v):
    if isinstance(v, Decimal):
        return int(v) if v % 1 == 0 else float(v)
    return v

# ---------- Data loaders: scan violation_master and join employee_master ----------
def _scan_table_all(tbl_name: str) -> list[dict]:
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

def _load_violation_df() -> pd.DataFrame:
    vio_items = _scan_table_all(VIOLATION_TABLE)
    if not vio_items:
        return pd.DataFrame(columns=[
            "EmployeeID","violations","last_missing","last_image_key","last_updated",
            "name","department","site"
        ])

    for it in vio_items:
        it["EmployeeID"]     = str(it.get("EmployeeID",""))
        it["violations"]     = int(_to_native(it.get("violations", 0)))
        it["last_missing"]   = it.get("last_missing","")
        it["last_image_key"] = it.get("last_image_key","")
        it["last_updated"]   = str(it.get("last_updated",""))

    vio_df = pd.DataFrame(vio_items)

    emp_items = _scan_table_all(EMPLOYEE_TABLE)
    for it in emp_items:
        it["EmployeeID"] = str(it.get("EmployeeID",""))
        it["name"]       = it.get("name")
        it["department"] = it.get("department")
        it["site"]       = it.get("site")
    emp_df = pd.DataFrame(emp_items)[["EmployeeID","name","department","site"]] if emp_items else pd.DataFrame(columns=["EmployeeID","name","department","site"])

    merged = vio_df.merge(emp_df, on="EmployeeID", how="left")
    return merged

def _update_violation_count(emp_id: str, new_count: int):
    tbl = ddb_table(VIOLATION_TABLE)
    tbl.update_item(
        Key={"EmployeeID": emp_id},
        UpdateExpression="SET violations=:v, last_updated=:lu",
        ExpressionAttributeValues={
            ":v": int(new_count),
            ":lu": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
    )

# =========================
#   Aggregated view/edit
# =========================
@st.cache_data(ttl=30, show_spinner=False)
def _cached_violations_df():
    return _load_violation_df()

# ---------- Toolbar ----------
bar = st.container()
with bar:
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    query = c1.text_input("Search by EmployeeID or Name", placeholder="e.g., emp01 or Alvin")
    min_v = c2.number_input("Min violations", min_value=0, value=0, step=1)
    sort_desc = c3.toggle("Sort by violations (desc)", value=True)
    refresh = c4.button("↻ Refresh")

if refresh:
    st.cache_data.clear()
    st.rerun()

df = _cached_violations_df()

# ---------- Filter / sort ----------
view = df.copy()
if query:
    q = query.strip().lower()
    view = view[
        view["EmployeeID"].str.lower().str.contains(q, na=False) |
        view.get("name", pd.Series("", index=view.index)).astype(str).str.lower().str.contains(q, na=False)
    ]
view = view[view["violations"] >= min_v]

if sort_desc:
    view = view.sort_values(by="violations", ascending=False, kind="mergesort")
else:
    view = view.sort_values(by="EmployeeID", ascending=True, kind="mergesort")

view = view.reset_index(drop=True)

# ---------- KPIs ----------
left_kpi, right_kpi = st.columns(2)
left_kpi.metric("Employees with violations (view)", len(view))
right_kpi.metric("Total violations (view)", int(view["violations"].sum()) if not view.empty else 0)

st.divider()

# ---------- High-Risk section (≥ 3) ----------
st.subheader("🚨 High-Risk Employees (≥ 3 violations)")
high_risk = view[view["violations"] >= 3].copy()
if high_risk.empty:
    st.info("No employees currently exceed the high-risk threshold.")
else:
    st.dataframe(
        high_risk[["EmployeeID","name","department","site","violations","last_updated","last_missing"]],
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ---------- Editable table (full view) ----------
st.subheader("Edit & Save Violations")
st.caption("Edit counts in the table and click **Save changes**. Only changed rows are updated.")

display_cols = ["EmployeeID","name","department","site","violations","last_updated","last_missing","last_image_key"]
view_for_edit = view.reindex(columns=[c for c in display_cols if c in view.columns])

edited = st.data_editor(
    view_for_edit,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "EmployeeID": st.column_config.TextColumn("EmployeeID", disabled=True),
        "name":       st.column_config.TextColumn("Name", disabled=True),
        "department": st.column_config.TextColumn("Department", disabled=True),
        "site":       st.column_config.TextColumn("Site", disabled=True),
        "violations": st.column_config.NumberColumn("Violations", min_value=0, step=1),
        "last_updated": st.column_config.TextColumn("Last Updated", disabled=True),
        "last_missing": st.column_config.TextColumn("Last Missing PPE", disabled=True),
        "last_image_key": st.column_config.TextColumn("Last Image Key", disabled=True),
    },
    key="violations_editor",
)

save_col, _ = st.columns([1, 5])
with save_col:
    if st.button("💾 Save changes", type="primary"):
        diffs = []
        for i in range(len(edited)):
            old_row = view_for_edit.iloc[i]
            new_row = edited.iloc[i]
            if int(old_row["violations"]) != int(new_row["violations"]):
                diffs.append((new_row["EmployeeID"], int(new_row["violations"])))

        if not diffs:
            st.info("No changes detected.")
        else:
            updated = 0
            for emp_id, new_val in diffs:
                try:
                    _update_violation_count(emp_id, new_val)
                    updated += 1
                except ClientError as e:
                    # Most likely IAM AccessDenied — show a clear message
                    st.error(
                        f"Failed to update {emp_id}: {e.response.get('Error',{}).get('Message','Access denied')}. "
                        "Grant dynamodb:UpdateItem on table/violation_master to the app's IAM identity."
                    )
                except Exception as e:
                    st.error(f"Failed to update {emp_id}: {e}")

            if updated > 0:
                st.success(f"Updated {updated} record(s).")
                st.cache_data.clear()
                st.rerun()
