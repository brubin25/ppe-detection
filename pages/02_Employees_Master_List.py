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
import base64
import html

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
    for n in (name, *aliases):
        if hasattr(data_mod, n):
            return getattr(data_mod, n)
    _missing.append(name if not aliases else f"{name} (aliases tried: {', '.join(aliases)})")
    return None

load_employees_from_dynamodb = _require("load_employees_from_dynamodb", "load_employees", "get_employees")
update_employee_violations   = _require("update_employee_violations", "update_employee", "set_employee_violations")
upsert_employee              = _require("upsert_employee", "put_employee", "create_or_update_employee")

if _missing:
    st.error(
        "Your `utils/data.py` is missing the following function(s): "
        + ", ".join(f"`{m}`" for m in _missing)
        + ".\n\nAdd them (or rename yours to match), then rerun."
    )
    st.stop()

# --- Page config & header ---
st.set_page_config(page_title="Employees (Master List)", page_icon="👥", layout="wide")
st.title("👥 Employees (Master List)")
st.caption("Directory of employees (DynamoDB: employee_master) with profile photos. Register new employees below.")

# --- AWS config (reads secrets w/ env fallbacks) ---
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET      = "ppe-detection-input"
S3_PREFIX      = "employees"             # employees/<employee_id>.<ext>
EMPLOYEE_TABLE = "employee_master"       # for profiles

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

# --- Helpers: photo handling ---
def _presign_photo(key: str, expires=60 * 60 * 24 * 7) -> str | None:
    """
    Return a presigned GET URL for the S3 object key.
    Requires IAM permission: s3:GetObject on the key.
    """
    try:
        client = _s3_client()
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return None

def _placeholder_avatar(name: str, size_px: int = 144) -> str:
    """
    Returns a data: URI for a simple SVG avatar (no S3 needed).
    Used as a fallback when presigned GET is not permitted yet.
    """
    initials = "".join([w[0] for w in (name or "U").split()][:2]).upper()
    initials = html.escape(initials)
    svg = f'''
    <svg xmlns="http://www.w3.org/2000/svg" width="{size_px}" height="{size_px}" viewBox="0 0 120 120">
      <defs>
        <linearGradient id="g" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stop-color="#c7d2fe"/>
          <stop offset="100%" stop-color="#93c5fd"/>
        </linearGradient>
      </defs>
      <rect width="120" height="120" rx="16" fill="url(#g)"/>
      <text x="50%" y="58%" text-anchor="middle" dominant-baseline="middle"
            font-family="Inter,system-ui,-apple-system,Segoe UI,Roboto" font-size="56" fill="#0f172a">{initials}</text>
    </svg>
    '''
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"

def _photo_src_for_row(photo_key: str | None, name: str) -> str:
    """
    Prefer a presigned URL (needs s3:GetObject). If that can't be created,
    return a data: URI placeholder so we never show a broken image.
    """
    if photo_key:
        url = _presign_photo(photo_key)
        if url:
            return url
    return _placeholder_avatar(name)

# ---------- DATA LOAD ----------
@st.cache_data(ttl=30, show_spinner=False)
def _cached_load_employees():
    st.session_state.setdefault("_emp_load_count", 0)
    st.session_state["_emp_load_count"] += 1
    print(f"[info] Loading employees from DynamoDB (call #{st.session_state['_emp_load_count']})")
    return load_employees_from_dynamodb()

# ---------- SEARCH ----------
q = st.text_input("Search employees", placeholder="Search by name, EmployeeID, department, site, email…")

# ---------- DIRECTORY ----------
df_raw = _cached_load_employees().copy()

# Normalize columns expected here (defensive)
for col in ["EmployeeID", "name", "department", "site", "job_title", "email", "status", "created_at", "photo_key"]:
    if col not in df_raw.columns:
        df_raw[col] = ""

# Build photo source (presigned or placeholder)
df_raw["Photo"] = [
    _photo_src_for_row(row.get("photo_key"), row.get("name", "")) for _, row in df_raw.iterrows()
]

# Search filter
if q:
    ql = q.lower()
    df_raw = df_raw[
        df_raw.apply(
            lambda r: any(
                ql in str(r.get(c, "")).lower()
                for c in ["EmployeeID", "name", "department", "site", "job_title", "email", "status"]
            ),
            axis=1,
        )
    ]

# Reorder & rename for display
df_dir = df_raw[
    ["Photo", "EmployeeID", "name", "department", "site", "job_title", "email", "status", "created_at"]
].rename(
    columns={
        "name": "Name",
        "department": "Department",
        "site": "Site",
        "job_title": "Job title",
        "email": "Email",
        "status": "Status",
        "created_at": "Created",
    }
).reset_index(drop=True)

st.markdown("## Directory")

# 3× larger photos (approx). ImageColumn width controls cell size.
st.dataframe(
    df_dir,
    use_container_width=True,
    column_config={
        "Photo": st.column_config.ImageColumn(
            "Photo",
            width=144,              # ~3x the default small thumbs
            help="Employee profile photo",
        )
    },
    hide_index=True,
)

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

def _make_employee_id(name: str) -> str:
    # (kept the same logic you accepted earlier)
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
        "EmployeeID": employee_id,
        "name": payload.get("name"),
        "department": payload.get("department"),
        "site": payload.get("site"),
        "job_title": payload.get("job_title"),
        "email": payload.get("email"),
        "photo_key": payload.get("photo_key"),
        "created_at": payload.get("created_at"),
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
        st.info("Profile saved to `employee_master`. You can now associate detections with this EmployeeID.")
    except Exception as e:
        st.error(f"Something went wrong while creating the employee: {e}")
