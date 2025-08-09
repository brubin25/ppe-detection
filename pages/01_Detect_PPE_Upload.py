import streamlit as st
import boto3
import os
import time
import uuid
import mimetypes
from datetime import datetime
import random

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
REGION        = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

BUCKET_NAME   = "ppe-detection-input"
UPLOAD_PREFIX = "uploads/"

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
# HEADER
# ------------------------
st.title("🦺 Detect PPE (Upload)")
st.caption("Upload a photo and see the detection result appear on the right.")

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

def unique_key(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"{UPLOAD_PREFIX}{int(time.time())}-{uuid.uuid4().hex[:8]}{ext}"

def guess_content_type(filename: str) -> str:
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"

def fake_rekognition_response(filename: str):
    """
    Placeholder shape for what a Rekognition/Lambda result might return.
    Extend/replace this with your real JSON shape when you hook up to your backend.
    """
    base = os.path.splitext(os.path.basename(filename))[0] or "Unknown"
    # Randomize a little for demo feel
    all_items = ["Hard Hat", "Safety Vest", "Safety Glasses", "Gloves", "Ear Protection"]
    missing = ["No Helmet", "No Safety Vest"]  # example violations
    present = [i for i in all_items if ("No " + i.replace(" ", "")) not in missing]
    confidence = round(random.uniform(92.5, 99.5), 1)

    return {
        "employee_id": f"EMP-{random.randint(10000, 99999)}",
        "name": base.replace("_", " ").title(),
        "department": "Manufacturing",
        "site": "Plant 3",
        "shift": "Night",
        "zone": "Line A",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Non-Compliant" if missing else "Compliant",
        "violations": missing,
        "ppe_detected": ["Safety Glasses", "Gloves"],  # example present PPE
        "model_confidence": confidence,               # top-level overall score
        "image_key": filename,
    }

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
                    st.success("✅ Uploaded successfully. PPE analysis will start shortly.")
                    # Simulate/attach a detection response
                    result = fake_rekognition_response(original_name)
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
            st.markdown(f'<div class="value">{result.get("name","Unknown")}</div>', unsafe_allow_html=True)
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
            st.markdown(f'<div class="value">{result.get("shift","—")} / {result.get("zone","—")}</div>', unsafe_allow_html=True)
        with c6:
            st.markdown('<div class="label">Timestamp</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="value">{result.get("timestamp","—")}</div>', unsafe_allow_html=True)

        st.divider()

        # --------- Metrics row ---------
        total_violations = len(result.get("violations", []))
        total_detected   = len(result.get("ppe_detected", []))
        confidence       = result.get("model_confidence", None)

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Violations", total_violations)
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

    st.markdown('</div>', unsafe_allow_html=True)
