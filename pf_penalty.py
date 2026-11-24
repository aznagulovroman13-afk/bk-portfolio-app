"""Неустойка по ЖК и годам: за просрочку передачи по ДДУ и за нарушение сроков устранения недостатков, с учётом моратория.

Правовая основа расчёта:
- ПП РФ от 18.03.2024 № 326 (ред. ПП № 1916 от 26.12.2024, № 925 от 19.06.2025, № 2227 от 30.12.2025): неустойка
  по ч. 2 ст. 6 214-ФЗ не начисляется с 22.03.2024 (день опубликования) по 31.12.2025; неустойка по ч. 8 ст. 7
  и иные санкции в пользу граждан (ч. 9 ст. 4) — также не начисляются с 22.03.2024 по 31.12.2025;
  п. 2: с 01.07.2023 по 31.12.2025 ставка не выше ключевой на 01.07.2023 (7,5%) — в расчёте действует для 01.01–21.03.2024.
- 266-ФЗ (с 01.09.2024): неустойка по ч. 8 ст. 7 — 1/300 ставки × 2 для граждан (1/150) от стоимости устранения,
  не более стоимости устранения; до 01.09.2024 — 1% в день. 482-ФЗ (с 01.01.2025, ч. 4 ст. 10): сумма по требованиям
  о качестве — не более 3% цены договора.
2026 год: по квартирам и замечаниям среза; по ДДУ совпадает с накопленной неустойкой раздела «Финансы».
2024–2025 годы: ранее переданные очереди ЖК; уровень относительно 2026 года задаётся профилем ЖК.
"""
from __future__ import annotations

import pandas as pd

import pf_remstat

PENALTY_SCHEMA = "p4"
YEARS = (2024, 2025, 2026)
MORATORIUM = (pd.Timestamp("2024-03-22"), pd.Timestamp("2025-12-31"))   # ПП № 326, п. 1 (с продлениями)
RATE_CAP = 7.5                                                            # ПП № 326, п. 2: ключевая ставка на 01.07.2023, %
RATE_CAP_FROM = pd.Timestamp("2023-07-01")
LAW_266_FROM = pd.Timestamp("2024-09-01")                                 # новая редакция ч. 8 ст. 7 214-ФЗ
OLD_REMARK_RATE = 0.01                                                    # 1% в день до 01.09.2024
REMARK_LIMIT_DAYS = 45                                                    # регламентный срок устранения, дней
CLAIM_BASE_PER_FLAT = 180_000.0                                           # расчётная стоимость устранения по квартире, ₽
QUALITY_CAP = 0.03                                                        # ч. 4 ст. 10 214-ФЗ: 3% цены договора
HIST_DDU_RATE = 16.0                                                      # ставка на срок исполнения ДДУ ранее переданных очередей, %
# ключевая ставка Банка России (дата начала действия → %), cbr.ru
KEY_RATE = ((pd.Timestamp("2023-12-18"), 16.0), (pd.Timestamp("2024-07-29"), 18.0), (pd.Timestamp("2024-09-16"), 19.0),
            (pd.Timestamp("2024-10-28"), 21.0), (pd.Timestamp("2025-06-09"), 20.0), (pd.Timestamp("2025-07-28"), 18.0),
            (pd.Timestamp("2025-09-15"), 17.0), (pd.Timestamp("2025-10-27"), 16.5), (pd.Timestamp("2025-12-22"), 16.0),
            (pd.Timestamp("2026-02-16"), 15.5), (pd.Timestamp("2026-03-23"), 15.0), (pd.Timestamp("2026-04-27"), 14.5),
            (pd.Timestamp("2026-06-22"), 14.25), (pd.Timestamp("2026-07-27"), 14.0))


def key_rate(d: pd.Timestamp) -> float:
    r = KEY_RATE[0][1]
    for start, v in KEY_RATE:
        if d >= start:
            r = v
    return r


def in_moratorium(d: pd.Timestamp) -> bool:
    return MORATORIUM[0] <= d <= MORATORIUM[1]


def year_in_moratorium(y: int) -> bool:
    """Календарный год целиком приходится на мораторий."""
    return MORATORIUM[0] <= pd.Timestamp(year=y, month=1, day=1) and pd.Timestamp(year=y, month=12, day=31) <= MORATORIUM[1]


def _days(y: int, snapshot: pd.Timestamp):
    end = min(pd.Timestamp(year=y, month=12, day=31), snapshot)
    return pd.date_range(pd.Timestamp(year=y, month=1, day=1), end, freq="D")


def remark_daily_rate(d: pd.Timestamp) -> float:
    """Доля стоимости устранения за день: 1% до 01.09.2024, далее 1/150 ключевой ставки (266-ФЗ, граждане)."""
    return OLD_REMARK_RATE if d < LAW_266_FROM else key_rate(d) / 100 / 150


def history_factors(key: str) -> dict:
    """Уровень начислений 2024 и 2025 годов (ранее переданные очереди) к 2026 году: ramp < 0 — давно строящийся ЖК, > 0 — новый."""
    ramp = pf_remstat.PROFILES.get(key, {}).get("ramp", 0.0)
    return {2024: round(min(1.0, max(0.0, 0.35 - 0.40 * ramp)), 3), 2025: round(min(1.4, max(0.12, 0.80 - 0.45 * ramp)), 3), 2026: 1.0}


def history_transfers(key: str, units_kv: int) -> dict:
    """Передано квартир ранее переданных очередей в 2024 и 2025 годах: тот же профиль ЖК, что и у неустойки этих лет."""
    h = history_factors(key)
    return {y: int(round(units_kv * h[y] * 0.9)) for y in (2024, 2025)}


def ddu_2026(A: pd.DataFrame, price: float) -> float:
    """Неустойка 2026 года по квартирам среза — те же коэффициенты, что в «Финансах» (начисление с 01.01.2026)."""
    kv = A[A["Тип объекта"].eq("Квартира")]
    return float(kv["Коэф. неустойки на 1 ₽ цены (верх)"].fillna(0).sum()) * price


def remarks_2026(A: pd.DataFrame, price: float, avg_days: float, snapshot: pd.Timestamp) -> tuple[float, int, float]:
    """Неустойка за просрочку устранения по квартирам с просроченными замечаниями: дни сверх 45 — в конце периода до среза."""
    flats = int(A["Просрочено (регл)"].fillna(0).gt(0).sum())
    late = int(max(10.0, avg_days - REMARK_LIMIT_DAYS))
    days = pd.date_range(snapshot - pd.Timedelta(days=late - 1), snapshot, freq="D")
    per_flat = CLAIM_BASE_PER_FLAT * sum(remark_daily_rate(d) for d in days)
    cap = min(CLAIM_BASE_PER_FLAT, max(0.0, QUALITY_CAP * price - CLAIM_BASE_PER_FLAT))
    return flats * min(per_flat, cap), flats, late


def project_row(d: dict, p: dict) -> dict:
    A, cd = d["units"], d["calc_date"]
    price = p["price"]
    d26 = _days(2026, cd)
    ddu26 = ddu_2026(A, price)
    rem26, flats, late = remarks_2026(A, price, p["rem"]["avg_days"], cd)
    ddu_day = ddu26 / len(d26)                                         # средняя дневная неустойка 2026 года
    rem_unit = sum(remark_daily_rate(x) for x in d26) / len(d26)       # средняя дневная доля 2026 года
    rem_day = rem26 / len(d26) / rem_unit if rem_unit else 0.0         # база замечаний на день
    h = history_factors(p["key"])
    gross = {"ddu": {}, "remarks": {}}
    acc = {"ddu": {}, "remarks": {}}
    for y in YEARS:
        if y == 2026:
            gross["ddu"][y] = acc["ddu"][y] = ddu26
            gross["remarks"][y] = acc["remarks"][y] = rem26
            continue
        g_d = a_d = g_r = a_r = 0.0
        for x in _days(y, cd):
            gd = ddu_day * h[y]
            gr = rem_day * h[y] * remark_daily_rate(x)
            g_d += gd
            g_r += gr
            if not in_moratorium(x):
                a_d += gd * (min(1.0, RATE_CAP / HIST_DDU_RATE) if x >= RATE_CAP_FROM else 1.0)
                a_r += gr
        gross["ddu"][y], acc["ddu"][y], gross["remarks"][y], acc["remarks"][y] = g_d, a_d, g_r, a_r
    eff = {m: {y: gross[m][y] - acc[m][y] for y in YEARS} for m in ("ddu", "remarks")}
    total = sum(acc["ddu"].values()) + sum(acc["remarks"].values())
    return dict(key=p["key"], name=p["name"], ddu=acc["ddu"], remarks=acc["remarks"], gross=gross, effect=eff,
                effect_total=sum(eff["ddu"].values()) + sum(eff["remarks"].values()), total=total,
                accrued_2026=ddu26, flats_overdue_remarks=flats, late_days=late)


def table(D: dict, projects: list[dict]) -> dict:
    rows = [project_row(D[p["key"]], p) for p in projects]
    grand = sum(r["total"] for r in rows) or 1.0
    for r in rows:
        r["share"] = r["total"] / grand
    rows.sort(key=lambda r: -r["total"])
    s = lambda f: {y: sum(f(r, y) for r in rows) for y in YEARS}
    tot = dict(name="Итого", ddu=s(lambda r, y: r["ddu"][y]), remarks=s(lambda r, y: r["remarks"][y]),
               gross={m: s(lambda r, y, m=m: r["gross"][m][y]) for m in ("ddu", "remarks")},
               effect={m: s(lambda r, y, m=m: r["effect"][m][y]) for m in ("ddu", "remarks")},
               effect_total=sum(r["effect_total"] for r in rows), total=grand, share=1.0)
    return dict(rows=rows, total=tot)
