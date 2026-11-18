"""Загрузка среза Бунинских кварталов из зашифрованных файлов. Шлюз проверяется ДО чтения файлов."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import pf_crypto
from data_gate import real_data_allowed

DATA_DIR = Path(__file__).resolve().parent / "data" / "bunino"
DATA_KEY_NAME = "DATA_KEY"


class LockedError(PermissionError):
    """Шлюз закрыт или нет ключа — данные не читаются и не расшифровываются."""


def _key(key):
    if key:
        return key
    try:
        import streamlit as st
        return st.secrets.get(DATA_KEY_NAME)
    except Exception:
        return None


def load(allowed: bool | None = None, root: Path = DATA_DIR, key: str | None = None) -> dict:
    if allowed is None:
        allowed = real_data_allowed()
    if allowed is not True:
        raise LockedError("Приложение не активировано")
    key = _key(key)
    if not key:
        raise LockedError("Нет ключа данных")
    try:
        out = {n: pf_crypto.read_parquet_enc(root / f"{n}.parquet.enc", key) for n in ("apartments", "korpus_summary", "transfers_weekly")}
        out["kpis"] = pf_crypto.read_json_enc(root / "kpis.json.enc", key)
    except pf_crypto.InvalidToken as e:
        raise LockedError("Ключ данных не подходит") from e
    out["calc_date"] = pd.Timestamp(pd.to_datetime(out["kpis"]["calc_date"], dayfirst=True))
    return out
