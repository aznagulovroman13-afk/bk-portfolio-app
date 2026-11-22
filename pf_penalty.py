"""Начисленная неустойка по ЖК и годам: за просрочку передачи по ДДУ и за нарушение сроков устранения недостатков.

2026 год считается по квартирам и замечаниям среза (до даты среза включительно):
- просрочка передачи — ч. 2 ст. 6 214-ФЗ, 1/300 ставки × 2 × цена за каждый день; дни просрочки разнесены по календарным годам;
- замечания — 1% стоимости устранения недостатков по квартире за каждый день сверх регламентного срока (45 дней);
  база — расчётная стоимость устранения по квартире с просроченными замечаниями (CLAIM_BASE_PER_FLAT).
2024–2025 годы — начисления по ранее переданным очередям ЖК: доля к уровню 2026 года задаётся профилем ЖК
(давно строящиеся ЖК несут больше прошлых начислений, новые — меньше).
"""
from __future__ import annotations

import pandas as pd

import pf_core as C
import pf_remstat

YEARS = (2024, 2025, 2026)
REMARK_RATE = 0.01          # 1% стоимости устранения за день просрочки
REMARK_LIMIT_DAYS = 45      # регламентный срок устранения, дней
CLAIM_BASE_PER_FLAT = 180_000.0  # расчётная стоимость устранения недостатков по квартире, ₽ (допущение)


def history_factors(key: str) -> dict:
    """Начисления 2024 и 2025 годов относительно 2026 года по профилю ЖК (ramp < 0 — давно строящийся ЖК, > 0 — новый)."""
    ramp = pf_remstat.PROFILES.get(key, {}).get("ramp", 0.0)
    return {2024: round(min(1.0, max(0.0, 0.35 - 0.40 * ramp)), 3), 2025: round(min(1.4, max(0.12, 0.80 - 0.45 * ramp)), 3)}


def ddu_by_year(A: pd.DataFrame, price: float, snapshot: pd.Timestamp) -> dict:
    """Неустойка за просрочку передачи по квартирам среза (те же коэффициенты, что в разделе «Финансы»),
    разнесённая по годам пропорционально календарным дням просрочки."""
    kv = A[A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].isin([C.NT_OVERDUE, C.LATE])]
    amount = kv["Коэф. неустойки на 1 ₽ цены (верх)"].fillna(0) * price
    start = pd.to_datetime(kv["Срок по ДДУ"], errors="coerce") + pd.Timedelta(days=1)
    end = pd.to_datetime(kv["Дата принятия собственником"], errors="coerce").fillna(snapshot)
    spans = {}
    for y in YEARS:
        lo, hi = pd.Timestamp(year=y, month=1, day=1), pd.Timestamp(year=y + 1, month=1, day=1)
        spans[y] = (end.clip(upper=hi) - start.clip(lower=lo)).dt.days.clip(lower=0).fillna(0)
    total_days = sum(spans.values())
    last = YEARS[-1]
    out = {}
    for y in YEARS:
        share = (spans[y] / total_days.where(total_days > 0)).fillna(1.0 if y == last else 0.0)
        out[y] = float((amount * share).sum())
    return out


def project_row(d: dict, p: dict) -> dict:
    A, cd = d["units"], d["calc_date"]
    ddu = ddu_by_year(A, p["price"], cd)
    late_days = max(10.0, p["rem"]["avg_days"] - REMARK_LIMIT_DAYS)
    flats = int(A["Просрочено (регл)"].fillna(0).gt(0).sum())
    rem26 = flats * CLAIM_BASE_PER_FLAT * REMARK_RATE * late_days
    h = history_factors(p["key"])
    base = ddu[2026]
    ddu_y = {2024: ddu[2024] + base * h[2024], 2025: ddu[2025] + base * h[2025], 2026: base}
    rem_y = {2024: rem26 * h[2024], 2025: rem26 * h[2025], 2026: rem26}
    total = sum(ddu_y.values()) + sum(rem_y.values())
    return dict(key=p["key"], name=p["name"], ddu=ddu_y, remarks=rem_y, total=total, accrued_2026=base, flats_overdue_remarks=flats,
                overdue_remarks=int(A["Просрочено (регл)"].fillna(0).sum()))


def table(D: dict, projects: list[dict]) -> dict:
    rows = [project_row(D[p["key"]], p) for p in projects]
    grand = sum(r["total"] for r in rows) or 1.0
    for r in rows:
        r["share"] = r["total"] / grand
    rows.sort(key=lambda r: -r["total"])
    tot = dict(name="Итого по портфелю", ddu={y: sum(r["ddu"][y] for r in rows) for y in YEARS},
               remarks={y: sum(r["remarks"][y] for r in rows) for y in YEARS}, total=grand, share=1.0)
    return dict(rows=rows, total=tot)
