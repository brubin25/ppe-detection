# pages/03_Violations.py
import streamlit as st
import pandas as pd

# --- Make sure /utils is importable from inside /pages on Streamlit Cloud ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- AWS / general imports
import importlib
import boto3
import mimetypes
import time
import uuid
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from botocore.exceptions import ClientError

# ---------- Robust import of utils.data, with graceful fallbacks ----------
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
    """Return the first attribute that exists on data_mod; remember if missing."""
    for n in (name, *aliases):
        if hasattr(data_mod, n):
            return getattr(data_mod, n)
    _missing.append(name if not aliases else f"{name} (aliases tried: {', '.join(aliases)})")
    return None


# Map to whatever exists in utils/data.py (compatible with your Employees page)
load_employees_from_dynamodb = _require("load_employees_from_dynamodb", "load_employees", "get_employees")
update_employee_violations   = _require("update_employee_violations", "update_employee", "set_employee_violations")
upsert_employee              = _require("upsert_employee", "put_employee", "create_or_update_employee")

if _missing:
    st.set_page_config(page_title="Violations", page_icon="⚠️", layout="wide")
    st.error(
        "Your `utils/data.py` is missing the following function(s): "
        + ", ".join(f"`{m}`" for m in _missing)
        + ".\n\nAdd them (or rename yours to match), then rerun."
    )
    st.stop()

# ---------- Page UI ----------
st.set_page_config(page_title="Violations", page_icon="⚠️", layout="wide")
st.title("⚠️ Violations")
st.caption("Upload a photo to S3 (uploads/) to trigger detection, then view & edit aggregated counts (DynamoDB: violation_master).")

# ---------- AWS config ----------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

S3_BUCKET      = "ppe-detection-input"
UPLOAD_PREFIX  = "uploads/"

EMPLOYEE_TABLE = "employee_master"
VIOLATION_TABLE= "violation_master"

def s3_client():
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
    )

def ddb_resource():
    return boto3.resource(
        "dynamodb",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=REGION,
    )

def ddb_table(name:str):
    return ddb_resource().Table(name)

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _guess_ct(filename:str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"

def _put_to_s3(file, filename:str) -> str:
    key = f"{UPLOAD_PREFIX}{int(time.time())}-{uuid.uuid4().hex[:8]}-{os.path.basename(filename)}"
    cli = s3_client()
    file.seek(0)
    cli.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=file.read(),
        ContentType=_guess_ct(filename),
    )
    return key

def _presigned_url(key:str, expires=3600) -> str:
    try:
        return s3_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return ""

def _to_native(v):
    if isinstance(v, Decimal):
        return int(v) if v % 1 == 0 else float(v)
    return v

def _stem_to_empid(name:str) -> str | None:
    base = os.path.basename(name)
    stem, _ = os.path.splitext(base)
    m = re.search(r"(emp\d+)", stem, flags=re.IGNORECASE)
    return m.group(1) if m else None

def _get_employee(emp_id:str) -> dict | None:
    try:
        resp = ddb_table(EMPLOYEE_TABLE).get_item(Key={"EmployeeID": emp_id})
        return resp.get("Item")
    except ClientError:
        return None

def _get_violation(emp_id:str) -> dict | None:
    try:
        resp = ddb_table(VIOLATION_TABLE).get_item(Key={"EmployeeID": emp_id})
        return resp.get("Item")
    except ClientError:
        return None

def _scan_recent_violations(since_iso: str, expect_image_key: str | None = None) -> dict | None:
    """
    Fallback when we don't know EmployeeID from filename or face.
    Scan table for items with last_updated >= since and (optionally) last_image_key == key.
    NOTE: Scan is OK for small tables; for large tables you should add a GSI on last_updated.
    """
    try:
        tbl = ddb_table(VIOLATION_TABLE)
        resp = tbl.scan()
        best = None
        for it in resp.get("Items", []):
            lu = it.get("last_updated")
            if isinstance(lu, (int, float, Decimal)):
                # unlikely, but normalize
                lu_dt = datetime.fromtimestamp(_to_native(lu), tz=timezone.utc)
            else:
                try:
                    lu_dt = datetime.fromisoformat(str(lu).replace("Z", "+00:00"))
                except Exception:
                    continue
            since_dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
            if lu_dt >= since_dt:
                if expect_image_key and it.get("last_image_key") != expect_image_key:
                    continue
                # choose the most recent
                if not best or lu_dt > datetime.fromisoformat(best.get("last_updated").replace("Z", "+00:00")):
                    best = it
        return best
    except ClientError:
        return None

# =========================
#   Upload & Live Result
# =========================
st.subheader("Detect PPE from a new photo")
with st.container():
    lcol, rcol = st.columns([6,5])
    with lcol:
        up = st.file_uploader("📂 Choose an image to analyze", type=["jpg","jpeg","png","webp"])
        hint = st.caption("Tip: naming the file like **emp01_photo.jpg** helps us show results instantly.")
        do_upload = st.button("⬆️ Upload to S3 & Analyze", type="primary", disabled=(up is None))

    result_slot = st.empty()

    if do_upload and up is not None:
        start_iso = _now_iso()
        s3_key = _put_to_s3(up, up.name)
        st.success(f"Uploaded to **s3://{S3_BUCKET}/{s3_key}**. Running analysis…")
        # Try to infer the employee id from filename while we wait
        hinted_emp = _stem_to_empid(up.name) or _stem_to_empid(s3_key)

        # Poll DynamoDB for up to ~25s (Lambda + Rekognition typically < a few seconds)
        found = None
        for _ in range(25):
            time.sleep(1.0)
            # Prefer targeted lookup when we know the employee id; else fallback to scan
            if hinted_emp:
                found = _get_violation(hinted_emp)
                # ensure it’s the new record (last_image_key matches or updated now)
                if found and (found.get("last_image_key") == s3_key or
                              found.get("last_updated", "") >= start_iso):
                    break
            else:
                found = _scan_recent_violations(start_iso, expect_image_key=s3_key)
                if found:
                    break

        # Build the professional card
        if not found:
            result_slot.warning(
                "No detection record yet. The Lambda may still be running. "
                "Give it a few more seconds and click **Refresh** below."
            )
        else:
            emp_id = found.get("EmployeeID", "—")
            emp = _get_employee(emp_id) or {}
            # Prepare fields
            photo_key = found.get("last_image_key")
            photo_url = _presigned_url(photo_key) if photo_key else ""
            violations = _to_native(found.get("violations", 0))
            last_missing = found.get("last_missing", "—")
            # Employee master fields
            name = emp.get("name") or "—"
            dept = emp.get("department") or "—"
            site = emp.get("site") or "—"
            job  = emp.get("job_title") or "—"
            email= emp.get("email") or "—"
            status = emp.get("status") or "—"

            with result_slot.container():
                st.markdown("### 🧾 Detection Result")
                c1, c2 = st.columns([1,2])
                with c1:
                    if photo_url:
                        st.image(photo_url, caption="Analyzed image", width=240)
                with c2:
                    st.markdown(
                        f"""
**Employee:** `{emp_id}` — {name}  
**Department / Site:** {dept} / {site}  
**Job title:** {job}  
**Email:** {email}  
**Status:** {status}  

**Last missing PPE:** {last_missing}  
**Total violations:** **{violations}**  
**Image S3 key:** `{photo_key or '—'}`  
**Last updated:** {found.get("last_updated","—")}
                        """
                    )

st.divider()

# =========================
#   Aggregated view/edit
# =========================
@st.cache_data(ttl=30, show_spinner=False)
def _cached_load():
    # Expecting utils.data function to return a DataFrame with EmployeeID & violations
    df = load_employees_from_dynamodb()
    # Normalize expected columns if necessary
    if "EmployeeID" not in df.columns:
        # Try common alternatives defensively
        for cand in ["employee_id", "employeeID", "id"]:
            if cand in df.columns:
                df = df.rename(columns={cand: "EmployeeID"})
                break
    if "violations" not in df.columns:
        for cand in ["violation_count", "count", "Violations"]:
            if cand in df.columns:
                df = df.rename(columns={cand: "violations"})
                break
    # Make sure types are nice
    if not df.empty:
        df["EmployeeID"] = df["EmployeeID"].astype(str)
        df["violations"] = pd.to_numeric(df["violations"], errors="coerce").fillna(0).astype(int)
    return df

# ---------- Toolbar ----------
bar = st.container()
with bar:
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    query = c1.text_input("Search by EmployeeID", placeholder="e.g., emp01")
    min_v = c2.number_input("Min violations", min_value=0, value=0, step=1)
    sort_desc = c3.toggle("Sort by violations (desc)", value=True)
    refresh = c4.button("↻ Refresh")

if refresh:
    st.cache_data.clear()
    st.experimental_rerun()

df = _cached_load()

# ---------- Filter / sort ----------
view = df.copy()
if query:
    view = view[view["EmployeeID"].str.contains(query, case=False)]
view = view[view["violations"] >= min_v]

if sort_desc:
    view = view.sort_values(by="violations", ascending=False, kind="mergesort")
else:
    view = view.sort_values(by="EmployeeID", ascending=True, kind="mergesort")

view = view.reset_index(drop=True)

# ---------- KPIs ----------
left_kpi, right_kpi = st.columns(2)
left_kpi.metric("Employees in view", len(view))
right_kpi.metric("Total violations (view)", int(view["violations"].sum()) if not view.empty else 0)

st.divider()

# ---------- Editable table ----------
st.subheader("Edit & Save")
st.caption("Edit counts in the table and click **Save changes**. Only changed rows are updated.")

edited = st.data_editor(
    view,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "EmployeeID": st.column_config.TextColumn("EmployeeID", disabled=True),
        "violations": st.column_config.NumberColumn("Violations", min_value=0, step=1),
    },
    key="violations_editor",
)

save_col, _ = st.columns([1, 5])
with save_col:
    if st.button("💾 Save changes", type="primary"):
        diffs = []
        for i in range(len(edited)):
            old_row = view.iloc[i]
            new_row = edited.iloc[i]
            if int(old_row["violations"]) != int(new_row["violations"]):
                diffs.append((new_row["EmployeeID"], int(new_row["violations"])))
        if not diffs:
            st.info("No changes detected.")
        else:
            for emp_id, new_val in diffs:
                try:
                    update_employee_violations(emp_id, new_val)
                except Exception as e:
                    st.error(f"Failed to update {emp_id}: {e}")
            st.success(f"Updated {len(diffs)} record(s).")
            st.cache_data.clear()
            st.experimental_rerun()

st.divider()

# ---------- Quick add / upsert ----------
st.subheader("Add / Upsert employee record (manual override)")
with st.form("violations_upsert_form", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    new_emp_id = c1.text_input("EmployeeID", placeholder="e.g., emp07")
    init_v = c2.number_input("Initial violations", min_value=0, value=0, step=1)
    submit = c3.form_submit_button("Add / Upsert")
    if submit:
        if not new_emp_id.strip():
            st.error("EmployeeID cannot be empty.")
        else:
            try:
                upsert_employee(new_emp_id.strip(), int(init_v))
                st.success(f"Upserted '{new_emp_id}' with violations={int(init_v)}.")
                st.cache_data.clear()
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Failed to upsert employee: {e}")
