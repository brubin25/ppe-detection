import streamlit as st
from pathlib import Path
from PIL import Image
import base64

# --- Page config ---
st.set_page_config(page_title="PPE Safety Suite", page_icon="🦺", layout="wide")

# --- Assets ---
HERO_IMG = Path("images/home1.png")
CARD_IMG1 = Path("images/home1.png")
CARD_IMG2 = Path("images/home2.png")
CARD_IMG3 = Path("images/home3.png")
SLIDESHOW_IMAGES = [
    Path("images/carousel1.png"),
    Path("images/carousel2.png"),
    Path("images/carousel3.png"),
]

# --- Styles ---
st.markdown("""
<style>
.stApp {background: radial-gradient(1200px 600px at 10% 10%, #e9f3ff 0%, #f5fbff 40%, #ffffff 100%);}
footer {visibility: hidden;}
.stImage img {display:block; margin:auto; border-radius:12px;}

/* Navbar */
.navbar {display:flex; align-items:center; justify-content:space-between; padding:14px 10px;}
.nav-left, .nav-right {display:flex; gap:22px; align-items:center;}
.nav-link {font-weight:600; color:#0f172a; text-decoration:none;}
.nav-cta {background:#2563eb; color:white !important; padding:8px 14px; border-radius:10px; font-weight:600; text-decoration:none;}

/* Chips */
.chips {display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}
.chip {display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}

/* Hero */
.hero {padding: 10px 0 20px 0;}
.kicker {letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}
.h1 {font-size:36px; line-height:1.2; font-weight:800; color:#0f172a; margin:6px 0;}
.h1 span {color:#64748b; font-weight:800;}
.hero-subgrid {display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:14px 0 22px 0; font-size:14px; color:#334155;}

/* Full-width hero image */
.hero-image-wrap {
  width: 100vw;
  margin-left: -50px;  /* compensate Streamlit padding */
  margin-right: -50px;
  overflow: hidden;
}
.hero-image-wrap img {
  width: 100%;
  height: 380px;          /* adjust banner height */
  object-fit: cover;      /* fill width, crop excess */
  display: block;
}

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

# --- Navbar ---
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

# --- Chips & hero text ---
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

# --- Hero image full width ---
if HERO_IMG.exists():
    st.markdown(f"""
    <div class="hero-image-wrap">
      <img src="data:image/png;base64,{base64.b64encode(HERO_IMG.read_bytes()).decode()}">
    </div>
    """, unsafe_allow_html=True)

# --- Updates section ---
st.markdown("""
<div class="section-kicker">
  <span>AI Inspection Updates</span><span class="badge">New</span>
</div>
""", unsafe_allow_html=True)

# Example card
with st.container():
    col = st.columns([1.1, .9])
    with col[0]:
        st.markdown('<div class="card-date">March 10, 2024</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Seamless Integration: AI & AWS Rekognition for PPE</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-text card-block">Our AI integrates with AWS Rekognition for scalable PPE detection...</div>', unsafe_allow_html=True)
        st.link_button("Learn More", "pages/04_About.py")
    with col[1]:
        if CARD_IMG1.exists():
            st.image(str(CARD_IMG1), use_container_width=True)
