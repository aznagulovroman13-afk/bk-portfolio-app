"""Шифрование среза данных (Fernet). Расшифровка только в памяти, на диск ничего не пишется."""
from __future__ import annotations

import io
import json

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken

__all__ = ["encrypt_bytes", "decrypt_bytes", "read_parquet_enc", "read_json_enc", "InvalidToken"]


def encrypt_bytes(raw: bytes, key: str | bytes) -> bytes:
    return Fernet(key).encrypt(raw)


def decrypt_bytes(blob: bytes, key: str | bytes) -> bytes:
    return Fernet(key).decrypt(blob)


def read_parquet_enc(path, key) -> pd.DataFrame:
    with open(path, "rb") as fh:
        return pd.read_parquet(io.BytesIO(decrypt_bytes(fh.read(), key)))


def read_json_enc(path, key) -> dict:
    with open(path, "rb") as fh:
        return json.loads(decrypt_bytes(fh.read(), key).decode("utf-8"))
