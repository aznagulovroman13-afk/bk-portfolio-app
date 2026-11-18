"""Собирает из исходного проекта (ТОЛЬКО чтение) минимальный обезличенный срез и сразу шифрует его (Fernet).

Запуск:  python tools/build_data.py <путь_к_исходному_проекту>
Ключ — DATA_KEY из .streamlit/secrets.toml. Открытые файлы на диск не пишутся: в data/bunino/ попадают только *.enc.
В срез входят только счётчики и статусы по помещениям: без ФИО, телефонов, свободного текста и подрядчиков.
"""
from __future__ import annotations

import io
import json
import sys
import tomllib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pf_crypto  # noqa: E402

SRC = Path(sys.argv[1]) / "data" / "ceo"
DST = ROOT / "data" / "bunino"
KEY = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["DATA_KEY"]
APT_COLS = ["Объект", "Корпус", "Тип объекта", "Срок по ДДУ", "Плановая дата ключей в ОЗ", "Дата принятия собственником",
            "Исходный статус", "Просрочка ДДУ", "Просрочка ДДУ факт, дн.", "Ставка ЦБ на срок ДДУ, %",
            "Ставка (нижний вариант), %", "Коэф. неустойки на 1 ₽ цены (верх)", "Коэф. неустойки на 1 ₽ цены (низ)",
            "Мот. отказ / снятие готовности", "Статус записи собственника", "Замечаний открыто", "Критических"]
KPI_KEYS = ["calc_date", "remarks_date", "pa_date", "schedule_date", "current", "previous_snapshot"]


def _put_parquet(df: pd.DataFrame, name: str) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    (DST / f"{name}.parquet.enc").write_bytes(pf_crypto.encrypt_bytes(buf.getvalue(), KEY))


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    a = pd.read_parquet(SRC / "apartments.parquet")[APT_COLS]
    a["Корпус"] = a["Корпус"].astype(str)
    _put_parquet(a, "apartments")
    ks = pd.read_parquet(SRC / "korpus_summary.parquet")[["Корпус", "Помещений", "Передано", "Не_передано_просрочка"]]
    ks["Корпус"] = ks["Корпус"].astype(str)
    _put_parquet(ks, "korpus_summary")
    _put_parquet(pd.read_parquet(SRC / "transfers_weekly.parquet"), "transfers_weekly")
    k = json.loads((SRC / "kpis.json").read_text(encoding="utf-8"))
    out = {key: k.get(key) for key in KPI_KEYS}
    out["week_transfers"] = k.get("week_over_week", {}).get("transfers")
    (DST / "kpis.json.enc").write_bytes(pf_crypto.encrypt_bytes(json.dumps(out, ensure_ascii=False).encode("utf-8"), KEY))
    print("готово:", DST, [p.name for p in DST.iterdir()])


if __name__ == "__main__":
    main()
