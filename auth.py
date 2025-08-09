# auth.py
import os
import requests
from urllib.parse import urlencode
from jose import jwt, jwk   # keep jwk import (useful if you extend validation)
import streamlit as st

# ---- Config (from secrets with sane defaults) ----
COGNITO_DOMAIN   = st.secrets["COGNITO_DOMAIN"]          # e.g. https://us-xxx.auth.xx.amazoncognito.com
COGNITO_CLIENTID = st.secrets["COGNITO_APP_CLIENT_ID"]   # App client (no secret)
COGNITO_POOL_ID  = st.secrets["COGNITO_USER_POOL_ID"]    # e.g. us-east-2_abc123
REGION           = st.secrets.get("REGION", "us-east-2")
REDIRECT_URI     = st.secrets["COGNITO_REDIRECT_URI"]    # your Streamlit URL

# ---------------------------
# Utilities
# ---------------------------
def _get_query_params():
    # Streamlit API changed; this keeps it compatible
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()

def _first(v):
    """Return first value if v is a list, else v."""
    if isinstance(v, (list, tuple)):
        return v[0] if v else None
    return v

def _config_ok():
    problems = []
    if not COGNITO_DOMAIN or not COGNITO_DOMAIN.startswith("https://"):
        problems.append("COGNITO_DOMAIN must start with https:// and not be empty.")
    if "amazoncognito.com" not in (COGNITO_DOMAIN or ""):
        problems.append("COGNITO_DOMAIN doesn't look like a Cognito domain.")
    if not COGNITO_CLIENTID:
        problems.append("COGNITO_APP_CLIENT_ID is empty.")
    if not REDIRECT_URI or not REDIRECT_URI.startswith("http"):
        problems.append("COGNITO_REDIRECT_URI must start with http(s) and not be empty.")
    return problems

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
# Session helpers
# ---------------------------
def is_logged_in() -> bool:
    """True if we have an id_token in session."""
    return "id_token" in st.session_state or st.session_state.get("logged_in", False)

# ---------------------------
# Public API used by pages
# ---------------------------
def ensure_logged_in():
    """
    If not logged-in, render login control and stop.
    If redirected back with ?code=..., exchange for tokens, validate, and store the session.
    """
    # Config sanity check (prevents ‘button goes Home’ when URL is bad/relative)
    issues = _config_ok()
    if issues:
        st.error("Auth configuration issue:\n- " + "\n- ".join(issues))
        st.stop()

    qp = _get_query_params()

    # Complete the OAuth flow when Cognito redirects back
    if not is_logged_in() and "code" in qp:
        code = _first(qp.get("code"))
        if code:
            tokens = exchange_code_for_tokens(code)
            claims = validate_id_token(tokens["id_token"])

            st.session_state["id_token"] = tokens["id_token"]
            st.session_state["user"] = {
                "email": claims.get("email"),
                "name": claims.get("name") or claims.get("cognito:username"),
                "sub": claims.get("sub"),
            }
            st.session_state["logged_in"] = True

            # Clean URL
            try:
                st.query_params.clear()
            except Exception:
                st.experimental_set_query_params()  # clears

    # If still not logged in, force a TOP-LEVEL redirect to Cognito (no iframes)
    if not is_logged_in():
        href = login_url()

        # Button that triggers full-page navigation (bypass any embedding)
        if st.button("🔐 Log in with Cognito", type="primary"):
            st.markdown(
                f"""
                <script>
                  window.top.location.replace({href!r});
                </script>
                """,
                unsafe_allow_html=True,
            )
            st.stop()

        # Fallback link in case JS is disabled or blocked
        st.markdown(
            f"""
            <div style="margin-top:8px">
              <a href="{href}" target="_self">Having trouble? Click here to open the Cognito login.</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

def logout_button():
    if is_logged_in():
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()

def require_login(
    login_page_path: str = "pages/00_Login.py",
    message: str = "You must log in to access this page."
):
    """
    Gate a page behind login. Use at the top of any page you want to protect:
        from auth import require_login
        require_login()
    """
    if not is_logged_in():
        st.warning(message)
        try:
            st.page_link(login_page_path, label="🔐 Go to Login")
        except Exception:
            st.link_button("🔐 Go to Login", login_url(), type="primary")
        st.stop()
