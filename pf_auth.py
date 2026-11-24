"""Парольный вход. Пароль — в st.secrets['APP_PASSWORD'], сравнение через hmac.compare_digest.

После MAX_FAILS неверных попыток в сессии вход блокируется на LOCK_SECONDS. Без верного пароля данные не читаются.
"""
from __future__ import annotations

import hmac
import time

import streamlit as st

MAX_FAILS = 5
LOCK_SECONDS = 60
PASS_KEY = "APP_PASSWORD"
OK_FLAG = "pf_auth_ok"


def check_password(candidate: str, secret) -> bool:
    if not isinstance(secret, str) or not secret or not isinstance(candidate, str):
        return False
    return hmac.compare_digest(candidate.encode("utf-8"), secret.encode("utf-8"))


def lock_left(state, now: float | None = None) -> int:
    """Сколько секунд ещё заблокирован вход (0 — можно пробовать)."""
    now = time.time() if now is None else now
    return max(0, int(round(state.get("pf_lock_until", 0) - now)))


def register_fail(state, now: float | None = None) -> None:
    now = time.time() if now is None else now
    state["pf_fails"] = state.get("pf_fails", 0) + 1
    if state["pf_fails"] >= MAX_FAILS:
        state["pf_lock_until"] = now + LOCK_SECONDS
        state["pf_fails"] = 0


def _secret():
    try:
        return st.secrets.get(PASS_KEY)
    except Exception:
        return None


def authenticated() -> bool:
    return st.session_state.get(OK_FLAG) is True


def login_screen(css: str) -> None:
    """Рисует экран входа; при верном пароле ставит флаг и перезапускает страницу."""
    st.markdown(css, unsafe_allow_html=True)
    st.markdown(
        '<style>.stMainBlockContainer{max-width:520px !important;padding-top:14vh !important}'
        '.lg{background:#0B1F3A;color:#fff;border-radius:6px 6px 0 0;padding:24px 28px 18px;border-bottom:3px solid #A67C00}'
        '.lg .k{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#C5CEDA;font-weight:600}'
        '.lg .t{font-size:28px;font-weight:700;margin-top:6px;color:#fff}</style>'
        '<div class="lg"><div class="k">Закрытый отчёт</div><div class="t">Отчёт по заселению</div></div>', unsafe_allow_html=True)
    left = lock_left(st.session_state)
    with st.form("pf_login", border=True):
        pwd = st.text_input("Пароль", type="password", key="pf_pwd", disabled=left > 0)
        ok = st.form_submit_button("Войти", disabled=left > 0)
    if left > 0:
        st.markdown(f'<div class="note">Слишком много попыток. Повторите через {left} с.</div>', unsafe_allow_html=True)
        return
    if ok:
        if check_password(pwd, _secret()):
            st.session_state[OK_FLAG] = True
            st.session_state["pf_fails"] = 0
            st.session_state.pop("pf_pwd", None)
            st.rerun()
        register_fail(st.session_state)
        if lock_left(st.session_state) > 0:
            st.rerun()
        st.markdown('<div class="note" style="color:#B3261E">Неверный пароль</div>', unsafe_allow_html=True)
