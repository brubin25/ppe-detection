# Home.py (or app.py if this is the main page)
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
logout_clicked = ("logout" in qp)
if logout_clicked:
    st.session_state.clear()
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()
    st.rerun()

# ✅ Hide sidebar when logged out
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

# Greeting
if "user" in st.session_state:
    user_email = st.session_state["user"].get("email", "")
    user_name  = st.session_state["user"].get("name", "")
    display_name = (user_email.split("@")[0] if user_email else "") or (user_name or "User")
else:
    display_name = None

# --- Assets ---
HERO_IMG   = Path("images/home1.png")
CARD_IMG1  = Path("images/home1.png")
CARD_IMG2  = Path("images/home2.png")
CARD_IMG3  = Path("images/home3.png")

SLIDESHOW_IMAGES = [
    Path("images/carousel1.png"),
    Path("images/carousel2.png"),
    Path("images/carousel3.png"),
]
HERO_HEIGHT_PX = 420

# --- Helpers ---
def img_to_data_uri(p: Path) -> str:
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = p.suffix.replace(".", "").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    return f"data:image/{mime};base64,{b64}"

# --- Global styles (smaller card images & tight spacing) ---
st.markdown(f"""
<style>
/* App background with PPE-themed warm gradient + subtle radial glow */
.stApp {{
  background:
    radial-gradient(
      circle at 15% 20%,
      rgba(255, 127, 39, 0.08) 0%,
      transparent 40%
    ),
    linear-gradient(
      135deg,
      #fff7ed 0%,   /* light PPE orange */
      #ffedd5 40%,  /* soft peach */
      #ffffff 100%  /* fade to white for readability */
    );
}}
footer {{ visibility: hidden; }}

/* Sidebar background to match theme */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
}}

.greet {{ font-size: 16px; color: #0f172a; margin: 4px 0 8px 2px; }}

.navbar {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 10px; margin-bottom: 6px; width: 100%; }}
.nav-left, .nav-right {{ display: flex; align-items: center; gap: 22px; white-space: nowrap; }}
.nav-link {{ font-weight: 600; color: #0f172a; text-decoration: none; padding: 6px 8px; border-radius: 6px; }}
.nav-link:hover {{ background: #f1f5f9; }}

.chips {{display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}}
.chip {{display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}}
.hero {{padding: 10px 0 20px 0;}}
.kicker {{letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}}
.h1 {{font-size:36px; line-height:1.2; font-weight:800; color:#0f172a; margin:6px 0;}}
.hero-subgrid {{display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:14px 0 22px 0; font-size:14px; color:#334155;}}

.section-kicker {{display:flex; align-items:center; gap:10px; color:#2563eb; font-weight:700; font-size:12px; text-transform:uppercase; margin-top:20px;}}

.card {{display:grid; grid-template-columns:1.1fr .9fr; gap:26px; padding:22px; border:1px solid #e5e7eb; border-radius:16px; background:white;}}
.card + .card {{margin-top:16px;}}
.card-date {{font-size:11px; color:#64748b; text-transform:uppercase; margin-bottom:6px;}}
.card-title {{font-size:18px; font-weight:800; margin:0 0 6px 0; color:#0f172a;}}
.card-text {{font-size:13px; color:#334155; line-height:1.65;}}
.card-cta {{margin-top:12px;}}

.card-img-sm img {{
  width: 100%;
  max-height: 250px;     /* compact, consistent */
  object-fit: cover;
  border-radius: 12px;
  display: block;
  margin-top: 6px;
}}

.full-bleed {{width: 100vw; position: relative; left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw;}}
.hero-bleed {{
  width: 100vw; height: {HERO_HEIGHT_PX}px; position: relative; overflow: hidden;
  border-radius: 12px; box-shadow: 0 6px 18px rgba(0,0,0,.12); background: #000;
}}
.hero-bleed img.fade {{position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0; animation: fadeShow 9s infinite;}}
.hero-bleed img.fade.img2 {{ animation-delay: 3s; }}
.hero-bleed img.fade.img3 {{ animation-delay: 6s; }}
@keyframes fadeShow {{ 0%{{opacity:0}} 3%{{opacity:1}} 28%{{opacity:1}} 33%{{opacity:0}} 100%{{opacity:0}} }}
</style>
""", unsafe_allow_html=True)

# --- NAVBAR ---
nav_html = """
<div class="navbar">
  <div class="nav-left">
    <span style="font-weight:800;">🦺 PPE Safety Suite</span>
  </div>
  <div class="nav-right">
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
        f'<div class="greet">Welcome back to PPE Safety Suite, <strong>{display_name}</strong>.</div>',
        unsafe_allow_html=True,
    )

# --- HERO TEXT / CHIPS ---
st.markdown("""
<div class="chips">
  <div class="chip">⚡ Real-time Processing</div>
  <div class="chip">☁️ AWS Cloud Integration</div>
  <div class="chip">🛡️ Enhanced Workplace Safety</div>
  <div class="chip">🤖 AI/ML Powered</div>
</div>

<section class="hero">
  <div class="kicker">Revolutionizing Safety with</div>
  <div class="h1">AI-Powered PPE Detection</div>
  <div class="hero-subgrid">
    <div>
      <b>Advanced AI Solutions</b>
      <div>Our Rekognition-based models identify missing helmets, vests, and eyewear with production-grade accuracy. The pipeline is tuned for real-world factory conditions and handles glare, motion blur, and cluttered backgrounds. It’s continuously tested against representative images to avoid regressions. As accuracy improves, you benefit automatically—no manual updates required.</div>
    </div>
    <div>
      <b>Real-time Monitoring</b>
      <div>Each upload triggers automated analysis, alerts, and a tamper-evident record for compliance. Supervisors receive concise notifications with evidence crops so they can act quickly. All outcomes are written to DynamoDB with timestamps for audit and trend analysis. The result is fewer blind spots and faster intervention when standards slip.</div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)

# --- Slideshow (kept) ---
slide_imgs = [p for p in SLIDESHOW_IMAGES if p.exists()]
if slide_imgs:
    sources = [img_to_data_uri(p) for p in slide_imgs]
    while len(sources) < 3:
        sources.append(sources[-1])
    st.markdown(f"""
<div class="full-bleed">
  <div class="hero-bleed">
    <img class="fade img1" src="{sources[0]}" alt="slide 1"/>
    <img class="fade img2" src="{sources[1]}" alt="slide 2"/>
    <img class="fade img3" src="{sources[2]}" alt="slide 3"/>
  </div>
</div>
""", unsafe_allow_html=True)
else:
    st.info("Add images to `images/carousel1.png`, `images/carousel2.png`, `images/carousel3.png` to drive the slideshow.")

st.write("")

# --- WHY PPE AUTOMATION MATTERS (professional sentences) ---
st.markdown("### Why PPE Automation Matters")
st.markdown(
    """
- **Prevent injuries.** Automated checks catch missing PPE before incidents occur.  
- **Prove compliance.** Every detection is logged with time, image, and outcome to create an auditable record.  
- **Focus teams.** Alerts surface repeat offenders and rising hotspots so supervisors spend time where it matters.  
    """
)

# --- Updates / Cards (smaller images; single CTA to Detect PPE Upload) ---
st.markdown("""
<div class="section-kicker">
  <span>AI Inspection Updates</span>
</div>
""", unsafe_allow_html=True)

# Card 1
with st.container():
    col = st.columns([1.1, .9], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card-date">March 10, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Seamless Integration: Rekognition + Lambda + DynamoDB</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-text">'
            'Uploads to S3 automatically trigger PPE detection, face matching, and violation updates—no manual steps required. '
            'A Lambda function orchestrates the workflow, writing results to DynamoDB and pushing alerts through SNS. '
            'The pipeline is fully serverless, highly resilient, and scales down to zero when idle to minimize cost. '
            'Configuration is driven by environment variables and IaC, so deployments are repeatable and auditable. '
            'Security best practices are followed with least-privilege policies and private buckets by default.'
            '</div>',
            unsafe_allow_html=True
        )
        # Single primary CTA → Detect PPE Upload
        st.link_button("Upload Photo Test", "pages/01_Detect_PPE_Upload.py")
    with col[1]:
        if CARD_IMG1.exists():
            st.markdown(f'<div class="card-img-sm"><img src="{img_to_data_uri(CARD_IMG1)}"/></div>', unsafe_allow_html=True)

# Card 2
with st.container():
    col = st.columns([1.1, .9], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card-date">February 28, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Real-Time PPE Detection in Tough Conditions</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-text">'
            'Low light, reflective surfaces, and motion are handled with tuned thresholds and robust pre-processing. '
            'Detections include evidence crops so supervisors can verify issues without downloading full images. '
            'Confidence scores are recorded to support quality reviews and continuous improvement. '
            'Latency is typically under a second from upload to alert in regional deployments. '
            'The system is designed to maintain performance even when image quality varies throughout a shift.'
            '</div>',
            unsafe_allow_html=True
        )
    with col[1]:
        if CARD_IMG2.exists():
            st.markdown(f'<div class="card-img-sm"><img src="{img_to_data_uri(CARD_IMG2)}"/></div>', unsafe_allow_html=True)

# Card 3
with st.container():
    col = st.columns([1.1, .9], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card-date">January 15, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Actionable Insights for Supervisors</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-text">'
            'Aggregations by department, site, and line reveal where risks concentrate so training can be targeted. '
            'Cumulative violation counts highlight repeat offenders and support coaching conversations. '
            'Timestamps and image keys provide an auditable trail for investigations and compliance reporting. '
            'Supervisors can adjust thresholds and escalation rules to match local safety policies. '
            'All data remains within your AWS account to simplify governance and data privacy.'
            '</div>',
            unsafe_allow_html=True
        )
    with col[1]:
        if CARD_IMG3.exists():
            st.markdown(f'<div class="card-img-sm"><img src="{img_to_data_uri(CARD_IMG3)}"/></div>', unsafe_allow_html=True)
