"""Расчётное ядро «Портфеля ЖК».

Функции переписаны один в один из действующего отчёта по Бунинским кварталам (проект bk-analytics-real),
чтобы цифры совпадали; здесь они самодостаточны — старый проект не импортируется и не меняется.
Только счётчики и суммы: персональных данных нет.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ILLUSTR_PRICE = 10_000_000          # расчётная цена квартиры, ₽ (цен ДДУ в данных нет)
MM_PRICE = 1_500_000                # расчётная цена машиноместа, ₽
NHP_PRICE = 500_000                 # расчётная цена кладовой (НХП), ₽

NT_OVERDUE = "не передан, срок ДДУ нарушен"
LATE = "передан с нарушением срока"
ONTIME = "передан в срок"
NO_DDU = "нет срока ДДУ в данных"
UNSOLD = "не продан"


def transferred_mask(a: pd.DataFrame) -> pd.Series:
    return a["Исходный статус"].fillna("").astype(str).str.startswith("Принята")


def unit_kpis(a: pd.DataFrame) -> dict:
    tr = transferred_mask(a)
    st = a["Просрочка ДДУ"]
    nto = a[st.eq(NT_OVERDUE)]
    late = a[st.eq(LATE)]
    return {
        "units_total": int(len(a)),
        "transferred": int(tr.sum()),
        "not_transferred": int((~tr).sum()),
        "nt_overdue": int(len(nto)),
        "nt_overdue_kv": int(nto["Тип объекта"].eq("Квартира").sum()),
        "nt_overdue_median": float(nto["Просрочка ДДУ факт, дн."].median()) if len(nto) else 0.0,
        "late_transferred": int(len(late)),
        "late_median": float(late["Просрочка ДДУ факт, дн."].median()) if len(late) else 0.0,
        "ontime": int(st.eq(ONTIME).sum()),
        "no_ddu": int(st.eq(NO_DDU).sum()),
        "unsold": int(st.eq(UNSOLD).sum()),
        "ready_no_remarks": int((a["Исходный статус"].eq("Открыта к передаче")
                                 & a["Замечаний открыто"].eq(0)).sum()),
        "refusals": int((a["Мот. отказ / снятие готовности"].fillna(False) & ~tr).sum()),
    }


def units_state_at(a: pd.DataFrame, when: pd.Timestamp) -> dict:
    """Реконструкция на дату по датам ПА: сколько передано и сколько непереданных с нарушенным ДДУ."""
    acc = a["Дата принятия собственником"]
    tr_now = transferred_mask(a)
    tr_at = tr_now & acc.notna() & (acc <= when)
    ddu = a["Срок по ДДУ"]
    sold = ~a["Просрочка ДДУ"].isin([UNSOLD, NO_DDU])
    nt_over = (~tr_at) & sold & ddu.notna() & (ddu < when)
    kv = a["Тип объекта"].eq("Квартира")
    return {"transferred": int(tr_at.sum()), "nt_overdue": int(nt_over.sum()),
            "nt_overdue_kv": int((nt_over & kv).sum()), "mask_nt_kv": nt_over & kv}


def _pen_part(a, kind, price):
    x = a[a["Тип объекта"].eq(kind)]
    part = x[x["Просрочка ДДУ"].isin([NT_OVERDUE, LATE])]
    nt = x[x["Просрочка ДДУ"].eq(NT_OVERDUE)]
    up = float(part["Коэф. неустойки на 1 ₽ цены (верх)"].fillna(0).sum()) * price
    lo = float(part["Коэф. неустойки на 1 ₽ цены (низ)"].fillna(0).sum()) * price
    daily = float((nt["Ставка ЦБ на срок ДДУ, %"].fillna(0) / 100 / 150).sum()) * price
    return part, up, lo, daily, len(nt)


def penalty(a: pd.DataFrame, price: float = ILLUSTR_PRICE, price_mm: float = MM_PRICE,
            price_nhp: float = NHP_PRICE) -> dict:
    """Неустойка ч.2 ст.6 214-ФЗ: коэффициенты на 1 ₽ цены × расчётная цена.

    Основные суммы (accrued_up/lo, daily, by_korpus) — по квартирам. Машиноместа и кладовые считаются
    отдельно по своим расчётным ценам (*_mm, *_nhp); *_total — всё вместе. Коммерция не считается.
    """
    part, up, lo, daily, _ = _pen_part(a, "Квартира", price)
    _, up_mm, lo_mm, d_mm, n_mm = _pen_part(a, "Машиноместо", price_mm)
    _, up_nh, lo_nh, d_nh, n_nh = _pen_part(a, "НХП", price_nhp)
    by_k = (part.assign(
        up=part["Коэф. неустойки на 1 ₽ цены (верх)"].fillna(0) * price,
        lo=part["Коэф. неустойки на 1 ₽ цены (низ)"].fillna(0) * price,
        nt=part["Просрочка ДДУ"].eq(NT_OVERDUE))
        .groupby("Корпус", observed=True).agg(up=("up", "sum"), lo=("lo", "sum"), kv=("Объект", "size"),
                                              nt=("nt", "sum"))
        .reset_index())
    by_k["Корпус"] = by_k["Корпус"].astype(str)
    by_k = by_k.sort_values("up", ascending=False)
    n_com = int((a["Тип объекта"].eq("Нежилое") & a["Просрочка ДДУ"].eq(NT_OVERDUE)).sum())
    return {"accrued_up": up, "accrued_lo": lo, "daily": daily, "by_korpus": by_k,
            "daily_mm": d_mm, "accrued_mm": up_mm, "nt_mm": n_mm,
            "daily_nhp": d_nh, "accrued_nhp": up_nh, "nt_nhp": n_nh, "nt_commercial": n_com,
            "daily_nonres": d_mm + d_nh, "accrued_nonres": up_mm + up_nh,
            "daily_total": daily + d_mm + d_nh, "accrued_total": up + up_mm + up_nh}


def ready_overdue_daily(a: pd.DataFrame, price: float = ILLUSTR_PRICE) -> tuple[int, float]:
    """Готовые к передаче квартиры без замечаний с нарушенным ДДУ: штук и ₽/сутки неустойки."""
    m = (a["Исходный статус"].eq("Открыта к передаче") & a["Замечаний открыто"].eq(0)
         & a["Просрочка ДДУ"].eq(NT_OVERDUE) & a["Тип объекта"].eq("Квартира"))
    return int(m.sum()), float((a.loc[m, "Ставка ЦБ на срок ДДУ, %"].fillna(0) / 100 / 150).sum()) * price


def fmt_int(v) -> str:
    try:
        if v is None or pd.isna(v):
            return "—"
    except (TypeError, ValueError):
        pass
    return f"{int(round(float(v))):,}".replace(",", " ")


def fmt_money(v: float) -> str:
    v = float(v)
    if abs(v) >= 1e9:
        return f"{v/1e9:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " млрд ₽"
    if abs(v) >= 1e6:
        return f"{v/1e6:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " млн ₽"
    if abs(v) >= 1e3:
        return f"{v/1e3:.0f} тыс. ₽"
    return f"{v:.0f} ₽"


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def fmt_pct(v: float, d: int = 0) -> str:
    return f"{100*float(v):.{d}f}%".replace(".", ",")


def fmt_delta(v, good_when_down=True, unit="") -> tuple[str, str]:
    """Текст и класс цвета для изменения неделя к неделе."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "нет снимка прошлой недели", "flat"
    v = float(v)
    if abs(v) < 1e-9:
        return "без изменений", "flat"
    sign = "+" if v > 0 else "−"
    txt = f"{sign}{fmt_int(abs(v)) if not unit else unit(abs(v))}"
    bad = (v > 0) if good_when_down else (v < 0)
    return txt, "bad" if bad else "good"
