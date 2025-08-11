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

# Map to whatever exists in utils/data.py (kept for your existing master list logic)
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
st.title("👥👥 Employees (Master List)")
st.caption("Directory of employees (DynamoDB: employee_master) with profile photos. Register new employees below.")

# --- AWS config (reads secrets w/ env fallbacks) ---
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION        = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET        = "ppe-detection-input"
S3_PREFIX        = "employees"             # employees/<employee_id>.<ext>
EMPLOYEE_TABLE   = "employee_master"       # table that holds employee directory

DISPLAY_COLS = ["Photo", "EmployeeID", "Name", "Department", "Site", "Job title", "Email", "Status", "Created"]

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

def _presigned_url(key: str, expires=3600) -> str | None:
    if not key:
        return None
    try:
        s3 = _s3_client()
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return None

def _scan_employee_master() -> pd.DataFrame:
    """Read employee_master and return normalized DataFrame."""
    tbl = _ddb_table(EMPLOYEE_TABLE)
    items = []
    start_key = None
    while True:
        if start_key:
            resp = tbl.scan(ExclusiveStartKey=start_key)
        else:
            resp = tbl.scan()
        items.extend(resp.get("Items", []))
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            break

    if not items:
        # Return an empty dataframe with the display columns to avoid KeyError downstream
        return pd.DataFrame(columns=DISPLAY_COLS)

    rows = []
    for it in items:
        rows.append(
            {
                "EmployeeID": it.get("EmployeeID", ""),
                "Name": it.get("name", ""),
                "Department": it.get("department", ""),
                "Site": it.get("site", ""),
                "Job title": it.get("job_title", ""),
                "Email": it.get("email", ""),
                "Status": it.get("status", ""),
                "Created": it.get("created_at", ""),
                "Photo": _presigned_url(it.get("photo_key", "")),
            }
        )
    df = pd.DataFrame(rows)

    # Ensure all DISPLAY_COLS exist (even if some items lack fields)
    for c in DISPLAY_COLS:
        if c not in df.columns:
            df[c] = ""
    return df

@st.cache_data(ttl=30, show_spinner=False)
def _cached_directory():
    return _scan_employee_master()

# ======= Search / Directory =======
search = st.text_input("Search employees", placeholder="Search by name, EmployeeID, department, site, email…")

df_dir = _cached_directory()

# Apply search filter (works even when empty)
if search:
    s = search.strip().lower()
    mask = pd.Series([False] * len(df_dir))
    for col in ["EmployeeID", "Name", "Department", "Site", "Job title", "Email", "Status", "Created"]:
        mask = mask | df_dir[col].astype(str).str.lower().str.contains(s, na=False)
    df_dir = df_dir[mask]

# ✅ Sort by Created (descending; newest first)
if not df_dir.empty and "Created" in df_dir.columns:
    try:
        df_dir["Created_dt"] = pd.to_datetime(df_dir["Created"], errors="coerce")
        df_dir = df_dir.sort_values(by="Created_dt", ascending=False).drop(columns=["Created_dt"])
    except Exception as e:
        st.warning(f"Could not sort by creation date: {e}")

# Keep the column order and avoid KeyError even when empty
if df_dir.empty:
    grid_df = pd.DataFrame(columns=DISPLAY_COLS)
else:
    grid_df = df_dir.reindex(columns=DISPLAY_COLS)

# NEW: add the running index column as the first column (1..n)
if grid_df.empty:
    grid_df_display = pd.DataFrame(columns=["#"] + DISPLAY_COLS)
else:
    grid_df_display = grid_df.copy().reset_index(drop=True)
    grid_df_display.insert(0, "#", range(1, len(grid_df_display) + 1))

# Enlarged photo thumbnails
st.subheader("Directory")
if grid_df_display.empty:
    st.info("No employees found yet. Use the form below to register the first employee.")
else:
    st.dataframe(
        grid_df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn("#", help="Row number", format="%d", width=70),
            "Photo": st.column_config.ImageColumn(
                "Photo",
                help="Employee photo",
                width=288,          # enlarged to ~3×
            ),
            "EmployeeID": st.column_config.TextColumn("EmployeeID"),
            "Name": st.column_config.TextColumn("Name"),
            "Department": st.column_config.TextColumn("Department"),
            "Site": st.column_config.TextColumn("Site"),
            "Job title": st.column_config.TextColumn("Job title"),
            "Email": st.column_config.TextColumn("Email"),
            "Status": st.column_config.TextColumn("Status"),
            "Created": st.column_config.TextColumn("Created"),
        },
    )

st.divider()

# =====================================================================
# Register new employee WITH ID photo (S3 + DynamoDB employee_master)
# =====================================================================

def _make_employee_id_sequential(df_master: pd.DataFrame) -> str:
    """Generate sequential IDs emp01, emp02, … based on what exists; works when table is empty."""
    if df_master.empty or "EmployeeID" not in df_master:
        return "emp01"
    nums = []
    for e in df_master["EmployeeID"].astype(str):
        if e.lower().startswith("emp") and e[3:].isdigit():
            nums.append(int(e[3:]))
    nxt = (max(nums) + 1) if nums else 1
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
    """Write/overwrite the profile to employee_master (separate table)."""
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

st.subheader("Register new employee (with ID photo)")
st.caption(
    "Create a new employee profile with professional details and upload an ID photo. "
    "The photo is stored in S3 at **ppe-detection-input/employees/** and the profile is saved to "
    "**DynamoDB table `employee_master`**."
)

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

    employee_id = _make_employee_id_sequential(_cached_directory())
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

        # Refresh directory cache so the new employee appears immediately
        st.cache_data.clear()
        st.experimental_rerun()   # ✅ auto-refresh the page/table

    except Exception as e:
        st.error(f"Something went wrong while creating the employee: {e}")
