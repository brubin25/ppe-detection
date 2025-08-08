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
# AWS CONFIG — read like the reference (from st.secrets), with safe fallbacks
# ------------------------
AWS_ACCESS_KEY = st.secrets.get("AWS_ACCESS_KEY_ID", os.getenv("AWS_ACCESS_KEY_ID", ""))
AWS_SECRET_KEY = st.secrets.get("AWS_SECRET_ACCESS_KEY", os.getenv("AWS_SECRET_ACCESS_KEY", ""))
REGION        = st.secrets.get("REGION", os.getenv("AWS_REGION", "us-east-2"))

# keep your original bucket/prefix values
BUCKET_NAME   = "ppe-detection-input"
UPLOAD_PREFIX = "uploads/"

# ------------------------
# CONSTANTS
# ------------------------
# Make preview much smaller than before (~1/4 of previous full-width)
PREVIEW_MAX_WIDTH_PX = 320

# ------------------------
# STYLES
# ------------------------
st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #f5f9ff, #ffffff
