# pages/Detect_PPE_Upload.py
import streamlit as st
import boto3
import os
import time
import uuid
import mimetypes
import json
from datetime import datetime
from boto3.dynamodb.conditions import Attr

# ✅ Auth guard
from auth import require_login

# ------------------------
# PAGE CONFIG
# ------------------------
st.set_page_config(page_title="Detect PPE (Upload)", page_icon="🦺", layout="wide")
require_login()

# ------------------------
# AWS CONFIG (secrets with env fallbacks)
# ------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION         = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

BUCKET_NAME    = "ppe-detection-input"
UPLOAD_PREFIX  = "uploads/"
EMP_TABLE      = "employee_master"
VIOL_TABLE     = "violation_master"

if not UPLOAD_PREFIX.endswith("/"):
    UPLOAD_PREFIX += "/"

# Poll (how long we wait for Lambda to write the result row)
POLL_SECONDS  = 25
POLL_INTERVAL = 2.0

# ------------------------
# CONSTANTS / STYLES
# ------------------------
PREVIEW_WIDTH_PX = 380

st.markdown("""
<style>
  .stApp { background: linear-gradient(135deg, #f5f9ff, #ffffff); }
  .upload-box, .panel {
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
  /* Bigger badge for cumulative violations */
  .big-badge {
    display:inline-block; font-weight:800; font-size:32px; color:#111827;
    padding: 6px 14px; border-radius: 12px; background:#f3f4f6;
  }
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
    return f"{UPLOAD_PREFIX}{int(time.time())}-{uuid.uuid4().hex[:8]}{ext}"

def guess_content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"

def poll_violation_result(image_key: str):
    """Poll violation_master for a row whose last_image_key == image_key."""
    ddb = ddb_resource()
    table = ddb.Table(VIOL_TABLE)

    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
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
    """Get row from employee_master."""
    if not employee_id or employee_id == "—":
        return {}
    ddb = ddb_resource()
    table = ddb.Table(EMP_TABLE)
    resp = table.get_item(Key={"EmployeeID": employee_id})
    return resp.get("Item", {})

def _read_json_from_s3(key: str):
    """Try to read a small JSON object from S3; return dict or None."""
    try:
        s3 = s3_client()
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        data = obj["Body"].read()
        return json.loads(data)
    except Exception:
        return None

def fetch_detection_json(image_key: str):
    """
    Try a couple of common locations for the Lambda-produced JSON:
    1) Same key + .json  (e.g., uploads/abc.png.json)
    2) results/<basename>.json
    """
    base = os.path.basename(image_key)
    cand1 = f"{image_key}.json"
    cand2 = f"results/{os.path.splitext(base)[0]}.json"

    for cand in (cand1, cand2):
        js = _read_json_from_s3(cand)
        if js is not None:
            return js
    return None

def build_display_result(image_key: str):
    """
    Compose a result dict for UI from DB (mandatory) + JSON (optional).
    Only shows fields that exist in DB; PPE detected / confidence come from JSON if present.
    """
    vio = poll_violation_result(image_key)
    det_json = fetch_detection_json(image_key)  # Optional

    if not vio:
        # Not found — likely compliant or still processing
        return {
            "employee_id": "—",
            "name": os.path.basename(image_key),
            "department": "—",
            "site": "—",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "Compliant or Pending",
            "violations": [],
            "ppe_detected": det_json.get("ppe_detected", []) if det_json else [],
            "model_confidence": det_json.get("model_confidence") if det_json else None,
            "image_key": image_key,
        }

    employee_id = vio.get("EmployeeID", "—")
    profile = get_employee_profile(employee_id)

    # From DB (violation_master)
    last_missing = (vio.get("last_missing") or "").strip()
    violations = [x.strip() for x in last_missing.split(",") if x.strip()]
    cumulative = int(vio.get("violations", 0))
    ts = vio.get("last_updated") or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # From optional JSON
    detected = []
    confidence = None
    if det_json:
        # Expect fields like {"ppe_detected": ["Safety Glasses", ...], "model_confidence": 95.2}
        if isinstance(det_json.get("ppe_detected"), list):
            detected = [str(x) for x in det_json["ppe_detected"]]
        confidence = det_json.get("model_confidence")

    return {
        "employee_id": employee_id,
        "name": profile.get("name") or employee_id,
        "department": profile.get("department") or "—",
        "site": profile.get("site") or "—",
        "timestamp": ts,
        "status": "Non-Compliant" if violations else "Compliant",
        "violations": violations,         # list from DB
        "ppe_detected": detected,         # list from JSON (if available)
        "model_confidence": confidence,   # from JSON (if available)
        "image_key": image_key,
        "violation_count": cumulative,    # cumulative (DB)
    }

# ------------------------
# UI
# ------------------------
st.title("🦺 Detect PPE (Upload)")
st.caption("Upload a photo and the Lambda pipeline will analyze it and update DynamoDB. Results appear on the right.")

left, right = st.columns([6, 5])
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
                st.error("❌ AWS credentials not found. Add them in `.streamlit/secrets.toml`.")
            else:
                key = unique_key(original_name)
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

                    with st.spinner("Analyzing (Lambda)…"):
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
        # ---- Top row: from DB only (no shift/zone) ----
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

        c4, c6 = st.columns([1, 1.2])
        with c4:
            st.markdown('<div class="label">Site</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("site","—")}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown('<div class="label">Timestamp</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("timestamp","—")}</div>', unsafe_allow_html=True)

        st.divider()

        # ---- Metrics ----
        total_violations_this_image = len(result.get("violations", []))
        total_detected   = len(result.get("ppe_detected", []))
        confidence       = result.get("model_confidence", None)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Violations (this image)", total_violations_this_image)
        # m2.metric("PPE Detected", total_detected)
        # m3.metric("Model Confidence", f"{confidence}%" if confidence is not None else "—")

        st.divider()

        # ---- Status & details ----
        st.markdown('<div class="label">Status</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="value">{result.get("status","—")}</div>', unsafe_allow_html=True)

        viol_list = result.get("violations", [])
        if viol_list:
            st.markdown('<div class="label" style="margin-top:10px;">Violations</div>', unsafe_allow_html=True)
            for v in viol_list:
                st.markdown(f"- {v}")
        else:
            st.markdown("No violations detected ✅")

        detected = result.get("ppe_detected", [])
        if detected:
            st.markdown('<div class="label" style="margin-top:14px;">PPE Detected</div>', unsafe_allow_html=True)
            chips = "".join([f'<span class="chip">{d}</span>' for d in detected])
            st.markdown(chips, unsafe_allow_html=True)

        # ---- BIG cumulative count (DB) ----
        if "violation_count" in result:
            st.markdown('<div class="label" style="margin-top:16px;">Cumulative Violations</div>', unsafe_allow_html=True)
            st.markdown(f'<span class="big-badge">{int(result["violation_count"])}</span>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
