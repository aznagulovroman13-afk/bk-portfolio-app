"""Шлюз доступа к реальному срезу. Без секрета данные не показываются."""
from __future__ import annotations

SECRET_KEY = "SHOW_REAL_DATA"
SECRET_YES = "yes"
LOCKED_MESSAGE = "Приложение не активировано"


def real_data_allowed(secrets=None) -> bool:
    """True только если SHOW_REAL_DATA == 'yes'.

    Нет файла секретов, нет ключа или любая ошибка чтения — False, без исключения.
    """
    try:
        src = secrets
        if src is None:
            import streamlit as st
            src = st.secrets
        return src.get(SECRET_KEY) == SECRET_YES
    except Exception:
        return False
