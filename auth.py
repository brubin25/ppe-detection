import requests
from urllib.parse import urlencode
from jose import jwt, jwk  # jwk kept for future extensions
import streamlit as st

# ---- Config (from secrets) ----
COGNITO_DOMAIN   = st.secrets["COGNITO_DOMAIN"]          # e.g. https://<your>.auth.<region>.amazoncognito.com
COGNITO_CLIENTID = st.secrets["COGNITO_APP_CLIENT_ID"]   # App client (no secret)
COGNITO_POOL_ID  = st.secrets["COGNITO_USER_POOL_ID"]    # e.g. us-east-2_abc123
REGION           = st.secrets.get("REGION", "us-east-2")
REDIRECT_URI     = st.secrets["COGNITO_REDIRECT_URI"]    # your Streamlit app URL

# ---------------------------
# Utilities
# ---------------------------
def _get_query_params():
    """Handle Streamlit pre/post-1.31 query param APIs."""
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()

# ---------------------------
# Hosted UI URLs & JWKS
# ---------------------------
def login_url(state="state123"):
    params = {
        "client_id": COGNITO_CLIENTID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }
    return f"{COGNITO_DOMAIN}/oauth2/authorize?{urlencode(params)}"

def _jwks():
    url = f"https://cognito-idp.{REGION}.amazonaws.com/{COGNITO_POOL_ID}/.well-known/jwks.json"
    return requests.get(url, timeout=15).json()

# ---------------------------
# Token exchange & validation
# ---------------------------
def exchange_code_for_tokens(code: str):
    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": COGNITO_CLIENTID,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(token_url, data=data, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()  # { id_token, access_token, ... }

def validate_id_token(id_token: str):
    jwks = _jwks()
    return jwt.decode(
        id_token,
        jwks,
        algorithms=["RS256"],
        audience=COGNITO_CLIENTID,
        issuer=f"https://cognito-idp.{REGION}.amazonaws.com/{COGNITO_POOL_ID}",
        options={"verify_at_hash": False},  # Hosted UI returns access token separately
    )

# ---------------------------
# Public API used by pages (UNCHANGED)
# ---------------------------
def ensure_logged_in():
    """
    If not logged-in, render a 'Log in with Cognito' button and stop.
    If redirected back with ?code=..., exchange for tokens, validate, and store the session.
    """
    qp = _get_query_params()

    # Complete the OAuth flow after Cognito redirects back
    if "code" in qp and "id_token" not in st.session_state:
        code = qp["code"][0] if isinstance(qp["code"], list) else qp["code"]
        tokens = exchange_code_for_tokens(code)
        claims = validate_id_token(tokens["id_token"])

        st.session_state["id_token"] = tokens["id_token"]
        st.session_state["user"] = {
            "email": claims.get("email"),
            "name": claims.get("name") or claims.get("cognito:username"),
            "sub": claims.get("sub"),
        }

        # Clean URL
        try:
            st.query_params.clear()
        except Exception:
            st.experimental_set_query_params()  # clears

    # Not logged in: show Hosted UI link
    if "id_token" not in st.session_state:
        st.link_button("🔐 Log in with Cognito", login_url(), type="primary")
        st.stop()

def require_login():
    """
    Compatibility wrapper for pages that import `require_login`.
    It simply enforces the same behavior as ensure_logged_in().
    """
    ensure_logged_in()

def logout_button():
    if "id_token" in st.session_state:
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()

# ---------------------------
# NEW: Lightweight helpers for greeting (SAFE ADDITION)
# ---------------------------
def current_user() -> dict:
    """
    Return the current user dict from the session or {}.
    Keys: email, name, sub (when logged in via Cognito).
    """
    return st.session_state.get("user", {}) or {}

def display_name(user: dict | None = None) -> str:
    """
    Derive a friendly display name.
    Prefers `name`; otherwise uses the local part of `email`; falls back to 'User'.
    """
    user = user or current_user()
    name = user.get("name")
    if name:
        return name
    email = user.get("email", "")
    if "@" in email:
        return email.split("@", 1)[0]
    return "User"

def greet_user(prefix: str = "Hi", emoji: str = "👋"):
    """
    Render a professional, unobtrusive greeting if the user is logged in.
    Safe to call on any page (no-op if not logged in).
    """
    if "id_token" in st.session_state:
        dn = display_name()
        st.markdown(f"### {emoji} {prefix} **{dn}**")
