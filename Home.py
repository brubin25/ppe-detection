import streamlit as st
from pathlib import Path
from PIL import Image
import base64

# --- Page config ---
st.set_page_config(page_title="PPE Safety Suite", page_icon="🦺", layout="wide")

# --- Assets for cards (unchanged) ---
HERO_IMG = Path("images/home1.png")
CARD_IMG1 = Path("images/home1.png")
CARD_IMG2 = Path("images/home2.png")
CARD_IMG3 = Path("images/home3.png")  # Optional

# --- Slideshow images (use your new set) ---
SLIDESHOW_IMAGES = [
    Path("images/carousel1.png"),
    Path("images/carousel2.png"),
    Path("images/carousel3.png"),
]

# --- Global styles ---
st.markdown("""
<style>
.stApp {background: radial-gradient(1200px 600px at 10% 10%, #e9f3ff 0%, #f5fbff 40%, #ffffff 100%);}
footer {visibility: hidden;}

/* Center any st.image and make it look nice */
.stImage img {display:block; margin:auto; border-radius:12px;}

/* Navbar */
.navbar {display:flex; align-items:center; justify-content:space-between; padding:14px 10px;}
.nav-left, .nav-right {display:flex; gap:22px; align-items:center;}
.nav-link {font-weight:600; color:#0f172a; text-decoration:none;}
.nav-cta {background:#2563eb; color:white !important; padding:8px 14px; border-radius:10px; font-weight:600; text-decoration:none;}

/* Chips / hero text */
.chips {display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}
.chip {display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}
.hero {padding: 10px 0 20px 0;}
.kicker {letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}
.h1 {font-size:36px; line-height:1.2; font-weight:800; color:#0f172a; margin:6px 0;}
.hero-subgrid {display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:14px 0 22px 0; font-size:14px; color:#334155;}

/* Section header */
.section-kicker {display:flex; align-items:center; gap:10px; color:#2563eb; font-weight:700; font-size:12px; text-transform:uppercase; margin-top:20px;}
.badge {padding:2px 8px; background:#e0ecff; border-radius:999px; font-size:11px; color:#1e40af;}

/* Cards */
.card {display:grid; grid-template-columns:1.1fr .9fr; gap:26px; padding:22px; border:1px solid #e5e7eb; border-radius:16px; background:white;}
.card + .card {margin-top:16px;}
.card-date {font-size:11px; color:#64748b; text-transform:uppercase; margin-bottom:6px;}
.card-title {font-size:18px; font-weight:800; margin:0 0 6px 0; color:#0f172a;}
.card-text {font-size:13px; color:#334155; line-height:1.55;}
.card-cta {margin-top:12px;}
.card-block {margin-bottom:8px;}
</style>
""", unsafe_allow_html=True)

# --- NAVBAR ---
st.markdown("""
<div class="navbar">
  <div class="nav-left">
    <span style="font-weight:800; font-size:16px;">🦺 PPE Safety Suite</span>
    <a class="nav-link" href="#">Homepage</a>
    <a class="nav-link" href="#">About</a>
    <a class="nav-link" href="#">Technology</a>
  </div>
  <div class="nav-right">
    <a class="nav-cta" href="#">Contact us</a>
  </div>
</div>
""", unsafe_allow_html=True)

# --- HERO TEXT ---
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
      <div>Ensure compliance and enhance safety in industrial environments with continuous, automated oversight.</div>
    </div>
  </div>
</section>
""", unsafe_allow_html=True)

# --- Utilities for slideshow ---
def img_to_data_uri(p: Path) -> str:
    try:
        data = p.read_bytes()
    except Exception:
        return ""
    b64 = base64.b64encode(data).decode("utf-8")
    ext = p.suffix.replace(".", "").lower()
    mime = "jpeg" if ext in ("jpg", "jpeg") else "png"
    return f"data:image/{mime};base64,{b64}"

# Build a robust source list: carousel -> hero -> cards
sources = [img_to_data_uri(p) for p in SLIDESHOW_IMAGES if p.exists()]
fallbacks = [HERO_IMG, CARD_IMG1, CARD_IMG2, CARD_IMG3]
if not sources:
    sources = [img_to_data_uri(p) for p in fallbacks if p.exists()]

# Always render a full-width banner so it never collapses
if sources:
    st.components.v1.html(f"""
      <style>
        /* Full-bleed wrapper */
        #hbwrap {{
          width: 100vw;
          position: relative;
          left: 50%;
          right: 50%;
          margin-left: -50vw;
          margin-right: -50vw;
          overflow: hidden;
          box-shadow: 0 6px 18px rgba(0,0,0,.08);
        }}
        #heroBanner {{
          width: 100%;
          height: 420px;
          background-size: cover;
          background-position: center;
          background-repeat: no-repeat;
        }}
        @media (max-width: 900px) {{
          #heroBanner {{ height: 300px; }}
        }}
      </style>
      <div id="hbwrap">
        <div id="heroBanner"></div>
      </div>
      <script>
        const imgs = {sources};
        let idx = 0;
        const el = document.getElementById('heroBanner');
        function show(i) {{ el.style.backgroundImage = `url('${{imgs[i]}}')`; }}
        show(idx);
        setInterval(() => {{ idx = (idx + 1) % imgs.length; show(idx); }}, 1000);
      </script>
    """, height=430)
else:
    # Gradient fallback (no files found on the server)
    st.components.v1.html("""
      <style>
        #hbwrap {
          width: 100vw;
          position: relative;
          left: 50%;
          right: 50%;
          margin-left: -50vw;
          margin-right: -50vw;
          overflow: hidden;
          box-shadow: 0 6px 18px rgba(0,0,0,.08);
        }
        #heroBanner {
          width: 100%;
          height: 420px;
          background: linear-gradient(120deg,#e9f3ff,#dbeafe,#ffffff);
        }
        @media (max-width: 900px) { #heroBanner { height: 300px; } }
      </style>
      <div id="hbwrap"><div id="heroBanner"></div></div>
    """, height=430)

st.write("")

# --- SECTION: Updates ---
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

# --- Quick links ---
st.markdown("#### Quick links")
ql1, ql2, ql3, ql4 = st.columns(4)
with ql1:
    st.page_link("pages/01_Detect_PPE_Upload.py", label="Detect PPE (Upload)", icon="⬆️")
with ql2:
    st.page_link("pages/02_Employees_Master_List.py", label="Employees (Master List)", icon="👥")
with ql3:
    st.page_link("pages/03_Violations.py", label="Employees Violations", icon="⚠️")
with ql4:
    st.page_link("pages/04_About.py", label="About", icon="ℹ️")
