import hmac

import streamlit as st

from config import get_secret


def is_auth_enabled() -> bool:
    return bool(get_secret("APP_USERNAME") and get_secret("APP_PASSWORD"))


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def get_authenticated_username() -> str:
    return str(st.session_state.get("authenticated_user", ""))


def logout():
    st.session_state["authenticated"] = False
    st.session_state["authenticated_user"] = ""
    for key in ("login_username", "login_password"):
        if key in st.session_state:
            del st.session_state[key]


def require_authentication():
    if not is_auth_enabled():
        return

    if is_authenticated():
        return

    expected_username = str(get_secret("APP_USERNAME", "")).strip()
    expected_password = str(get_secret("APP_PASSWORD", ""))

    st.title("Lead Research Dashboard")
    st.caption("Authentication is enabled for this deployment.")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        valid_user = hmac.compare_digest(username.strip(), expected_username)
        valid_password = hmac.compare_digest(password, expected_password)
        if valid_user and valid_password:
            st.session_state["authenticated"] = True
            st.session_state["authenticated_user"] = username.strip()
            st.rerun()
        st.error("Invalid username or password.")

    st.stop()
