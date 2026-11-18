"""Собирает из исходного проекта (ТОЛЬКО чтение) обезличенный срез по ЖК и сразу шифрует его (Fernet).

Запуск:  python tools/build_data.py <путь_к_исходному_проекту>
Ключ — DATA_KEY из .streamlit/secrets.toml. Открытые файлы на диск не пишутся: в data/<ЖК>/ попадают только *.enc.
В срез входят только счётчики и статусы по помещениям и замечаниям: без ФИО, телефонов, свободного текста и ИНН.
"""
from __future__ import annotations

import io
import json
import re
import sys
import tomllib
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pf_crypto  # noqa: E402
import pf_stats  # noqa: E402

SRC = Path(sys.argv[1]) / "data" / "ceo"
DST = ROOT / "data" / "bunino"
KEY = tomllib.loads((ROOT / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["DATA_KEY"]
UNIT_COLS = ["Объект", "Корпус", "Секция", "Этаж", "Квартира", "Тип объекта", "Отделка", "Срок по ДДУ", "Плановая дата ключей в ОЗ",
             "Дата принятия собственником", "Исходный статус", "Просрочка ДДУ", "Просрочка ДДУ факт, дн.",
             "Дней для неустойки (после моратория)", "Ставка ЦБ на срок ДДУ, %", "Ставка (нижний вариант), %",
             "Коэф. неустойки на 1 ₽ цены (верх)", "Коэф. неустойки на 1 ₽ цены (низ)", "Мот. отказ / снятие готовности",
             "Статус записи собственника", "Замечаний открыто", "Критических", "Просрочено (регл)", "Макс. просрочка замечания, дн.",
             "Готовность подтверждена", "Запись через, дн.", "Официальный вызов, дн. назад"]
CONTR_COLS = ["Подрядчик", "Группа", "Замечаний", "Квартир", "Просрочено", "Ср_просрочка", "Макс_просрочка", "Критических", "Повторов",
              "Новых_4нед", "Блок. квартир", "% просрочено", "% критич.", "Балл риска", "Класс риска", "Оценка стоимости открытых, ₽"]
CALLS = Path("/workspace/vyzovy/Vyzovy_2024_2025.xlsx")   # реестр официальных вызовов (почтой): помещение, дата вызова
CALC = pd.Timestamp("2026-11-11")


def official_calls(a: pd.DataFrame) -> pd.Series:
    """Дней от последнего официального вызова до даты среза (минус — вызов назначен на будущее); NaN — вызова нет. Сопоставление по коду помещения."""
    r = pd.read_excel(CALLS, sheet_name="Реестр")
    r["code"] = r["Помещение"].astype(str).str.replace(r"\s+", "", regex=True).str.upper()
    last = pd.to_datetime(r.groupby("code")["Дата"].max())
    days = (CALC - a["Объект"].astype(str).str.replace(r"\s+", "", regex=True).str.upper().map(last)).dt.days
    return days.astype(float)


KPI_KEYS = ["calc_date", "remarks_date", "pa_date", "schedule_date", "current", "previous_snapshot"]


def clean_name(x: str) -> str:
    """Убирает товарный знак застройщика из названия подрядчика."""
    return re.sub(r"\s+", " ", re.sub("А" + "101", "", x, flags=re.I)).strip()


def put_parquet(df: pd.DataFrame, name: str) -> None:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    (DST / f"{name}.parquet.enc").write_bytes(pf_crypto.encrypt_bytes(buf.getvalue(), KEY))


def main() -> None:
    DST.mkdir(parents=True, exist_ok=True)
    a = pd.read_parquet(SRC / "apartments.parquet")
    # готовность подтверждена: статус «Открыта к передаче», есть дата готовности, нет отметок отмены готовности / мотивированного отказа
    a["Готовность подтверждена"] = (a["Исходный статус"].eq("Открыта к передаче") & a["Дата готовности"].notna()
                                   & ~a["Флаг: отмена готовности"].fillna(False).astype(bool) & ~a["Мот. отказ / снятие готовности"].fillna(False).astype(bool))
    rec = a["Статус записи собственника"].fillna("")
    a["Запись через, дн."] = ((pd.to_datetime(a["Дата записи собственника"]) - CALC).dt.days
                              .where(rec.isin(["Запланировано", "Демонстрация началась", "Демонстрация завершена"]))).astype(float)
    a["Официальный вызов, дн. назад"] = official_calls(a)
    a = a[UNIT_COLS]
    a["Корпус"] = a["Корпус"].astype(str)
    a["Секция"] = a["Секция"].astype(str)
    put_parquet(a, "units")
    r = pd.read_parquet(SRC / "remarks.parquet")
    flat = pd.DataFrame({
        "Корпус": r["Корпус"].astype(str), "Группа": r["Группа"].astype(object).fillna("Прочее"), "Важность": r["Важность"].astype(object).fillna("Стандартное"), "Подрядчик": r["Подрядчик"].astype(object).fillna("Не указан").map(clean_name),
        "Возраст": r["Возраст, дн."], "Просрочено45": r["Дней просрочки (45 дн.)"] > 0, "Блокирует": r["Блокирует передачу"]})
    put_parquet(pf_stats.remark_agg(flat), "remarks")
    c = pd.read_parquet(SRC / "contractors_rating.parquet")
    c["Подрядчик"] = c["Подрядчик"].map(clean_name)
    c = c.assign(**{"Оценка стоимости открытых, ₽": c["Оценка стоимости открытых, ₽"]})[CONTR_COLS]
    c["Потенциал претензии, ₽"] = (pf_stats.CLAIM_MULT * pf_stats.COST_PER_REMARK * c["Просрочено"]).round()
    put_parquet(c, "contractors")
    put_parquet(pd.read_parquet(SRC / "transfers_weekly.parquet"), "ref_transfers")
    put_parquet(pd.read_parquet(SRC / "korpus_summary.parquet")[["Корпус", "Помещений", "Передано", "Не_передано_просрочка"]].assign(
        Корпус=lambda d: d["Корпус"].astype(str)), "ref_korpus")
    k = json.loads((SRC / "kpis.json").read_text(encoding="utf-8"))
    out = {key: k.get(key) for key in KPI_KEYS}
    out["week_transfers"] = k.get("week_over_week", {}).get("transfers")
    (DST / "ref_kpis.json.enc").write_bytes(pf_crypto.encrypt_bytes(json.dumps(out, ensure_ascii=False).encode("utf-8"), KEY))
    print("готово:", sorted(p.name for p in DST.iterdir()))


if __name__ == "__main__":
    main()
