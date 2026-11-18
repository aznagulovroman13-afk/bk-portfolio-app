"""Загрузка зашифрованных срезов ЖК. Шлюз проверяется ДО чтения файлов."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import pf_crypto
from data_gate import real_data_allowed

DATA_ROOT = Path(__file__).resolve().parent / "data"
DATA_KEY_NAME = "DATA_KEY"
# ключ папки данных → название ЖК (порядок — порядок в отчёте; все ЖК равноправны)
PROJECTS = (("bunino", "Бунинские кварталы"), ("zen", "Дзен-кварталы"), ("proksh", "Прокшино"), ("desn", "Десноречье"),
            ("scandc", "Скандинавия Центр"), ("yuzh", "Южные Сады"), ("vsev", "Всеволожск"), ("lag", "Лаголово"),
            ("zorge", "Дом на Зорге"), ("scands", "Скандинавия Юг"))
TABLES = ("units", "remarks", "contractors")


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


def load(allowed: bool | None = None, root: Path = DATA_ROOT, key: str | None = None, projects=PROJECTS) -> dict:
    """Возвращает {папка: {name, units, remarks, contractors, calc_date, [ref_*]}} для каждого ЖК."""
    if allowed is None:
        allowed = real_data_allowed()
    if allowed is not True:
        raise LockedError("Приложение не активировано")
    key = _key(key)
    if not key:
        raise LockedError("Нет ключа данных")
    out = {}
    try:
        for folder, name in projects:
            d = {"name": name, "key": folder}
            for t in TABLES:
                d[t] = pf_crypto.read_parquet_enc(root / folder / f"{t}.parquet.enc", key)
            for t in ("ref_transfers", "ref_korpus"):
                f = root / folder / f"{t}.parquet.enc"
                if f.exists():
                    d[t] = pf_crypto.read_parquet_enc(f, key)
            f = root / folder / "ref_kpis.json.enc"
            d["ref_kpis"] = pf_crypto.read_json_enc(f, key) if f.exists() else None
            for t in ("remarks", "contractors"):                       # единая терминология в названиях групп замечаний
                if "Группа" in d[t]:
                    d[t]["Группа"] = d[t]["Группа"].astype(str).replace({"Инженерка": "Инженерные системы"})
            d["calc_date"] = pd.Timestamp("2026-11-11")
            if d["ref_kpis"] and d["ref_kpis"].get("calc_date"):
                d["calc_date"] = pd.Timestamp(pd.to_datetime(d["ref_kpis"]["calc_date"], dayfirst=True))
            out[folder] = d
    except pf_crypto.InvalidToken as e:
        raise LockedError("Ключ данных не подходит") from e
    return out
