import hashlib
import hmac
import re
import secrets

import streamlit as st

from config import get_bool_secret, get_secret
from database import create_user, ensure_user, get_user_by_username

PASSWORD_ITERATIONS = 600_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def _normalize_username(username: str) -> str:
    return username.strip().lower()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = stored_hash.split("$", 3)
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations_text),
    ).hex()
    return hmac.compare_digest(derived, expected)


def is_auth_enabled() -> bool:
    return get_bool_secret("AUTH_REQUIRED", True)


def is_signup_enabled() -> bool:
    return get_bool_secret("ALLOW_SIGNUP", True)


def is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


def get_authenticated_user_id() -> int | None:
    user_id = st.session_state.get("authenticated_user_id")
    return int(user_id) if user_id is not None else None


def get_authenticated_username() -> str:
    return str(st.session_state.get("authenticated_user", ""))


def _set_authenticated_user(user: dict):
    st.session_state["authenticated"] = True
    st.session_state["authenticated_user_id"] = user["id"]
    st.session_state["authenticated_user"] = user["username"]


def logout():
    st.session_state["authenticated"] = False
    st.session_state["authenticated_user_id"] = None
    st.session_state["authenticated_user"] = ""
    st.session_state["session_id"] = None
    st.session_state["search_done"] = False
    for key in (
        "login_username",
        "login_password",
        "signup_username",
        "signup_password",
        "signup_password_confirm",
    ):
        if key in st.session_state:
            del st.session_state[key]


def bootstrap_default_user():
    username = str(get_secret("APP_USERNAME", "") or "").strip()
    password = str(get_secret("APP_PASSWORD", "") or "")
    if not username or not password:
        return

    normalized = _normalize_username(username)
    existing = get_user_by_username(normalized)
    if existing and verify_password(password, existing["password_hash"]):
        return
    ensure_user(normalized, hash_password(password))


def _validate_signup(username: str, password: str, confirm_password: str) -> str | None:
    if not USERNAME_RE.fullmatch(username):
        return "Username must be 3-32 characters and use only letters, numbers, `.`, `_`, or `-`."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if password != confirm_password:
        return "Passwords do not match."
    return None


def require_authentication():
    if not is_auth_enabled():
        return

    bootstrap_default_user()

    if is_authenticated():
        return

    st.title("Lead Research Dashboard")
    st.caption("Create an account or log in to access your workspace.")

    login_tab, signup_tab = st.tabs(
        ["Log in", "Sign up"] if is_signup_enabled() else ["Log in", "About access"]
    )

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Log in")

        if submitted:
            normalized = _normalize_username(username)
            user = get_user_by_username(normalized)
            if user and verify_password(password, user["password_hash"]):
                _set_authenticated_user(user)
                st.rerun()
            st.error("Invalid username or password.")

    with signup_tab:
        if not is_signup_enabled():
            st.info("Self-signup is disabled for this deployment.")
        else:
            with st.form("signup_form", clear_on_submit=False):
                username = st.text_input("Choose a username", key="signup_username")
                password = st.text_input(
                    "Choose a password", type="password", key="signup_password"
                )
                confirm_password = st.text_input(
                    "Confirm password",
                    type="password",
                    key="signup_password_confirm",
                )
                submitted = st.form_submit_button("Create account")

            if submitted:
                normalized = _normalize_username(username)
                error = _validate_signup(normalized, password, confirm_password)
                if error:
                    st.error(error)
                else:
                    user = create_user(normalized, hash_password(password))
                    if user is None:
                        st.error("That username is already taken.")
                    else:
                        _set_authenticated_user(user)
                        st.success("Account created.")
                        st.rerun()

    st.stop()
