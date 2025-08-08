import streamlit as st
import boto3
import os
import time
import uuid
import mimetypes
from datetime import datetime

# ------------------------
# PAGE CONFIG
# ------------------------
st.set_page_config(page_title="Detect PPE (Upload)", page_icon="🦺", layout="wide")

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
  .result-label { color:#64748b; font-size:14px; text-transform:uppercase; letter-spacing:.04em; }
  .result-value { font-weight:700; color:#0f172a; }
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
    """Placeholder result to render the right-side panel nicely."""
    # You can replace this with a poll to your pipeline / DynamoDB / SQS etc.
    base = os.path.splitext(os.path.basename(filename))[0]
    return {
        "employee": base.replace("_", " ").title() if base else "Unknown",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Non-Compliant",
        "violations": ["No Helmet", "No Safety Vest"],
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
        # No use_column_width → no deprecation warning. Fixed width keeps it “not too big”.
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
                    # Privacy-friendly success message
                    st.success("✅ Uploaded successfully. PPE analysis will start shortly.")
                    # Placeholder “output/response” we can show at the right panel
                    result = fake_rekognition_response(original_name)
                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

with right:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.subheader("📝 Detection Result")

    if result is None:
        st.caption("The detection summary will appear here after you upload a photo.")
    else:
        # Employee + timestamp
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="result-label">Employee</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="result-value">{result["employee"]}</div>', unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="result-label">Timestamp</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="result-value">{result["timestamp"]}</div>', unsafe_allow_html=True)

        st.divider()
        # Status
        st.markdown('<div class="result-label">Status</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="result-value">{result["status"]}</div>', unsafe_allow_html=True)

        # Violations
        if result.get("violations"):
            st.markdown('<div class="result-label" style="margin-top:10px;">Violations</div>', unsafe_allow_html=True)
            for v in result["violations"]:
                st.markdown(f"- {v}")
        else:
            st.markdown("No violations detected ✅")

    st.markdown('</div>', unsafe_allow_html=True)
