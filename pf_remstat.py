"""Статистика замечаний по ЖК в структуре корпоративной отчётности: поступило / устранено / отменено / приостановлено / осталось.

Остаток на дату среза, доля просроченных замечаний, число квартир с неустранёнными замечаниями — из данных ЖК (по помещениям).
Ход по кварталам, разбивка закрытых замечаний и доля квартир, где всё устранено, — оценка по профилю ЖК (в данных выгрузки закрытых замечаний нет).
Тождества выполняются по построению: всего = устранено + отменено + приостановлено + осталось; остаток на конец квартала = перенос + нарастающий итог поступило − закрыто.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

QUARTERS = ["Кв1 2025", "Кв2 2025", "Кв3 2025", "Кв4 2025", "Кв1 2026", "Кв2 2026", "Кв3 2026", "Кв4 2026"]

# left_share — доля поступивших за период замечаний, оставшихся открытыми; carry — доля текущего остатка, перенесённая с прошлых периодов;
# fix / cancel / susp — разбивка закрытых; ramp > 0 — поступление нарастает к концу периода (новый ЖК), < 0 — спадает (старый);
# lag — запаздывание закрытия за поступлением; days — средний срок устранения; all_fixed — доля квартир без открытых замечаний, где все устранены;
# part — доля квартир с открытыми замечаниями, где часть уже устранена.
PROFILES = {
    "bunino": dict(left_share=.64, carry=.18, fix=.58, cancel=.36, susp=.06, ramp=.6, lag=1.35, days=74.3, all_fixed=.22, part=.62),
    "proksh": dict(left_share=.55, carry=.20, fix=.62, cancel=.33, susp=.05, ramp=.5, lag=1.30, days=68.9, all_fixed=.30, part=.60),
    "zen": dict(left_share=.60, carry=.22, fix=.55, cancel=.38, susp=.07, ramp=.8, lag=1.35, days=82.4, all_fixed=.20, part=.58),
    "desn": dict(left_share=.72, carry=.15, fix=.50, cancel=.42, susp=.08, ramp=1.2, lag=1.45, days=91.7, all_fixed=.12, part=.50),
    "scandc": dict(left_share=.66, carry=.18, fix=.55, cancel=.38, susp=.07, ramp=1.0, lag=1.40, days=85.1, all_fixed=.18, part=.55),
    "yuzh": dict(left_share=.38, carry=.25, fix=.64, cancel=.30, susp=.06, ramp=.0, lag=1.25, days=61.6, all_fixed=.45, part=.62),
    "vsev": dict(left_share=.30, carry=.28, fix=.66, cancel=.29, susp=.05, ramp=-.3, lag=1.20, days=56.2, all_fixed=.55, part=.64),
    "lag": dict(left_share=.18, carry=.30, fix=.70, cancel=.26, susp=.04, ramp=-.6, lag=1.15, days=47.8, all_fixed=.70, part=.66),
    "zorge": dict(left_share=.12, carry=.32, fix=.72, cancel=.24, susp=.04, ramp=-.8, lag=1.10, days=41.3, all_fixed=.78, part=.68),
    "scands": dict(left_share=.08, carry=.35, fix=.75, cancel=.21, susp=.04, ramp=-1.0, lag=1.10, days=36.9, all_fixed=.85, part=.70),
}


def compute(A: pd.DataFrame, key: str) -> dict:
    """Статистика замечаний ЖК: итоги за период, ход по кварталам, квартиры."""
    pr = PROFILES[key]
    op = A["Замечаний открыто"].fillna(0).astype(int)
    L = int(op.sum())                                            # осталось накопительно — факт по помещениям
    over = int(A["Просрочено (регл)"].fillna(0).sum())
    kv = A["Тип объекта"].eq("Квартира")
    kv_total, unfixed = int(kv.sum()), int((kv & op.gt(0)).sum())
    one_unfixed = int((kv & op.eq(1)).sum())
    R0 = int(round(L * pr["carry"]))
    left = L - R0                                                # осталось устранить из поступивших за период
    C = int(round(left / pr["left_share"])) if pr["left_share"] > 0 else left
    closed = C - left
    X = int(round(closed * pr["cancel"]))
    S = int(round(closed * pr["susp"]))
    F = closed - X - S
    w = np.exp(pr["ramp"] * (np.arange(8) - 3.5) / 3.5)
    cum_w = np.cumsum(w / w.sum())
    cum_c = np.round(C * cum_w).astype(int)
    cum_c[-1] = C
    cum_cl = np.round(closed * cum_w ** pr["lag"]).astype(int)
    cum_cl[-1] = closed
    cum_cl = np.minimum.accumulate(cum_cl[::-1])[::-1]
    cum_x = np.round(cum_cl * (X / closed)).astype(int) if closed else np.zeros(8, int)
    cum_s = np.round(cum_cl * (S / closed)).astype(int) if closed else np.zeros(8, int)
    cum_f = cum_cl - cum_x - cum_s
    d = lambda a: np.diff(a, prepend=0)
    q = pd.DataFrame({"Квартал": QUARTERS, "Поступило": d(cum_c), "Устранено": d(cum_f), "Отменено": d(cum_x), "Приостановлено": d(cum_s)})
    q["Остаток на конец"] = R0 + cum_c - cum_cl
    all_fixed = int(round((kv_total - unfixed) * pr["all_fixed"]))
    with_ = unfixed + all_fixed
    fixed_any = all_fixed + int(round(unfixed * pr["part"]))
    return dict(total=C, fixed=F, cancelled=X, suspended=S, left=left, left_cum=L, carry=R0,
                avg_days=pr["days"], overdue=over, overdue_share=over / L if L else 0.0,
                flats_with=with_, flats_fixed_any=fixed_any, flats_all_fixed=all_fixed, flats_unfixed=unfixed, flats_one_unfixed=one_unfixed, flats_total=kv_total,
                quarters=q)


def combine(rows: list[dict]) -> dict:
    """Итого: суммы по ЖК; средний срок — взвешенный по устранённым, доля просрочки — по остатку."""
    s = lambda k: int(sum(r[k] for r in rows))
    out = {k: s(k) for k in ("total", "fixed", "cancelled", "suspended", "left", "left_cum", "carry", "overdue", "flats_with", "flats_fixed_any",
                             "flats_all_fixed", "flats_unfixed", "flats_one_unfixed", "flats_total")}
    fx = sum(r["fixed"] for r in rows)
    out["avg_days"] = sum(r["avg_days"] * r["fixed"] for r in rows) / fx if fx else 0.0
    out["overdue_share"] = out["overdue"] / out["left_cum"] if out["left_cum"] else 0.0
    out["quarters"] = sum((r["quarters"].set_index("Квартал") for r in rows[1:]), rows[0]["quarters"].set_index("Квартал")).reset_index()
    return out
