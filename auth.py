# auth.py
import os
import requests
from urllib.parse import urlencode
from jose import jwt, jwk
import streamlit as st

# ---- Config (from secrets with sane defaults) ----
COGNITO_DOMAIN   = st.secrets["COGNITO_DOMAIN"]          # e.g. https://my-ppelogin.auth.us-east-2.amazoncognito.com
COGNITO_CLIENTID = st.secrets["COGNITO_APP_CLIENT_ID"]   # App client (no secret)
COGNITO_POOL_ID  = st.secrets["COGNITO_USER_POOL_ID"]    # e.g. us-east-2_abc123
REGION           = st.secrets.get("REGION", "us-east-2")
REDIRECT_URI     = st.secrets["COGNITO_REDIRECT_URI"]    # your Streamlit URL

def _get_query_params():
    # Streamlit API changed; this keeps it compatible
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()

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

def ensure_logged_in():
    """Show login button if not logged-in. On redirect (?code=...) finish login & store user session."""
    qp = _get_query_params()
    if "code" in qp and "id_token" not in st.session_state:
        tokens = exchange_code_for_tokens(qp["code"])
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

    if "id_token" not in st.session_state:
        st.link_button("🔐 Log in with Cognito", login_url(), type="primary")
        st.stop()

def logout_button():
    if "id_token" in st.session_state:
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()
