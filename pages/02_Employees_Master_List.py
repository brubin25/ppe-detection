# pages/02_Employees_Master_List.py
import streamlit as st
import pandas as pd

# --- Make sure /utils is importable from inside /pages on Streamlit Cloud ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# NEW: imports for S3 & DynamoDB upload of employee photo + profile
import uuid
from datetime import datetime
import boto3
import importlib

# --- Robust import of utils.data, with graceful fallbacks and clear errors ---
_missing = []
try:
    data_mod = importlib.import_module("utils.data")
except Exception as e:
    st.error(
        "Couldn't import `utils.data`. Make sure the repo has a `utils/` folder "
        "with `__init__.py` and `data.py` in it. Error: {}".format(e)
    )
    st.stop()

def _require(name, *aliases):
    """Return the first attribute that exists on data_mod; remember if missing."""
    for n in (name, *aliases):
        if hasattr(data_mod, n):
            return getattr(data_mod, n)
    _missing.append(name if not aliases else f"{name} (aliases tried: {', '.join(aliases)})")
    return None

# (Kept for compatibility even though we no longer use them on this page)
load_employees_from_dynamodb = _require("load_employees_from_dynamodb", "load_employees", "get_employees")
update_employee_violations   = _require("update_employee_violations", "update_employee", "set_employee_violations")
upsert_employee              = _require("upsert_employee", "put_employee", "create_or_update_employee")

# Do not block the page for missing legacy helpers anymore (we don't use them below)
# They are still imported above for compatibility with your repo.

# ------------------------
# PAGE CONFIG
# ------------------------
st.set_page_config(page_title="Employees (Master List)", page_icon="👥", layout="wide")
st.title("👥 Employees (Master List)")
st.caption("Directory of employees from DynamoDB **employee_master** with S3 photo thumbnails. Add new employees below.")

# ------------------------
# AWS CONFIG — reads secrets/env
# ------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET      = "ppe-detection-input"
S3_PREFIX      = "employees"              # employees/<employee_id>.<ext>
EMPLOYEE_TABLE = "employee_master"        # directory source

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

# ------------------------
# DATA LOADERS
# ------------------------
@st.cache_data(ttl=30, show_spinner=False)
def load_employee_directory():
    """
    Read the employee directory from DynamoDB employee_master
    and return a DataFrame with presigned S3 URLs for images.
    """
    tbl = _ddb_table(EMPLOYEE_TABLE)
    items = []
    # Full scan (table is small; if it grows, we can paginate)
    resp = tbl.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = tbl.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))

    # Build DataFrame
    if not items:
        return pd.DataFrame(
            columns=["Photo", "EmployeeID", "name", "department", "site", "job_title", "email", "status", "created_at"]
        )

    df = pd.DataFrame(items)

    # Ensure consistent columns
    for col in ["EmployeeID", "name", "department", "site", "job_title", "email", "status", "created_at", "photo_key"]:
        if col not in df.columns:
            df[col] = ""

    # Generate presigned URLs for photos (private bucket)
    s3 = _s3_client()
    def presign(key: str) -> str:
        if not key:
            return ""
        try:
            return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": key},
                ExpiresIn=3600,
            )
        except Exception:
            return ""

    df["Photo"] = df["photo_key"].apply(presign)

    # Order and rename display columns
    df = df[
        ["Photo", "EmployeeID", "name", "department", "site", "job_title", "email", "status", "created_at"]
    ].rename(
        columns={
            "name": "Name",
            "department": "Department",
            "site": "Site",
            "job_title": "Job Title",
            "email": "Email",
            "status": "Status",
            "created_at": "Created",
        }
    )

    # Sort by Name (stable)
    df = df.sort_values(["Name", "EmployeeID"], kind="mergesort").reset_index(drop=True)
    return df

# ------------------------
# DIRECTORY UI (professional, searchable)
# ------------------------
dir_toolbar = st.container()
with dir_toolbar:
    l, r, r2 = st.columns([3, 1, 1])
    search = l.text_input("Search employees", placeholder="Name, EmployeeID, Department, Site, Email…")
    dept_filter = r.selectbox("Filter by department", ["All", "Manufacturing", "Maintenance", "Quality", "Logistics", "Safety", "Other"])
    refresh = r2.button("↻ Refresh")

if refresh:
    st.cache_data.clear()
    st.experimental_rerun()

directory_df = load_employee_directory()

# Apply filters
filtered = directory_df.copy()
if search:
    s = search.strip().lower()
    mask = (
        filtered["Name"].str.lower().str.contains(s, na=False)
        | filtered["EmployeeID"].str.lower().str.contains(s, na=False)
        | filtered["Department"].str.lower().str.contains(s, na=False)
        | filtered["Site"].str.lower().str.contains(s, na=False)
        | filtered["Email"].str.lower().str.contains(s, na=False)
    )
    filtered = filtered[mask]

if dept_filter != "All":
    filtered = filtered[filtered["Department"] == dept_filter]

# KPI
k1, k2 = st.columns(2)
k1.metric("Employees", len(filtered))
k2.metric("Total in directory", len(directory_df))

# Display directory table with face thumbnails
st.subheader("Employee directory")
if filtered.empty:
    st.info("No employees found. Use the form below to register a new employee.")
else:
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Photo": st.column_config.ImageColumn(
                "Photo",
                help="Employee ID photo from S3",
                width="small",
            ),
            "EmployeeID": st.column_config.TextColumn("EmployeeID", help="Primary key"),
            "Name": st.column_config.TextColumn("Name"),
            "Department": st.column_config.TextColumn("Department"),
            "Site": st.column_config.TextColumn("Site"),
            "Job Title": st.column_config.TextColumn("Job Title"),
            "Email": st.column_config.TextColumn("Email"),
            "Status": st.column_config.TextColumn("Status"),
            "Created": st.column_config.TextColumn("Created"),
        },
    )

# =====================================================================
# REGISTER NEW EMPLOYEE (kept exactly as you approved)
# =====================================================================
st.divider()
st.subheader("Register new employee (with ID photo)")
st.caption(
    "Create a new employee profile with professional details and upload an ID photo. "
    "The photo is stored in S3 at **ppe-detection-input/employees/** and the profile is saved to "
    "**DynamoDB table `employee_master`**."
)

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

        # Clear and reload the directory so the new hire appears immediately
        st.cache_data.clear()
        st.success("Directory refreshed. Scroll up to see the new employee.")
    except Exception as e:
        st.error(f"Something went wrong while creating the employee: {e}")
