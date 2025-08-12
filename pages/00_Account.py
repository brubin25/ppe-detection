# pages/00_Account.py
import streamlit as st
from pathlib import Path
from auth import ensure_logged_in, logout_button

st.set_page_config(page_title="Account • PPE Safety Suite", page_icon="🦺", layout="wide")


# ---- Styles (matches your other pages) ----
st.markdown("""
<style>
.stApp {background: radial-gradient(1200px 600px at 10% 10%, #e9f3ff 0%, #f5fbff 40%, #ffffff 100%);}
footer {visibility: hidden;}
.navbar {display:flex; align-items:center; justify-content:space-between; padding:14px 10px;}
.nav-left, .nav-right {display:flex; gap:22px; align-items:center;}
.nav-link {font-weight:600; color:#0f172a; text-decoration:none;}
.nav-cta {background:#2563eb; color:white !important; padding:8px 14px; border-radius:10px; font-weight:600; text-decoration:none;}
.chips {display:flex; gap:14px; flex-wrap:wrap; margin:10px 0 6px 0;}
.chip {display:inline-flex; gap:8px; align-items:center; padding:6px 10px; border:1px solid #e5e7eb; border-radius:999px; font-size:13px; background:white;}
.hero {padding: 10px 0 20px 0;}
.kicker {letter-spacing:.06em; text-transform:uppercase; font-size:12px; color:#2563eb; font-weight:700;}
.h1 {font-size:36px; line-height:1.2; font-weight:800; color:#0f172a; margin:6px 0;}
.card {display:grid; grid-template-columns:1fr 1fr; gap:26px; padding:22px; border:1px solid #e5e7eb; border-radius:16px; background:white;}
.badge {padding:2px 8px; background:#e0ecff; border-radius:999px; font-size:11px; color:#1e40af;}
.profile-grid {display:grid; grid-template-columns: 1.1fr .9fr; gap:24px;}
.profile-box {background:white; border:1px solid #e5e7eb; border-radius:16px; padding:18px;}
.kv {display:grid; grid-template-columns: 140px 1fr; gap:10px; margin:4px 0;}
.kv > div:first-child {color:#64748b; font-size:13px;}
.kv > div:last-child {font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ---- NAVBAR ----
st.markdown("""
<div class="navbar">
  <div class="nav-left">
    <span style="font-weight:800; font-size:16px;">🦺 PPE Safety Suite</span>
    <a class="nav-link" href="/">Homepage</a>
    <a class="nav-link" href="/About">About</a>
    <a class="nav-link" href="/Technology">Technology</a>
  </div>
  <div class="nav-right">
    <a class="nav-cta" href="#">Contact us</a>
  </div>
</div>
""", unsafe_allow_html=True)

# ---- HERO ----
st.markdown("""
<div class="chips">
  <div class="chip">🔒 AWS Cognito Login</div>
  <div class="chip">🪪 OIDC (Hosted UI)</div>
  <div class="chip">🧩 Least-Privilege IAM</div>
</div>

<section class="hero">
  <div class="kicker">Secure Access</div>
  <div class="h1">Sign in to PPE Safety Suite</div>
</section>
""", unsafe_allow_html=True)

# ---- LOGIN ----
# If not logged-in, ensure_logged_in() renders the Cognito button and stops the script.
ensure_logged_in()

# If logged-in, show profile details & quick links
user = st.session_state.get("user", {})
st.success(f"Signed in as **{user.get('name') or user.get('email') or 'User'}**")

colL, colR = st.columns([1.1, .9], vertical_alignment="center")

with colL:
    st.markdown("""
    <div class="profile-box">
      <div style="font-weight:800; font-size:18px; margin-bottom:6px;">Your Account</div>
      <div class="kv"><div>Email</div><div>{email}</div></div>
      <div class="kv"><div>User ID (sub)</div><div style="font-family:monospace;">{sub}</div></div>
      <div class="kv"><div>Session</div><div>Active</div></div>
    </div>
    """.format(
        name=user.get("name") or "—",
        email=user.get("email") or "—",
        sub=(user.get("sub") or "—"),
    ), unsafe_allow_html=True)

    st.write("")

with colR:
    st.markdown("""
    <div class="profile-box">
      <div style="font-weight:800; font-size:18px; margin-bottom:6px;">Security Notes</div>
      <ul style="margin:0 0 0 18px;">
        <li>Authentication via Amazon Cognito Hosted UI (Authorization Code flow).</li>
        <li>All S3 uploads are private and encrypted (SSE) with least-privilege IAM.</li>
        <li>We log access via CloudTrail; TLS enforced (no public bucket access).</li>
      </ul>
    </div>
    """, unsafe_allow_html=True)

st.write("")
logout_button()
