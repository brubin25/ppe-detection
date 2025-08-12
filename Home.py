import streamlit as st
from pathlib import Path
import base64

# Auth helpers
from auth import complete_login_if_returned, login_url

# --- Page config ---
st.set_page_config(page_title="PPE Safety Suite", page_icon="🦺", layout="wide")

# ✅ Finish OAuth callback if we just returned from Cognito (non-blocking)
complete_login_if_returned()

# ✅ Handle navbar “Log out” click via a query param (keeps layout inline with links)
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

# ✅ If not logged in, hide the entire sidebar (prevents seeing other pages)
if "id_token" not in st.session_state:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] { display: none !important; }
        /* expand main area when sidebar is hidden */
        .block-container { padding-left: 2rem; padding-right: 2rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

# --- Subtle greeting (small, professional; shown only when logged in) ---
if "user" in st.session_state:
    user_email = st.session_state["user"].get("email", "")
    user_name  = st.session_state["user"].get("name", "")
    # Prefer the part before '@' from email; fall back to name; else 'User'
    display_name = (user_email.split("@")[0] if user_email else "") or (user_name or "User")
else:
    display_name = None

# --- Assets for cards (unchanged) ---
HERO_IMG = Path("images/home1.png")
CARD_IMG1 = Path("images/home1.png")
CARD_IMG2 = Path("images/home2.png")
CARD_IMG3 = Path("images/home3.png")  # Optional

# --- Slideshow images ---
SLIDESHOW_IMAGES = [
    Path("images/carousel1.png"),
    Path("images/carousel2.png"),
    Path("images/carousel3.png"),
]

HERO_HEIGHT_PX = 420

# --- Global styles ---
st.markdown(f"""
<style>
.stApp {{ background: radial-gradient(1200px 600px at 10% 10%, #e9f3ff 0%, #f5fbff 40%, #ffffff 100%); }}
footer {{ visibility: hidden; }}

/* Subtle greeting line */
.greet {{
  font-size: 16px;
  color: #0f172a;
  margin: 4px 0 8px 2px;
}}

/* NAVBAR: single row, right-aligned auth link */
.navbar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 10px;
  margin-bottom: 6px;
  width: 100%;
}}
.nav-left, .nav-right {{
  display: flex;
  align-items: center;
  gap: 22px;
  white-space: nowrap;
}}
.nav-link {{
  font-weight: 600;
  color: #0f172a;
  text-decoration: none;
  padding: 6px 8px;
  border-radius: 6px;
}}
.nav-link:hover {{
  background: #f1f5f9;
}}

.chips {{display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}}
.chip {{display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}}
.hero {{padding: 10px 0 20px 0;}}
.kicker {{letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}}
.h1 {{font-size:36px; line-height:1.2; font-weight:800; color:#0f172a; margin:6px 0;}}
.h1 span {{color:#64748b; font-weight:800;}}
.hero-subgrid {{display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:14px 0 22px 0; font-size:14px; color:#334155;}}
.section-kicker {{display:flex; align-items:center; gap:10px; color:#2563eb; font-weight:700; font-size:12px; text-transform:uppercase; margin-top:20px;}}
.badge {{padding:2px 8px; background:#e0ecff; border-radius:999px; font-size:11px; color:#1e40af;}}

.card {{display:grid; grid-template-columns:1.1fr .9fr; gap:26px; padding:22px; border:1px solid #e5e7eb; border-radius:16px; background:white;}}
.card + .card {{margin-top:16px;}}
.card-date {{font-size:11px; color:#64748b; text-transform:uppercase; margin-bottom:6px;}}
.card-title {{font-size:18px; font-weight:800; margin:0 0 6px 0; color:#0f172a;}}
.card-text {{font-size:13px; color:#334155; line-height:1.55;}}
.card-cta {{margin-top:12px;}}
.card-img {{border-radius:12px; overflow:hidden;}}
.stButton>button, .stLinkButton>button {{border-radius:10px; padding:8px 12px; font-weight:600;}}
.card-block {{margin-bottom:8px;}}

.full-bleed {{width: 100vw; position: relative; left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw;}}
.hero-bleed {{
  width: 100vw;
  height: {HERO_HEIGHT_PX}px;
  position: relative;
  overflow: hidden;
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,.12);
  background: #000;
}}
.hero-bleed img.fade {{position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: 0; animation: fadeShow 9s infinite;}}
.hero-bleed img.fade.img2 {{ animation-delay: 3s; }}
.hero-bleed img.fade.img3 {{ animation-delay: 6s; }}

@keyframes fadeShow {{
  0%   {{ opacity: 0; }}
  3%   {{ opacity: 1; }}
  28%  {{ opacity: 1; }}
  33%  {{ opacity: 0; }}
  100% {{ opacity: 0; }}
}}
</style>
""", unsafe_allow_html=True)

# --- NAVBAR (single flex container; auth control on the far right) ---
nav_html = """
<div class="navbar">
  <div class="nav-left">
    <span style="font-weight:800;">🦺 PPE Safety Suite</span>
  </div>
  <div class="nav-right">
"""
if "id_token" in st.session_state:
    # Log out via query param (keeps same size & row as other nav links)
    nav_html += """<a class="nav-link" href="?logout">Log out</a>"""
else:
    nav_html += f"""<a class="nav-link" href="{login_url()}">Log in</a>"""
nav_html += "</div></div>"
st.markdown(nav_html, unsafe_allow_html=True)

# --- Compact greeting under navbar (only when logged in) ---
if display_name:
    st.markdown(
        f'<div class="greet">Welcome back to PPE Safety Suite, <strong>{display_name}</strong>.</div>',
        unsafe_allow_html=True,
    )

# --- HERO TEXT / CHIPS (unchanged) ---
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
      <div>Our cutting-edge AI leverages AWS Rekognition for precise and reliable PPE detection.</div>
    </div>
    <div>
      <b>Real-time Monitoring</b>
      <div>Ensure compliance and enhance safety with continuous, automated oversight.</div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)

# --- Slideshow (unchanged) ---
def img_to_data_uri(p: Path) -> str:
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = p.suffix.replace(".", "").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    return f"data:image/{mime};base64,{b64}"

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

# --- SECTION: Updates (unchanged) ---
st.markdown("""
<div class="section-kicker">
  <span>AI Inspection Updates</span><span class="badge">New</span>
</div>
""", unsafe_allow_html=True)

# Card 1
with st.container():
    col = st.columns([1.1, .9], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card-date">March 10, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Seamless Integration: AI & AWS Rekognition for PPE</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-text card-block">'
            'Discover how our AI integrates effortlessly with AWS Rekognition to deliver '
            'robust and accurate PPE detection at scale. The pipeline supports batch and real-time ingestion, '
            'automatically routes events to your preferred queues, and enriches them with site, shift, and zone metadata.'
            '</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="card-text card-block">'
            'Admins can review detections with side-by-side evidence frames, export annotated PDFs for audits, '
            'and sync results to your safety system of record. Zero-downtime deploys and IaC modules keep operations simple.'
            '</div>', unsafe_allow_html=True
        )
        st.link_button("Learn More", "pages/04_About.py")
    with col[1]:
        if CARD_IMG1.exists():
            st.image(str(CARD_IMG1), use_container_width=True)

# Card 2
with st.container():
    col = st.columns([1.1, .9], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card-date">February 28, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Real-Time PPE Detection: A New Era of Safety</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-text card-block">'
            'Our vision models run on streams and images to identify helmets, vests, goggles, and masks—'
            'even in low light and busy backgrounds. Latency is typically under a second, with configurable '
            'thresholds to balance sensitivity and precision.'
            '</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="card-text card-block">'
            'When a violation is detected, alerts are pushed to supervisors via email, SMS, or Slack '
            'with cropped evidence and location context. Webhooks make it easy to trigger lockout/tagout or badge rules.'
            '</div>', unsafe_allow_html=True
        )
        st.link_button("View Demo", "pages/01_Detect_PPE_Upload.py")
    with col[1]:
        if CARD_IMG2.exists():
            st.image(str(CARD_IMG2), use_container_width=True)

# Card 3
with st.container():
    col = st.columns([1.1, .9], vertical_alignment="center")
    with col[0]:
        st.markdown('<div class="card-date">January 15, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Optimizing Workplace Safety with AI-Driven Insights</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="card-text card-block">'
            'Dashboards summarize trends by site, line, contractor, and shift so leaders can target training where '
            'it matters most. Drill-downs show repeat hotspots, top violation types, and mean-time-to-resolution.'
            '</div>', unsafe_allow_html=True
        )
        st.markdown(
            '<div class="card-text card-block">'
            'Exports feed your BI stack, while scheduled reports keep supervisors in the loop. '
            'All insights are privacy-aware and auditable, designed to meet enterprise governance standards.'
            '</div>', unsafe_allow_html=True
        )
        st.link_button("Get Started", "pages/02_Employees_Master_List.py")
    with col[1]:
        if CARD_IMG3.exists():
            st.image(str(CARD_IMG3), use_container_width=True)

st.write("")
