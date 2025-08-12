import streamlit as st
from datetime import datetime

st.set_page_config(page_title="About", page_icon="ℹ️", layout="centered")

# ---------- Minimal styling for a cleaner, professional look ----------
st.markdown(
    """
    <style>
      .about-card {
        background: #ffffff;
        padding: 24px 28px;
        border-radius: 14px;
        border: 1px solid #eef2f7;
        box-shadow: 0 6px 18px rgba(16, 24, 40, 0.04);
      }
      .kicker {
        color: #475569;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: .06em;
        margin-bottom: 4px;
      }
      .headline {
        font-size: 32px;
        line-height: 1.15;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 8px 0;
      }
      .sub {
        color: #334155;
        font-size: 16px;
        margin-bottom: 14px;
      }
      .pill {
        display:inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background: #f8fafc;
        font-size: 12px;
        color: #0f172a;
        margin: 4px 6px 0 0;
      }
      .section-h {
        font-weight: 700;
        font-size: 18px;
        margin: 16px 0 8px 0;
        color: #0f172a;
      }
      ul.about-list { margin-top: 6px; }
      ul.about-list li { margin-bottom: 6px; }
      .muted { color:#64748b; font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Hero ----------
with st.container():
    left, right = st.columns([5, 3], gap="large")
    with left:
        st.markdown('<div class="about-card">', unsafe_allow_html=True)
        st.markdown('<div class="kicker">About this project</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="headline">AI-assisted PPE Compliance, built on AWS</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sub">This application detects Personal Protective Equipment '
            '(PPE) in uploaded images, identifies workers via face matching, '
            'and tracks violations in real time—using a fully serverless, cloud-native architecture.</div>',
            unsafe_allow_html=True,
        )

        st.markdown("**Key capabilities**")
        st.markdown(
            """
            - Real-time PPE detection and person identification  
            - Automatic alerts via SNS for violations (including critical thresholds)  
            - Persistent violation tracking in DynamoDB with audit details  
            - Streamlit front-end for uploads, reporting, and manual edits
            """
        )

        st.markdown("**Tech stack**")
        st.markdown(
            """
            <span class="pill">Streamlit (frontend)</span>
            <span class="pill">Amazon S3 (images & events)</span>
            <span class="pill">AWS Lambda (serverless)</span>
            <span class="pill">Amazon Rekognition (PPE + face)</span>
            <span class="pill">Amazon DynamoDB (violations & employees)</span>
            <span class="pill">Amazon SNS (email alerts)</span>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.caption("Add a photo or logo (optional)")
        logo = st.file_uploader("Upload image", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
        if logo:
            st.image(logo, use_column_width=True, caption="Project Image")

# ---------- Architecture & Flow ----------
st.markdown('<div class="section-h">Architecture Overview</div>', unsafe_allow_html=True)
st.markdown(
    """
    - **Streamlit** UI uploads an image to **S3** (under `uploads/`)  
    - **S3 event** triggers **AWS Lambda**  
    - Lambda calls **Amazon Rekognition** for PPE detection and face matching  
    - Lambda verifies the worker in **employee_master**, updates **violation_master**, and sends **SNS** alerts  
    - The Streamlit app polls **DynamoDB** and presents structured results
    """
)

st.markdown('<div class="section-h">Data Flow</div>', unsafe_allow_html=True)
st.markdown(
    """
    1. **Upload** → Image lands in `s3://…/uploads/`  
    2. **Detect** → Lambda runs PPE + face match (Rekognition)  
    3. **Track** → Write/Increment to `violation_master` with last_missing, last_updated, and image key  
    4. **Alert** → SNS sends email alerts for violations (and critical thresholds)  
    5. **Review** → Streamlit displays results and allows authorized edits
    """
)

# ---------- Security & Governance ----------
with st.expander("🔐 Security & Governance"):
    st.markdown(
        """
        - **Least privilege IAM**: separate read/write policies for app users and backend Lambda  
        - **Private S3 objects** with presigned access when needed  
        - **Serverless** services (Lambda, DynamoDB) reduce patching overhead  
        - **PII awareness**: face images and identifiers remain in your AWS account  
        - **Auditability**: `violation_master` includes timestamps and last image keys
        """
    )

# ---------- Operations ----------
with st.expander("🛠 Operations & Maintenance"):
    st.markdown(
        """
        - **Scaling**: serverless primitives autoscale with load  
        - **Costs**: pay-as-you-go (S3 storage/requests, Rekognition calls, Lambda GB-seconds, DynamoDB RCUs/WCUs, SNS)  
        - **Monitoring**: use CloudWatch logs/metrics and optional alarms for Lambda/SNS/DynamoDB  
        - **Extensibility**: add a GSI for advanced queries (e.g., last_updated) or a dashboard (QuickSight/Athena)
        """
    )

# ---------- How to Use ----------
st.markdown('<div class="section-h">How to Use</div>', unsafe_allow_html=True)
st.markdown(
    """
    1) Go to **Detect PPE Upload** → upload a photo  
    2) Wait briefly while Lambda processes the image  
    3) Review the **Detection Result** panel  
    4) See aggregated counts under **Violations**; edit counts where permitted
    """
)

# ---------- Footer ----------
st.markdown(
    f"<div class='muted'>Build time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')} UTC</div>",
    unsafe_allow_html=True,
)
