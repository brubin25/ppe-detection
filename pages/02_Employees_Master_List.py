# pages/02_Employees_Master_List.py
import streamlit as st
import pandas as pd

# NEW: imports for S3 & DynamoDB upload of employee photo + profile
import os
import uuid
from datetime import datetime
import boto3

from utils.data import load_employees_from_dynamodb, update_employee_violations, upsert_employee


st.set_page_config(page_title="Employees (Master List)", page_icon="👥", layout="wide")
st.title("👥 Employees (Master List)")
st.caption("Manage aggregated violation counts per employee (DynamoDB: PPEViolationTracker).")

@st.cache_data(ttl=30, show_spinner=False)
def _cached_load_employees():
    st.session_state.setdefault("_emp_load_count", 0)
    st.session_state["_emp_load_count"] += 1
    print(f"[info] Loading employees from DynamoDB (call #{st.session_state['_emp_load_count']})")
    return load_employees_from_dynamodb()

# ------------------------
# Existing toolbar controls
# ------------------------
toolbar = st.container()
with toolbar:
    c1, c2, c3, c4, c5 = st.columns([2,2,2,2,1])
    query = c1.text_input("Search by EmployeeID", placeholder="e.g., employee001")
    min_v = c2.number_input("Min violations", min_value=0, value=0, step=1)
    sort_by = c3.selectbox("Sort by", ["violations", "EmployeeID"], index=0)
    sort_asc = c4.toggle("Ascending", value=False)
    refresh = c5.button("↻ Refresh")

if refresh:
    st.cache_data.clear()
    st.experimental_rerun()

df = _cached_load_employees()

# ------------------------
# Filter/sort view
# ------------------------
view = df.copy()
if query:
    view = view[view["EmployeeID"].str.contains(query, case=False)]
view = view[view["violations"] >= min_v]
view = view.sort_values(by=sort_by, ascending=sort_asc, kind="mergesort").reset_index(drop=True)

# ------------------------
# KPI cards
# ------------------------
k1, k2, k3 = st.columns(3)
k1.metric("Employees", len(view))
k2.metric("Total violations", int(view["violations"].sum()) if not view.empty else 0)
threshold = k3.number_input("Critical threshold", min_value=1, value=3, step=1)
critical_count = (view["violations"] >= threshold).sum() if not view.empty else 0
k3.metric("Critical (≥ threshold)", int(critical_count))

st.divider()

# ------------------------
# Top violators (simple chart)
# ------------------------
st.subheader("Top violators")
if view.empty:
    st.info("No data.")
else:
    top = view.sort_values("violations", ascending=False).head(10).set_index("EmployeeID")["violations"]
    st.bar_chart(top)

st.divider()

# ------------------------
# Editable grid
# ------------------------
st.subheader("Edit & Save")
st.caption("You can edit violations in the table and click **Save changes**. Only changed rows will be updated.")

edited = st.data_editor(
    view,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "EmployeeID": st.column_config.TextColumn("EmployeeID", disabled=True),
        "violations": st.column_config.NumberColumn("Violations", help="Total aggregated violations", min_value=0, step=1),
    },
    key="emp_editor",
)

left, right = st.columns([1, 6])
with left:
    if st.button("Save changes", type="primary"):
        diffs = []
        for i in range(len(edited)):
            row_old = view.iloc[i]
            row_new = edited.iloc[i]
            if int(row_old["violations"]) != int(row_new["violations"]):
                diffs.append((row_new["EmployeeID"], int(row_new["violations"])))
        if not diffs:
            st.info("No changes detected.")
        else:
            for emp_id, new_val in diffs:
                print(f"[info] Saving change -> {emp_id}:{new_val}")
                update_employee_violations(emp_id, new_val)
            st.success(f"Updated {len(diffs)} record(s).")
            st.cache_data.clear()
with right:
    st.caption("Tip: set a critical threshold above to monitor high-risk employees.")

st.divider()

# ------------------------
# Quick add / upsert (kept as-is)
# ------------------------
st.subheader("Add employee")
with st.form("add_emp_form", clear_on_submit=True):
    c1, c2, c3 = st.columns([2,1,1])
    new_emp_id = c1.text_input("New EmployeeID", placeholder="e.g., employee123")
    new_emp_v = c2.number_input("Initial violations", min_value=0, value=0, step=1)
    submitted = c3.form_submit_button("Add / Upsert")
    if submitted:
        if not new_emp_id.strip():
            st.error("EmployeeID cannot be empty.")
        else:
            upsert_employee(new_emp_id.strip(), int(new_emp_v))
            st.success(f"Upserted '{new_emp_id}' with violations={int(new_emp_v)}.")
            st.cache_data.clear()

# =====================================================================
# NEW SECTION: Register new employee WITH ID photo (S3 + DynamoDB employee_master)
# =====================================================================

st.divider()
st.subheader("Register new employee (with ID photo)")
st.caption(
    "Create a new employee profile with professional details and upload an ID photo. "
    "The photo is stored in S3 at **ppe-detection-input/employees/** and the profile is saved to "
    "**DynamoDB table `employee_master`** (separate from your violation tracker)."
)

# --- AWS config (reads secrets w/ env fallbacks) ---
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION        = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET        = "ppe-detection-input"
S3_PREFIX        = "employees"             # employees/<employee_id>.<ext>
EMPLOYEE_TABLE   = "employee_master"       # <-- NEW TABLE for employee profiles

def _s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
    )

def _ddb_table(name: str):
    ddb = boto3.resource(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
    )
    return ddb.Table(name)

def _make_employee_id(name: str) -> str:
    slug = "".join(ch for ch in (name or "").lower() if ch.isalnum() or ch in ("-", "_"))
    slug = slug.replace("__", "_").strip("_") or "user"
    short = uuid.uuid4().hex[:4]
    date = datetime.utcnow().strftime("%Y%m%d")
    return f"EMP-{slug}-{date}-{short}"

def _put_photo_to_s3(employee_id: str, file, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    key = f"{S3_PREFIX}/{employee_id}{ext}"
    content_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")
    s3 = _s3_client()
    file.seek(0)
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=file.read(),
        ContentType=content_type,
        ACL="private",
    )
    return key

def _upsert_employee_profile_to_master(employee_id: str, payload: dict):
    """Write the profile to employee_master (separate table)."""
    tbl = _ddb_table(EMPLOYEE_TABLE)
    item = {
        "EmployeeID": employee_id,           # PK
        "name": payload.get("name"),
        "department": payload.get("department"),
        "site": payload.get("site"),
        "job_title": payload.get("job_title"),
        "email": payload.get("email"),
        "photo_key": payload.get("photo_key"),
        "created_at": payload.get("created_at"),  # ISO8601
        "status": payload.get("status", "Active"),
        # Feel free to expand schema later (manager, phone, etc.)
    }
    tbl.put_item(Item=item)

with st.form("register_employee_form", clear_on_submit=False, border=True):
    cL, cR = st.columns([1.2, 1])
    with cL:
        full_name  = st.text_input("Full name", placeholder="e.g., Jordan Alvarez", max_chars=80)
        department = st.selectbox(
            "Department",
            ["Manufacturing", "Maintenance", "Quality", "Logistics", "Safety", "Other"],
            index=0,
        )
        site       = st.text_input("Site / Location", placeholder="e.g., Plant 3")
        job_title  = st.text_input("Job title (optional)", placeholder="e.g., Line Operator")
        work_email = st.text_input("Work email (optional)", placeholder="e.g., user@company.com")

    with cR:
        st.markdown("**Employee ID photo**")
        photo = st.file_uploader("Upload image", type=["jpg", "jpeg", "png", "webp"])
        if photo is not None:
            st.image(photo, caption="Preview", width=260)

    submit_new_emp = st.form_submit_button("Create employee", type="primary")

if submit_new_emp:
    if not full_name.strip():
        st.error("Please provide the employee's full name.")
        st.stop()
    if photo is None:
        st.error("Please upload an employee ID photo.")
        st.stop()

    employee_id = _make_employee_id(full_name)  # automatic
    created_at  = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    try:
        with st.spinner("Uploading photo to S3…"):
            photo_key = _put_photo_to_s3(employee_id, photo, photo.name)

        with st.spinner("Saving employee profile to DynamoDB (employee_master)…"):
            payload = {
                "name": full_name,
                "department": department,
                "site": site,
                "job_title": job_title or None,
                "email": work_email or None,
                "photo_key": photo_key,
                "created_at": created_at,
                "status": "Active",
            }
            _upsert_employee_profile_to_master(employee_id, payload)

        st.success("Employee created successfully.")
        s1, s2 = st.columns([1, 2])
        with s1:
            if photo is not None:
                photo.seek(0)
                st.image(photo, width=220)
        with s2:
            st.markdown(
                f"""
**EmployeeID:** `{employee_id}`  
**Name:** {full_name}  
**Department:** {department}  
**Site:** {site}  
**Job title:** {job_title or "—"}  
**Work email:** {work_email or "—"}  
**Photo S3 key:** `{photo_key}`  
**Created at:** {created_at}
                """
            )

        # NOTE: This does NOT alter PPEViolationTracker. Master list above still shows violations table.
        st.info("Profile saved to `employee_master`. You can now associate detections with this EmployeeID.")
    except Exception as e:
        st.error(f"Something went wrong while creating the employee: {e}")
