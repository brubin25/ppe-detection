import streamlit as st
import boto3
import os
import time
import uuid
import mimetypes
from datetime import datetime
from boto3.dynamodb.conditions import Attr

# ✅ Auth guard (kept minimal; doesn’t change your logic)
from auth import require_login

# ------------------------
# PAGE CONFIG
# ------------------------
st.set_page_config(page_title="Detect PPE (Upload)", page_icon="🦺", layout="wide")

# Require login for this page (homepage can remain public)
require_login()

# ------------------------
# AWS CONFIG — like your reference (secrets with env fallbacks)
# ------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

BUCKET_NAME          = "ppe-detection-input"
UPLOAD_PREFIX        = "uploads/"          # all uploads go under uploads/
EMP_TABLE            = "employee_master"   # master employees
VIOL_TABLE           = "violation_master"  # aggregated violations

# Normalize to ensure single trailing slash (safety guard; doesn't change behavior)
if not UPLOAD_PREFIX.endswith("/"):
    UPLOAD_PREFIX = UPLOAD_PREFIX + "/"

# Poll settings (how long we wait for Lambda to write the result)
POLL_SECONDS  = 25
POLL_INTERVAL = 2.0

# ------------------------
# CONSTANTS
# ------------------------
PREVIEW_WIDTH_PX = 380  # ~¼ of a wide monitor

# ------------------------
# STYLES
# ------------------------
st.markdown("""
<style>
  .stApp { background: linear-gradient(135deg, #f5f9ff, #ffffff); }
  .upload-box {
    background: white; padding: 20px; border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  }
  .panel {
    background: white; padding: 20px; border-radius: 15px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  }
  .stButton button {
    background-color: #2563eb; color: white; font-weight: 600;
    border-radius: 8px; padding: 0.6rem 1.2rem;
  }
  .stButton button:hover { background-color: #1e4ed8; }
  .label { color:#64748b; font-size:13px; text-transform:uppercase; letter-spacing:.04em; }
  .value { font-weight:700; color:#0f172a; font-size:16px; }
  .chip {
    display:inline-block; padding:4px 10px; border-radius:999px;
    border:1px solid #e5e7eb; margin-right:6px; margin-bottom:6px; background:#fff;
    font-size:12px; color:#0f172a;
  }
</style>
""", unsafe_allow_html=True)

# ------------------------
# HELPERS
# ------------------------
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

def unique_key(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    # Build a key under uploads/: uploads/<timestamp>-<uuid>.<ext>
    return f"{UPLOAD_PREFIX}{int(time.time())}-{uuid.uuid4().hex[:8]}{ext}"

def guess_content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"

def poll_violation_result(image_key: str):
    """
    Poll violation_master for a row where last_image_key == image_key.
    Returns the violation item (dict) or None if not found in time.
    """
    ddb = ddb_resource()
    table = ddb.Table(VIOL_TABLE)

    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
        # SCAN with filter on last_image_key (simple but fine for modest tables)
        resp = table.scan(
            FilterExpression=Attr("last_image_key").eq(image_key),
            ProjectionExpression="#eid, violations, last_missing, last_updated, last_image_key",
            ExpressionAttributeNames={"#eid": "EmployeeID"},
        )
        items = resp.get("Items", [])
        if items:
            return items[0]
        time.sleep(POLL_INTERVAL)
    return None

def get_employee_profile(employee_id: str):
    """
    Get employee profile from employee_master by EmployeeID.
    """
    ddb = ddb_resource()
    table = ddb.Table(EMP_TABLE)
    resp = table.get_item(Key={"EmployeeID": employee_id})
    return resp.get("Item", {})

def build_display_result(image_key: str):
    """
    Compose a result dict for UI using violation_master + employee_master.
    If no violation row arrives (e.g., person compliant or detection failed), return a
    "compliant" placeholder with the key so users know it uploaded fine.
    """
    vio = poll_violation_result(image_key)

    if not vio:
        # Not found—either (1) compliant (Lambda sends a compliance SNS but no increment),
        # or (2) still processing. We’ll show a neutral card.
        return {
            "employee_id": "—",
            "name": os.path.basename(image_key),
            "department": "—",
            "site": "—",
            "shift": None,
            "zone": None,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Compliant or Pending",
            "violations": [],
            "ppe_detected": [],
            "model_confidence": None,
            "image_key": image_key,
        }

    employee_id = vio.get("EmployeeID", "—")
    profile = get_employee_profile(employee_id)

    # violations list comes from "last_missing" stored by Lambda (comma-separated)
    last_missing = vio.get("last_missing") or ""
    violations = [x.strip() for x in last_missing.split(",") if x.strip()]

    return {
        "employee_id": employee_id,
        "name": profile.get("name") or employee_id,
        "department": profile.get("department") or "—",
        "site": profile.get("site") or "—",
        "shift": None,            # not stored; leave None/— in UI
        "zone": None,             # not stored; leave None/— in UI
        "timestamp": vio.get("last_updated") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Non-Compliant" if violations else "Compliant",
        "violations": violations,
        "ppe_detected": [],       # if you store "last_detected" in Lambda, read it here
        "model_confidence": None, # not stored; can be added to Lambda if needed
        "image_key": image_key,
        "violation_count": int(vio.get("violations", 0)),
    }

# ------------------------
# HEADER
# ------------------------
st.title("🦺 Detect PPE (Upload)")
st.caption("Upload a photo and see the detection result appear on the right (powered by Lambda + DynamoDB).")

# ------------------------
# LAYOUT: LEFT (upload + preview) | RIGHT (result)
# ------------------------
left, right = st.columns([6, 5])

# A mutable placeholder for the result dictionary
result = None

with left:
    st.markdown('<div class="upload-box">', unsafe_allow_html=True)

    uploaded_file = st.file_uploader("📂 Choose an image", type=["jpg", "jpeg", "png"])
    use_camera = st.toggle("📸 Use camera")
    camera_img = st.camera_input("Take a photo") if use_camera else None

    file_bytes = None
    original_name = None

    if camera_img is not None:
        file_bytes = camera_img.getvalue()
        original_name = "camera_capture.png"
    elif uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        original_name = uploaded_file.name

    if file_bytes:
        st.markdown("**Preview**")
        st.image(file_bytes, caption=None, width=PREVIEW_WIDTH_PX)

        if st.button("⬆️ Upload to S3", type="primary"):
            if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
                st.error("❌ AWS credentials not found. Please add them in `.streamlit/secrets.toml`.")
            else:
                key = unique_key(original_name)  # ← uploads/<timestamp>-<uuid>.<ext>
                try:
                    with st.spinner("Uploading…"):
                        s3 = s3_client()
                        s3.put_object(
                            Bucket=BUCKET_NAME,
                            Key=key,
                            Body=file_bytes,
                            ContentType=guess_content_type(original_name),
                        )
                    st.success("✅ Uploaded successfully. Waiting for detection result…")

                    # Poll DynamoDB for the record written by Lambda
                    with st.spinner("Analyzing (Lambda) …"):
                        result = build_display_result(key)

                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("🧾 Detection Result")

    if result is None:
        st.caption("The detection summary will appear here after you upload a photo.")
    else:
        # --------- Top row: Identity ---------
        c1, c2, c3 = st.columns([1.2, 1, 1])
        with c1:
            st.markdown('<div class="label">Employee Name</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("name","—")}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="label">Employee ID</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("employee_id","—")}</div>', unsafe_allow_html=True)
        with c3:
            st.markdown('<div class="label">Department</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("department","—")}</div>', unsafe_allow_html=True)

        # --------- 2nd row: Location/Time ---------
        c4, c5, c6 = st.columns([1, 0.8, 1.2])
        with c4:
            st.markdown('<div class="label">Site</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("site","—")}</div>', unsafe_allow_html=True)
        with c5:
            st.markdown('<div class="label">Shift / Zone</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("shift","—") or "—"} / {result.get("zone","—") or "—"}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown('<div class="label">Timestamp</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("timestamp","—")}</div>', unsafe_allow_html=True)

        st.divider()

        # --------- Metrics row ---------
        total_violations = len(result.get("violations", []))
        total_detected   = len(result.get("ppe_detected", []))
        confidence       = result.get("model_confidence", None)

        m1, m2, m3 = st.columns(3)
        # If Lambda writes cumulative count, show it; else show this image's count (=len list)
        m1.metric("Total Violations (this image)", total_violations)
        m2.metric("PPE Detected", total_detected)
        if confidence is not None:
            m3.metric("Model Confidence", f"{confidence}%")
        else:
            m3.metric("Model Confidence", "—")

        st.divider()

        # --------- Status & details ---------
        st.markdown('<div class="label">Status</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="value">{result.get("status","—")}</div>', unsafe_allow_html=True)

        # Violations list
        violations = result.get("violations", [])
        if violations:
            st.markdown('<div class="label" style="margin-top:10px;">Violations</div>', unsafe_allow_html=True)
            for v in violations:
                st.markdown(f"- {v}")
        else:
            st.markdown("No violations detected ✅")

        # PPE detected (chips)
        detected = result.get("ppe_detected", [])
        if detected:
            st.markdown('<div class="label" style="margin-top:14px;">PPE Detected</div>', unsafe_allow_html=True)
            chips = "".join([f'<span class="chip">{d}</span>' for d in detected])
            st.markdown(chips, unsafe_allow_html=True)

        # Show cumulative count if present
        if "violation_count" in result:
            st.markdown('<div class="label" style="margin-top:14px;">Cumulative Violations</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result["violation_count"]}</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
