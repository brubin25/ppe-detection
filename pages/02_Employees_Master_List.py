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
from io import BytesIO

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

# Map to whatever exists in utils/data.py (still loaded for compatibility)
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

st.set_page_config(page_title="Employees (Master List)", page_icon="👥", layout="wide")
st.title("👥 Employees (Master List)")
st.caption("Directory of employees (DynamoDB: employee_master) with profile photos. Register new employees below.")

# --- AWS config (reads secrets w/ env fallbacks) ---
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET      = "ppe-detection-input"
S3_PREFIX      = "employees"             # employees/<employee_id>.<ext>
EMPLOYEE_TABLE = "employee_master"       # table for employee profiles

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

# --------- LIST + SEARCH (employee_master) ----------
@st.cache_data(ttl=30, show_spinner=False)
def _scan_employee_master():
    """Return all profiles from employee_master."""
    tbl = _ddb_table(EMPLOYEE_TABLE)
    items = []
    scan_kwargs = {}
    while True:
        resp = tbl.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        scan_kwargs["ExclusiveStartKey"] = lek
    # Normalize keys (some optional)
    for it in items:
        it.setdefault("name", "")
        it.setdefault("department", "")
        it.setdefault("site", "")
        it.setdefault("job_title", "")
        it.setdefault("email", "")
        it.setdefault("status", "Active")
        it.setdefault("photo_key", "")
        it.setdefault("created_at", "")
    return items

# 3× bigger thumbnails (previously ~96px). Now ~288px.
FACE_THUMB_W = 288

@st.cache_data(ttl=60, show_spinner=False)
def _img_data_uri(bucket: str, key: str, width: int = FACE_THUMB_W) -> str:
    """
    Fetch the image from S3 and return a data URI scaled by browser width attr.
    (We just embed original bytes; width is enforced via HTML attribute.)
    """
    if not key:
        return ""
    try:
        s3 = _s3_client()
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = obj["Body"].read()
        # Guess mime from extension
        ext = os.path.splitext(key)[1].lower()
        mime = "image/jpeg"
        if ext == ".png":
            mime = "image/png"
        elif ext == ".webp":
            mime = "image/webp"
        b64 = base64.b64encode(data).decode("utf-8")
        return f'<img src="data:{mime};base64,{b64}" width="{width}" style="border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,.08);" />'
    except Exception:
        return ""

# --- Directory UI ---
with st.container():
    # Search
    c_search, c_sp = st.columns([3, 1])
    with c_search:
        q = st.text_input("Search employees", placeholder="Search by name, EmployeeID, department, site, email…")

    items = _scan_employee_master()
    rows = []
    for it in items:
        photo_html = _img_data_uri(S3_BUCKET, it.get("photo_key", "")) if it.get("photo_key") else ""
        rows.append(
            {
                "Photo": photo_html,
                "EmployeeID": it.get("EmployeeID", ""),
                "Name": it.get("name", ""),
                "Department": it.get("department", ""),
                "Site": it.get("site", ""),
                "Job title": it.get("job_title", ""),
                "Email": it.get("email", ""),
                "Status": it.get("status", "Active"),
                "Created": it.get("created_at", ""),
            }
        )
    df_dir = pd.DataFrame(rows)

    # Filter by search query
    if q:
        q_lower = q.lower().strip()
        mask = (
            df_dir["EmployeeID"].str.lower().str.contains(q_lower, na=False)
            | df_dir["Name"].str.lower().str.contains(q_lower, na=False)
            | df_dir["Department"].str.lower().str.contains(q_lower, na=False)
            | df_dir["Site"].str.lower().str.contains(q_lower, na=False)
            | df_dir["Email"].str.lower().str.contains(q_lower, na=False)
        )
        df_dir = df_dir[mask]

    # Tidy order
    df_dir = df_dir[
        ["Photo", "EmployeeID", "Name", "Department", "Site", "Job title", "Email", "Status", "Created"]
    ].reset_index(drop=True)

    # Render as HTML for the Photo column
    st.markdown("#### Employee directory")
    st.caption("Profiles from the `employee_master` table.")
    if df_dir.empty:
        st.info("No employees found yet.")
    else:
        # Build simple HTML table to keep the Photo <img> column rendered
        def _to_html_table(df: pd.DataFrame) -> str:
            thead = "".join(f"<th style='text-align:left; padding:10px 12px;'>{c}</th>" for c in df.columns)
            trs = []
            for _, r in df.iterrows():
                tds = []
                for c in df.columns:
                    val = r[c]
                    if c == "Photo" and isinstance(val, str) and val.startswith("<img"):
                        tds.append(f"<td style='padding:10px 12px; vertical-align:middle;'>{val}</td>")
                    else:
                        tds.append(f"<td style='padding:10px 12px; vertical-align:middle;'>{val}</td>")
                trs.append("<tr>" + "".join(tds) + "</tr>")
            tbody = "".join(trs)
            return f"""
<table style="border-collapse:separate; border-spacing:0 8px; width:100%;">
  <thead style="font-weight:700; color:#0f172a;">
    <tr>{thead}</tr>
  </thead>
  <tbody>{tbody}</tbody>
</table>
"""
        st.markdown(_to_html_table(df_dir), unsafe_allow_html=True)

st.divider()

# =====================================================================
# REGISTER NEW EMPLOYEE (same flow as before) — ONLY CHANGE: EMP IDs like emp01
# =====================================================================

st.subheader("Register new employee (with ID photo)")
st.caption(
    "Create a new employee profile with professional details and upload an ID photo. "
    "The photo is stored in S3 at **ppe-detection-input/employees/** and the profile is saved to "
    "**DynamoDB table `employee_master`**."
)

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

# ---- NEW: sequential EmployeeID like emp01, emp02, ... ----
def _next_employee_id(prefix: str = "emp", min_width: int = 2) -> str:
    """
    Scan employee_master, find max N from IDs of form {prefix}{N}, return next.
    min_width pads with zeros (e.g., width=2 => emp01). Grows as needed.
    """
    items = _scan_employee_master()
    max_n = 0
    for it in items:
        eid = str(it.get("EmployeeID", "")).lower()
        if eid.startswith(prefix):
            num = eid[len(prefix):]
            if num.isdigit():
                max_n = max(max_n, int(num))
    next_n = max_n + 1
    # pad to at least min_width, grow naturally if bigger
    width = max(min_width, len(str(next_n)))
    return f"{prefix}{str(next_n).zfill(width)}"

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

    # 👇 REPLACED the old generator with sequential IDs like emp01, emp02, ...
    employee_id = _next_employee_id(prefix="emp", min_width=2)
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
        # refresh directory cache so the new employee appears immediately
        _scan_employee_master.clear()
        st.experimental_rerun()
    except Exception as e:
        st.error(f"Something went wrong while creating the employee: {e}")
