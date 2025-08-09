import streamlit as st
from pathlib import Path
import base64
from auth import complete_login_if_returned, login_url, logout_button

# --- Page config ---
st.set_page_config(page_title="PPE Safety Suite", page_icon="🦺", layout="wide")

# Handle OAuth callback if returning from login
complete_login_if_returned()

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

# --- Assets ---
HERO_HEIGHT_PX = 420
SLIDESHOW_IMAGES = [
    Path("images/carousel1.png"),
    Path("images/carousel2.png"),
    Path("images/carousel3.png"),
]
CARD_IMG1 = Path("images/home1.png")
CARD_IMG2 = Path("images/home2.png")
CARD_IMG3 = Path("images/home3.png")

# --- Global CSS ---
st.markdown(f"""
<style>
.stApp {{
  background: radial-gradient(1200px 600px at 10% 10%, #e9f3ff 0%, #f5fbff 40%, #ffffff 100%);
}}
footer {{ visibility: hidden; }}

.navbar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 10px;
  margin-bottom: 6px;
}}
.nav-left, .nav-right {{
  display: flex;
  align-items: center;
  gap: 22px;
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

.greet {{
  font-size: 16px;
  color: #0f172a;
  margin: 4px 0 8px 2px;
}}

.chips {{display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}}
.chip {{display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}}

.hero {{padding: 10px 0 20px 0;}}
.kicker {{letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}}
.h1 {{font-size:36px; line-height:1.2; font-weight:800; color:#0f172a; margin:6px 0;}}
.hero-subgrid {{display:grid; grid-template-columns:1fr 1fr; gap:24px; margin:14px 0 22px 0; font-size:14px; color:#334155;}}

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
  0% {{ opacity: 0; }}
  3% {{ opacity: 1; }}
  28% {{ opacity: 1; }}
  33% {{ opacity: 0; }}
  100% {{ opacity: 0; }}
}}
</style>
""", unsafe_allow_html=True)

# --- Navbar ---
st.markdown('<div class="navbar">', unsafe_allow_html=True)

# Left nav items
st.markdown(
    """
    <div class="nav-left">
      <span style="font-weight:800;">🦺 PPE Safety Suite</span>
      <a class="nav-link" href="#">Homepage</a>
      <a class="nav-link" href="#">About</a>
      <a class="nav-link" href="#">Technology</a>
    </div>
    """,
    unsafe_allow_html=True
)

# Right nav item — login/logout
if "id_token" in st.session_state:
    # Make logout look like a nav link
    st.markdown(
        f"""
        <div class="nav-right">
            <form action="?logout" method="post">
                <button type="submit" class="nav-link" style="border:none;background:none;cursor:pointer;">Log out</button>
            </form>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.markdown(
        f"""
        <div class="nav-right">
            <a class="nav-link" href="{login_url()}">Log in</a>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown('</div>', unsafe_allow_html=True)

# --- Greeting ---
if "user" in st.session_state:
    user_email = st.session_state["user"].get("email", "")
    user_name = st.session_state["user"].get("name", "")
    display_name = user_email.split("@")[0] if user_email else (user_name or "User")
    st.markdown(f'<div class="greet">Welcome back to PPE Safety Suite, <strong>{display_name}</strong>.</div>', unsafe_allow_html=True)

# --- Hero content ---
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

# --- Slideshow ---
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
