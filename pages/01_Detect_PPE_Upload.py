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
# AWS CONFIG
# ------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

BUCKET_NAME = "ppe-detection-input"
UPLOAD_PREFIX = "uploads/"

# ------------------------
# CONSTANTS
# ------------------------
PREVIEW_MAX_WIDTH_PX = 320  # About 1/4 size of previous image

# ------------------------
# STYLES
# ------------------------
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #f5f9ff, #ffffff);
        }
        .upload-box {
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        .stButton button {
            background-color: #2563eb;
            color: white;
            font-weight: 600;
            border-radius: 8px;
            padding: 0.6rem 1.2rem;
        }
        .stButton button:hover {
            background-color: #1e4ed8;
        }
    </style>
""", unsafe_allow_html=True)

# ------------------------
# FUNCTIONS
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

# ------------------------
# STATE INIT
# ------------------------
if "ppe_result" not in st.session_state:
    st.session_state["ppe_result"] = None

# ------------------------
# HEADER
# ------------------------
st.title("🦺 Detect PPE (Upload)")
st.caption("Upload an image to check compliance using AWS Rekognition.")

# ------------------------
# LAYOUT
# ------------------------
col1, col2 = st.columns([1.5, 1])  # Left: Upload; Right: Results

with col1:
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
        st.image(file_bytes, caption="Preview", width=PREVIEW_MAX_WIDTH_PX)
        if st.button("⬆️ Upload to S3"):
            if not AWS_ACCESS_KEY or not AWS_SECRET_KEY:
                st.error("❌ AWS credentials not found. Please add them in `.streamlit/secrets.toml`.")
            else:
                key = unique_key(original_name)
                try:
                    with st.spinner("Uploading to S3…"):
                        s3 = s3_client()
                        s3.put_object(
                            Bucket=BUCKET_NAME,
                            Key=key,
                            Body=file_bytes,
                            ContentType=guess_content_type(original_name),
                        )
                    st.success(f"✅ Uploaded to s3://{BUCKET_NAME}/{key}")
                    st.info("Your Lambda function will now process PPE detection.")

                    # Mock response (replace with real Rekognition/Lambda call)
                    st.session_state["ppe_result"] = {
                        "employee_name": "John Doe",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "violations": ["No Helmet", "No Safety Vest"],
                        "status": "Non-Compliant"
                    }

                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.subheader("📋 Detection Result")
    if st.session_state["ppe_result"]:
        res = st.session_state["ppe_result"]
        st.write(f"**Employee:** {res['employee_name']}")
        st.write(f"**Timestamp:** {res['timestamp']}")
        st.write(f"**Status:** {res['status']}")
        if res["violations"]:
            st.write("**Violations:**")
            for v in res["violations"]:
                st.write(f"- {v}")
    else:
        st.info("No detection result yet. Upload an image to see details.")
