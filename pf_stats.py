"""Агрегаты по замечаниям: возрастные корзины, свёртка замечаний и рейтинг подрядчиков.

Одинаковые функции используются для всех ЖК, поэтому показатели сопоставимы. Только счётчики и названия подрядчиков без реквизитов.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COST_PER_REMARK = 4222.16          # расчётная стоимость устранения одного замечания, ₽ (оценка)
CLAIM_MULT = 3                     # потенциал претензии по просроченным: 3× расходов
WEEK_BINS = 12                     # последние 12 недель — по неделям; дальше укрупнённые корзины
LATE_BINS = {12: "12–25 нед.", 13: "26–51 нед.", 14: "52+ нед."}


def age_bin(age_days) -> np.ndarray:
    w = (np.asarray(age_days) // 7).astype(int)
    return np.where(w < WEEK_BINS, w, np.where(w < 26, 12, np.where(w < 52, 13, 14)))


def remark_agg(df: pd.DataFrame) -> pd.DataFrame:
    """df: Корпус, Группа, Важность, Подрядчик, Возраст, Просрочено45, Блокирует (по одному замечанию)."""
    x = df.assign(Нед=age_bin(df["Возраст"]), n=1)
    keys = ["Корпус", "Группа", "Важность", "Подрядчик", "Нед", "Просрочено45", "Блокирует"]
    out = x.groupby(keys, observed=True, as_index=False)["n"].sum()
    out["Корпус"] = out["Корпус"].astype(str)
    return out


def risk_score(o: float, avg: float, crit: float, blk: float, n: int) -> float:
    s = 25.3 * o + 5.4 * min(avg / 300, 1.5) + 90.6 * crit + 21.0 * min(blk, 50) / 50 + 57.1 * np.log10(max(n, 1)) / 4.5 - 33.0
    return float(np.clip(s, 0, 100))


def risk_class(score: float, n: int) -> str:
    if n < 50:
        return "мало данных"
    return "высокий" if score >= 60 else "средний" if score >= 30 else "низкий"


def contractor_table(df: pd.DataFrame) -> pd.DataFrame:
    """df — по одному замечанию: Объект, Группа, Важность, Подрядчик, Возраст, Просрочено45, Блокирует, Повтор."""
    rows = []
    for name, g in df.groupby("Подрядчик", observed=True):
        n = len(g)
        over = g[g["Просрочено45"]]
        crit = int(g["Важность"].eq("Критическое").sum())
        avg = float((over["Возраст"] - 45).mean()) if len(over) else 0.0
        blk = int(g.loc[g["Блокирует"], "Объект"].nunique())
        o = len(over) / n
        score = risk_score(o, avg, crit / n, blk, n)
        rows.append({
            "Подрядчик": name, "Группа": g["Группа"].mode().iat[0], "Замечаний": n, "Квартир": int(g["Объект"].nunique()),
            "Просрочено": len(over), "Ср_просрочка": avg, "Макс_просрочка": int((over["Возраст"] - 45).max()) if len(over) else 0,
            "Критических": crit, "Повторов": int(g["Повтор"].sum()), "Новых_4нед": int((g["Возраст"] < 28).sum()),
            "Блок. квартир": blk, "% просрочено": o, "% критич.": crit / n,
            "Балл риска": round(score * (min(1, n / 50) if n < 50 else 1), 1), "Класс риска": risk_class(score, n),
            "Оценка стоимости открытых, ₽": round(n * COST_PER_REMARK),
            "Потенциал претензии, ₽": round(CLAIM_MULT * COST_PER_REMARK * len(over)),
        })
    return pd.DataFrame(rows).sort_values("Балл риска", ascending=False).reset_index(drop=True)
