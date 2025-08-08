import streamlit as st

st.set_page_config(page_title="About", page_icon="ℹ️", layout="centered")

st.title("ℹ️ About")
st.markdown(
    """
This project uses **AWS Rekognition PPE**, **SNS**, and **DynamoDB** via a Lambda that is triggered by S3 uploads.  
Use the **Detect PPE (Upload)** page to push images to the S3 bucket; results flow through your existing backend.

**Stack**
- Streamlit (frontend)
- S3 (image storage & events)
- Lambda (PPE detection + face match + DynamoDB updates + SNS)
- DynamoDB (violations)
- SNS (email alerts)
"""
)