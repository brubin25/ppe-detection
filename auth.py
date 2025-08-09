import requests
from urllib.parse import urlencode
from jose import jwt, jwk  # jwk kept for future extension
import streamlit as st

# ---- Config from secrets ----
COGNITO_DOMAIN   = st.secrets["COGNITO_DOMAIN"]        # e.g. https://xxxxx.auth.us-east-2.amazoncognito.com
COGNITO_CLIENTID = st.secrets["COGNITO_APP_CLIENT_ID"] # App client (no secret)
COGNITO_POOL_ID  = st.secrets["COGNITO_USER_POOL_ID"]  # e.g. us-east-2_abc123
REGION           = st.secrets.get("REGION", "us-east-2")
REDIRECT_URI     = st.secrets["COGNITO_REDIRECT_URI"]  # your Streamlit URL (exact, no trailing slash)

# ---------------------------
# Utilities
# ---------------------------
def _get_query_params():
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()

def _first(v):
    if isinstance(v, (list, tuple)):
        return v[0] if v else None
    return v

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
        options={"verify_at_hash": False},
    )

# ---------------------------
# Session helpers
# ---------------------------
def is_logged_in() -> bool:
    return "id_token" in st.session_state or st.session_state.get("logged_in", False)

# ---------------------------
# Public API used by pages
# ---------------------------
def ensure_logged_in():
    """Blocking: show login button if not logged-in; complete flow if ?code=..."""
    qp = _get_query_params()

    # complete flow if redirected back
    if "code" in qp and not is_logged_in():
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
            # clean URL
            try:
                st.query_params.clear()
            except Exception:
                st.experimental_set_query_params()

    if not is_logged_in():
        st.link_button("🔐 Log in with Cognito", login_url(), type="primary")
        st.stop()

def complete_login_if_returned():
    """
    Non-blocking: if we came back with ?code=..., finish the login silently and continue.
    Use this on public pages (e.g., Home).
    """
    qp = _get_query_params()
    code = _first(qp.get("code"))
    if code and not is_logged_in():
        tokens = exchange_code_for_tokens(code)
        claims = validate_id_token(tokens["id_token"])
        st.session_state["id_token"] = tokens["id_token"]
        st.session_state["user"] = {
            "email": claims.get("email"),
            "name": claims.get("name") or claims.get("cognito:username"),
            "sub": claims.get("sub"),
        }
        st.session_state["logged_in"] = True
        try:
            st.query_params.clear()
        except Exception:
            st.experimental_set_query_params()

def logout_button():
    if is_logged_in():
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()

def require_login(
    login_page_path: str = "pages/00_Login.py",
    message: str = "You must log in to access this page.",
):
    if not is_logged_in():
        st.warning(message)
        try:
            st.page_link(login_page_path, label="🔐 Go to Login")
        except Exception:
            st.link_button("🔐 Go to Login", login_url(), type="primary")
        st.stop()
