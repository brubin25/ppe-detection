# Home.py
import streamlit as st
from pathlib import Path
import base64

# Auth helpers
from auth import complete_login_if_returned, login_url

# --- Page config ---
st.set_page_config(page_title="PPE Safety Suite", page_icon="🦺", layout="wide")

# ✅ Finish OAuth callback if we just returned from Cognito (non-blocking)
complete_login_if_returned()

def _get_qp():
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()

qp = _get_qp()
if "logout" in qp:
    st.session_state.clear()
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()
    st.rerun()

# Hide sidebar if not logged in
if "id_token" not in st.session_state:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-left: 2rem; padding-right: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# Greet user
if "user" in st.session_state:
    email = st.session_state["user"].get("email", "")
    name  = st.session_state["user"].get("name", "")
    display_name = (email.split("@")[0] if email else "") or (name or "User")
else:
    display_name = None

# Assets
HERO_IMG = Path("images/home1.png")
CARD_IMG1 = Path("images/home1.png")
CARD_IMG2 = Path("images/home2.png")
CARD_IMG3 = Path("images/home3.png")

SLIDESHOW_IMAGES = [
    Path("images/carousel1.png"),
    Path("images/carousel2.png"),
    Path("images/carousel3.png"),
]
HERO_HEIGHT_PX = 420

# --- Styles ---
st.markdown(f"""
<style>
.stApp {{ background: radial-gradient(1200px 600px at 10% 10%, #e9f3ff 0%, #f5fbff 40%, #ffffff 100%); }}
footer {{ visibility: hidden; }}

.greet {{ font-size: 16px; color: #0f172a; margin: 4px 0 8px 2px; }}

.navbar {{
  display:flex; justify-content:space-between; align-items:center;
  padding:14px 10px; margin-bottom:6px; width:100%;
}}
.nav-link {{ font-weight:600; color:#0f172a; text-decoration:none; padding:6px 8px; border-radius:6px; }}
.nav-link:hover {{ background:#f1f5f9; }}

.chips {{display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}}
.chip {{display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}}

.hero {{padding:10px 0 10px 0;}}
.kicker {{letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}}
.h1 {{font-size:38px; line-height:1.15; font-weight:800; color:#0f172a; margin:6px 0;}}
.hero-subgrid {{display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:14px 0 6px 0; font-size:14px; color:#334155;}}

.section-h {{ font-weight:800; font-size:20px; color:#0f172a; margin:20px 0 10px 0; }}

.card {{display:grid; grid-template-columns:1.2fr .8fr; gap:26px; padding:22px; border:1px solid #e5e7eb;
        border-radius:16px; background:white;}}
.card + .card {{margin-top:16px;}}
.card-title {{font-size:20px; font-weight:800; margin:0 0 8px 0; color:#0f172a;}}
.card-text {{font-size:14px; color:#334155; line-height:1.6;}}
.card-img {{border-radius:12px; overflow:hidden;}}
.stButton>button, .stLinkButton>button {{border-radius:10px; padding:8px 12px; font-weight:600;}}

.full-bleed {{width:100vw; position:relative; left:50%; right:50%; margin-left:-50vw; margin-right:-50vw;}}
.hero-bleed {{
  width:100vw; height:{HERO_HEIGHT_PX}px; position:relative; overflow:hidden; border-radius:12px;
  box-shadow:0 6px 18px rgba(0,0,0,.12); background:#000;
}}
.hero-bleed img.fade {{position:absolute; inset:0; width:100%; height:100%; object-fit:cover; opacity:0; animation:fadeShow 9s infinite;}}
.hero-bleed img.fade.img2 {{ animation-delay: 3s; }}
.hero-bleed img.fade.img3 {{ animation-delay: 6s; }}
@keyframes fadeShow {{ 0%{{opacity:0}} 3%{{opacity:1}} 28%{{opacity:1}} 33%{{opacity:0}} 100%{{opacity:0}} }}
</style>
""", unsafe_allow_html=True)

# --- NAVBAR ---
nav_html = """
<div class="navbar">
  <div style="font-weight:800;">🦺 PPE Safety Suite</div>
  <div>
"""
if "id_token" in st.session_state:
    nav_html += """<a class="nav-link" href="?logout">Log out</a>"""
else:
    nav_html += f"""<a class="nav-link" href="{login_url()}">Log in</a>"""
nav_html += "</div></div>"
st.markdown(nav_html, unsafe_allow_html=True)

# Greeting
if display_name:
    st.markdown(
        f'<div class="greet">Welcome back, <strong>{display_name}</strong>.</div>',
        unsafe_allow_html=True,
    )

# --- HERO ---
st.markdown("""
<div class="chips">
  <div class="chip">⚡ Real-time</div>
  <div class="chip">☁️ 100% AWS</div>
  <div class="chip">🛡️ Compliance</div>
  <div class="chip">🤖 Rekognition PPE + Face</div>
</div>
<section class="hero">
  <div class="kicker">Workplace safety, operationalized</div>
  <div class="h1">AI-Powered PPE Compliance & Violation Tracking</div>
  <div class="hero-subgrid">
    <div><b>Why it matters</b><br/>Reduce incidents, meet regulatory requirements, and build a safety-first culture. The system shortens time-to-response and creates an auditable trail for investigations.</div>
    <div><b>What it delivers</b><br/>Automatic detection of PPE in images, identity match to your employee directory, violation logging with evidence, and alerts for repeat or critical events.</div>
  </div>
</section>
""", unsafe_allow_html=True)

# --- Slideshow ---
def img_to_data_uri(p: Path) -> str:
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = p.suffix.replace(".", "").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    return f"data:image/{mime};base64,{b64}"

slide_imgs = [p for p in SLIDESHOW_IMAGES if p.exists()]
if slide_imgs:
    srcs = [img_to_data_uri(p) for p in slide_imgs]
    while len(srcs) < 3:  # ensure 3 for animation offsets
        srcs.append(srcs[-1])
    st.markdown(f"""
<div class="full-bleed">
  <div class="hero-bleed">
    <img class="fade img1" src="{srcs[0]}" alt="slide 1"/>
    <img class="fade img2" src="{srcs[1]}" alt="slide 2"/>
    <img class="fade img3" src="{srcs[2]}" alt="slide 3"/>
  </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# --- SECTION: Practical Overview (3 cards) ---
# Card A: Why it’s important
with st.container():
    col = st.columns([1.05, .95], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Why PPE Automation Matters</div>', unsafe_allow_html=True)
        st.markdown(
            """<div class="card-text">
- **Prevent injuries** by catching missing helmets, vests, and glasses before accidents happen.<br/>
- **Prove compliance** with an immutable record of detections and actions.<br/>
- **Focus teams** with alerts on repeat offenders and locations trending the wrong way.
</div>""",
            unsafe_allow_html=True,
        )
        st.link_button("Upload a test photo →", "pages/01_Detect_PPE_Upload.py")
        st.markdown('</div>', unsafe_allow_html=True)
    with col[1]:
        if CARD_IMG1.exists():
            st.image(str(CARD_IMG1), use_container_width=True)

# Card B: Summary of what it does
with st.container():
    col = st.columns([1.05, .95], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">What the System Does</div>', unsafe_allow_html=True)
        st.markdown(
            """<div class="card-text">
- Detects PPE on each person in an image and identifies them against your **employee_master**.<br/>
- Updates **violation_master** with count, last missing items, timestamp, and image key.<br/>
- Notifies supervisors via **SNS**; escalates when thresholds are exceeded.
</div>""",
            unsafe_allow_html=True,
        )
        st.link_button("Review violations →", "pages/03_Violations.py")
        st.markdown('</div>', unsafe_allow_html=True)
    with col[1]:
        if CARD_IMG2.exists():
            st.image(str(CARD_IMG2), use_container_width=True)

# Card C: Technical overview
with st.container():
    col = st.columns([1.05, .95], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Technical Overview</div>', unsafe_allow_html=True)
        st.markdown(
            """<div class="card-text">
- **S3** triggers **Lambda** on `uploads/` and `employees/` prefixes.<br/>
- Lambda calls **Rekognition** (PPE + `search_faces_by_image`), writes to **DynamoDB** tables
  `employee_master` and `violation_master`, and publishes **SNS** alerts.<br/>
- The Streamlit app reads from **DynamoDB**, uploads images to **S3**, and presents analytics.
</div>""",
            unsafe_allow_html=True,
        )
        # Link to analytics page if present
        st.link_button("View analytics →", "pages/05_Safety_Intelligence.py")
        st.markdown('</div>', unsafe_allow_html=True)
    with col[1]:
        if CARD_IMG3.exists():
            st.image(str(CARD_IMG3), use_container_width=True)

st.write("")
