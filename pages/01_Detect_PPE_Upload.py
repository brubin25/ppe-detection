import streamlit as st
import boto3
import os
import time
import uuid
import mimetypes

# ------------------------
# PAGE CONFIG
# ------------------------
st.set_page_config(page_title="Detect PPE (Upload)", page_icon="🦺", layout="wide")

# ------------------------
# AWS CONFIG — read like the reference (from st.secrets), with safe fallbacks
# ------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION        = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

# keep your original bucket/prefix values
BUCKET_NAME   = "ppe-detection-input"
UPLOAD_PREFIX = "uploads/"

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
# HEADER
# ------------------------
st.title("🦺 Detect PPE (Upload)")
st.caption("Upload an image to check compliance using AWS Rekognition.")

# ------------------------
# S3 CLIENT (uses credentials loaded above)
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
    # Try to infer correct content-type; fallback to 'application/octet-stream'
    ctype, _ = mimetypes.guess_type(filename)
    return ctype or "application/octet-stream"

# ------------------------
# UPLOAD UI (unchanged logic/flow)
# ------------------------
with st.container():
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
        st.image(file_bytes, caption="Preview", use_column_width=True)
        if st.button("⬆️ Upload to S3"):
            # sanity check for creds like the reference flow expects
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
                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)
