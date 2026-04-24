import os
from typing import Any


def _streamlit_secrets() -> Any | None:
    try:
        import streamlit as st

        return st.secrets
    except Exception:
        return None


def get_secret(name: str, default: Any = None) -> Any:
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    secrets = _streamlit_secrets()
    if secrets is None:
        return default

    try:
        return secrets[name]
    except Exception:
        return default


def get_secret_list(name: str) -> list[str]:
    value = get_secret(name, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
    return []
