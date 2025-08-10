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
import re

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

# Map to whatever exists in utils/data.py (kept for compatibility even if not used here)
load_employees_from_dynamodb = _require("load_employees_from_dynamodb", "load_employees", "get_employees")
update_employee_violations   = _require("update_employee_violations", "update_employee", "set_employee_violations")
upsert_employee              = _require("upsert_employee", "put_employee", "create_or_update_employee")

st.set_page_config(page_title="Employees (Master List)", page_icon="👥", layout="wide")

st.title("👥 Employees (Master List)")
st.caption("Directory of employees (DynamoDB: employee_master) with profile photos. Register new employees below.")

# --- AWS config (reads secrets w/ env fallbacks) ---
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET       = "ppe-detection-input"
S3_PREFIX       = "employees"             # employees/<employee_id>.<ext>
EMPLOYEE_TABLE  = "employee_master"       # table for employee profiles

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

def _public_s3_url(key: str) -> str:
    # Works for private objects if bucket policy allows it; for purely private buckets
    # consider using presigned URLs instead.
    if not key:
        return ""
    # us-east-1 is special; us-east-2 (your region) includes the region in the hostname
    return f"https://{S3_BUCKET}.s3.{REGION}.amazonaws.com/{key}"

def _make_employee_id_from_name(name: str) -> str:
    # Not used now for final ID, but kept (do not delete)
    slug = "".join(ch for ch in (name or "").lower() if ch.isalnum() or ch in ("-", "_"))
    slug = slug.replace("__", "_").strip("_") or "user"
    short = uuid.uuid4().hex[:4]
    date = datetime.utcnow().strftime("%Y%m%d")
    return f"EMP-{slug}-{date}-{short}"

def _next_emp_id(existing_ids) -> str:
    """
    Create sequential IDs: emp01, emp02, ...
    existing_ids: iterable of strings (EmployeeID values already in the table)
    """
    max_num = 0
    for eid in existing_ids:
        m = re.fullmatch(r"emp(\d+)", str(eid).lower().strip())
        if m:
            try:
                num = int(m.group(1))
                if num > max_num:
                    max_num = num
            except:
                pass
    nxt = max_num + 1
    return f"emp{nxt:02d}"

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
    }
    tbl.put_item(Item=item)

@st.cache_data(ttl=30, show_spinner=False)
def _cached_directory() -> pd.DataFrame:
    """Scan employee_master and return a display-ready DataFrame."""
    tbl = _ddb_table(EMPLOYEE_TABLE)

    items = []
    scan_kwargs = {}
    while True:
        resp = tbl.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" in resp:
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        else:
            break

    if not items:
        return pd.DataFrame(columns=[
            "Photo", "EmployeeID", "Name", "Department", "Site",
            "Job title", "Email", "Status", "Created"
        ])

    def to_row(it):
        return {
            "Photo": _public_s3_url(it.get("photo_key", "")),
            "EmployeeID": it.get("EmployeeID", ""),
            "Name": it.get("name", ""),
            "Department": it.get("department", ""),
            "Site": it.get("site", ""),
            "Job title": it.get("job_title", ""),
            "Email": it.get("email", ""),
            "Status": it.get("status", "Active"),
            "Created": it.get("created_at", ""),
        }

    df = pd.DataFrame([to_row(x) for x in items]).sort_values("EmployeeID")
    return df.reset_index(drop=True)

# ---------------------------------------
# Search + Directory (with bigger photos)
# ---------------------------------------
search = st.text_input(
    "Search employees",
    placeholder="Search by name, EmployeeID, department, site, email…"
)

df_dir = _cached_directory()

if search:
    s = search.strip().lower()
    mask = pd.Series([False] * len(df_dir))
    for col in ["EmployeeID", "Name", "Department", "Site", "Job title", "Email", "Status", "Created"]:
        mask = mask | df_dir[col].astype(str).str.lower().str.contains(s, na=False)
    df_dir = df_dir[mask]

DISPLAY_COLS = ["Photo", "EmployeeID", "Name", "Department", "Site", "Job title", "Email", "Status", "Created"]

st.subheader("Directory")
if df_dir.empty:
    st.info("No employees found yet. Use the form below to register the first employee.")
else:
    # Build table for display
    grid_df = df_dir.reindex(columns=DISPLAY_COLS)

    # 🔎 Make Photo column render 3× larger thumbnails by embedding <img width="120">
    def make_img_tag(url):
        if not url:
            return ""
        return f'<img src="{url}" width="120" style="border-radius:10px;"/>'

    grid_df = grid_df.copy()
    grid_df["Photo"] = grid_df["Photo"].apply(make_img_tag)

    # Optional minimal table styling
    st.markdown(
        """
        <style>
          table.emp-dir {border-collapse: collapse; width: 100%;}
          table.emp-dir th, table.emp-dir td {padding: 10px 12px; border-bottom: 1px solid #eef2f7; text-align: left;}
          table.emp-dir th {background:#f8fafc; font-weight:700;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(grid_df.to_html(escape=False, index=False, classes="emp-dir"), unsafe_allow_html=True)

st.divider()

# ------------------------
# Register new employee
# ------------------------
st.subheader("Add employee  ↪")
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
            st.image(photo, caption="Preview", width=220)

    submit_new_emp = st.form_submit_button("Create employee", type="primary")

if submit_new_emp:
    if not full_name.strip():
        st.error("Please provide the employee's full name.")
        st.stop()
    if photo is None:
        st.error("Please upload an employee ID photo.")
        st.stop()

    # Create sequential EmployeeID like emp01, emp02, ...
    try:
        existing = _cached_directory()["EmployeeID"].tolist()
    except Exception:
        existing = []
    employee_id = _next_emp_id(existing)

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
                st.image(photo, width=240)
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
        st.info("Profile saved to `employee_master`. You can now associate detections with this EmployeeID.")
        st.cache_data.clear()  # refresh the directory
    except Exception as e:
        st.error(f"Something went wrong while creating the employee: {e}")
