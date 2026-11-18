"""Расчётный и реальный риск, причины непередачи готовых, прогноз и решения уровня генерального директора.

Факты — из данных ЖК (статусы записи, дата записи, реестр официальных вызовов, замечания, подрядчики).
Модельные коэффициенты собраны здесь и в DEFAULT_K; их описание выводится в «Допущениях».
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import pf_core as C

# ---- модельные коэффициенты (в данных нет претензий, исков и выплат)
DEFAULT_K = dict(claim=0.35,   # доля неустойки, по которой собственники предъявляют претензии и иски
                 cut=0.50,     # на сколько в среднем суд снижает неустойку по ст. 333 ГК РФ
                 paid=0.25)    # доля ожидаемых выплат, уже выплаченная
BOOK_DAYS = 7          # запись в пределах 7 дней — «записан», позже — очередь на слоты приёмщиков
CALL_WAIT_DAYS = 30    # официальный вызов не старше 30 дней — ждём срок, старше — срок истёк
EXTRA_CAPACITY = 0.25  # доп. бригады приёмки: +25% к фактическому темпу передачи
CALL_RESPONSE = 0.50   # доля собственников, пришедших после официального вызова
UNILATERAL_SHARE = 0.90
REFUSAL_RESOLVED = 0.40
PRESSURE_SHARE = 0.25  # доля риска подрядчика, снимаемая удержаниями/штрафами за 4 недели
MONTH_W = 4
HORIZON_W = 104

REASONS = [
    ("booked", "Записаны на приёмку (в ближайшие 7 дней)"),
    ("queue", "Записаны позже 7 дней: очередь на слоты приёмщиков"),
    ("refused", "Приёмка была, акт не подписан (отказ)"),
    ("called", "Вызваны официально, ждём срок"),
    ("expired", "Срок официального вызова истёк"),
    ("silent", "Нет записи и вызова: не отвечают или не вызваны"),
]
REASON_KEYS = [k for k, _ in REASONS]


def ladder(up: float, lo: float, K: dict) -> dict:
    """Лесенка: расчётная неустойка (верхняя граница) → предъявлено → ожидаемые выплаты → уже выплачено."""
    claimed = up * K["claim"]
    expected = claimed * (1 - K["cut"])
    paid = expected * K["paid"]
    return dict(upper=up, lower=lo, claimed=claimed, expected=expected, paid=paid, left=expected - paid)


def ready_rows(A: pd.DataFrame) -> pd.DataFrame:
    return A[C.ready_mask(A) & A["Просрочка ДДУ"].eq(C.NT_OVERDUE) & A["Тип объекта"].eq("Квартира")]


def classify_ready(A: pd.DataFrame, price: float) -> dict:
    """Взаимоисключающие причины, по которым готовые квартиры не переданы: количество и риск в сутки по каждой."""
    r = ready_rows(A)
    rec = r["Статус записи собственника"].fillna("")
    days = r["Запись через, дн."]
    call = r["Официальный вызов, дн. назад"]
    planned = rec.isin(["Запланировано", "Демонстрация началась", "Демонстрация завершена"])
    refused = rec.isin(["Завершено", "Отменено", "Не состоялось"])
    cat = np.select(
        [refused, planned & (days > BOOK_DAYS), planned, call.notna() & (call <= CALL_WAIT_DAYS), call.notna()],
        ["refused", "queue", "booked", "called", "expired"], default="silent")
    rate = r["Ставка ЦБ на срок ДДУ, %"].fillna(0) / 100 / 150 * price
    out = {}
    for k in REASON_KEYS:
        m = cat == k
        out[k] = dict(n=int(m.sum()), risk=float(rate[m].sum()))
    return out


def simulate(n0: float, burn: float, r_unit: float, ready: float = 0.0, ready_weeks: int | None = None, cap: int = HORIZON_W) -> dict:
    """Недельная модель: остаток просрочки, накопленный риск. burn — чистый темп (минус приток), ready_weeks — сценарий «все готовые за N недель»."""
    n, acc, path, left = float(n0), 0.0, [(0, float(n0), 0.0)], float(ready)
    weeks = None
    for w in range(1, cap + 1):
        b = burn
        if ready_weeks and w <= ready_weeks and left > 0:
            b = max(burn, ready / ready_weeks)
            left = max(0.0, left - b)
        n2 = max(0.0, n - b)
        if n2 > 0.5 or b <= 0:
            acc += 7 * r_unit * (n + n2) / 2
        else:                                   # последняя неделя: остаток обнуляется на доле недели
            frac = min(1.0, n / b)
            acc += 7 * frac * r_unit * n / 2
            n2 = 0.0
        n = n2
        path.append((w, n, acc))
        if n <= 0.5:
            weeks = (w - 1) + (n / b if b > 0 else 1.0)
            break
    return dict(weeks=weeks, accrued=acc, path=path)


def forecast(p: dict, ready_weeks: int = 4) -> dict:
    """Прогноз по ЖК: срок закрытия просрочки при текущем темпе и ориентире, накопленный риск, сценарий «все готовые за N недель»."""
    n, burn = p["overdue_kv"], p["burn_pace"]
    r_unit = p["risk_day"] / n if n else 0.0
    base = simulate(n, burn, r_unit)
    tgt = simulate(n, p["target_burn"], r_unit)
    scn = simulate(n, burn, r_unit, ready=p["ready"], ready_weeks=ready_weeks)
    return dict(base=base, target=tgt, scn=scn, r_unit=r_unit, saving=base["accrued"] - scn["accrued"],
                saving_4w=_acc_at(base, MONTH_W) - _acc_at(scn, MONTH_W))


def _acc_at(sim: dict, w: int) -> float:
    path = sim["path"]
    return path[min(w, len(path) - 1)][2]


def portfolio_forecast(projects: list[dict], ready_weeks: int = 4) -> dict:
    fs = [forecast(p, ready_weeks) for p in projects]
    out = {}
    for key in ("base", "target", "scn"):
        L = max(len(f[key]["path"]) for f in fs)
        n = np.zeros(L); acc = np.zeros(L)
        for f in fs:
            pth = f[key]["path"]
            for i in range(L):
                j = min(i, len(pth) - 1)
                n[i] += pth[j][1]
                acc[i] += pth[j][2]
        closed = [f[key]["weeks"] for f in fs]
        out[key] = dict(weeks=(max(closed) if all(c is not None for c in closed) else None), accrued=float(acc[-1]),
                        path=[(i, float(n[i]), float(acc[i])) for i in range(L)])
    out["saving"] = out["base"]["accrued"] - out["scn"]["accrued"]
    out["saving_4w"] = sum(f["saving_4w"] for f in fs)
    return out


def contractor_risk(p: dict, ct: pd.DataFrame, n: int = 3) -> list[dict]:
    """Доля суточного риска ЖК на подрядчиках: риск просроченных квартир с открытыми замечаниями делится по числу квартир с замечаниями подрядчика."""
    big = ct[ct["Квартир"] > 0]
    tot = float(big["Квартир"].sum())
    if not len(big) or tot <= 0 or p["risk_day"] <= 0 or p["risk_blocked"] <= 0:
        return []
    out = []
    for _, r in big.sort_values("Квартир", ascending=False).head(n).iterrows():
        risk = p["risk_blocked"] * float(r["Квартир"]) / tot
        out.append(dict(name=r["Подрядчик"], risk=risk, share=risk / p["risk_day"], blocked=int(r["Блок. квартир"]), units=int(r["Квартир"]),
                        claim=float(r.get("Потенциал претензии, ₽", 0.0) or 0.0)))
    return out


def decisions(p: dict, ct: pd.DataFrame) -> list[dict]:
    """Решения уровня генерального директора по ЖК, каждое с эффектом в ₽ расчётного риска за 4 недели."""
    rs = p["reasons"]
    ready = max(p["ready"], 1)
    r_ready = p["ready_risk"] / ready
    out = []
    # 1. деньги и люди: дополнительные бригады приёмки
    extra = min(max(1, round(EXTRA_CAPACITY * p["week_fact"])), p["ready"] // MONTH_W)
    wait = rs["queue"]["n"] + rs["booked"]["n"]
    if extra > 0 and wait > 0:
        out.append(dict(key="crew", kind="Деньги, люди", title=f"Утвердить дополнительные бригады приёмки: +{C.fmt_int(extra)} передач в неделю",
                        short="Доп. бригады приёмки", roles=["Генеральный директор", "Финансовый директор", "Директор по заселению"],
                        effect=extra * r_ready * 56,
                        basis=f"{C.fmt_int(wait)} готовых квартир ждут слотов приёмки; темп сейчас {C.fmt_int(p['week_fact'])} в неделю"))
    # 2. полномочия: официальные вызовы
    n_sil = rs["silent"]["n"]
    if n_sil > 0:
        moved = round(CALL_RESPONSE * n_sil)
        out.append(dict(key="calls", kind="Полномочия", title=f"Разрешить массовые официальные вызовы по {C.fmt_int(n_sil)} готовым квартирам без записи",
                        short="Официальные вызовы без записи", roles=["Генеральный директор", "Юридический департамент", "Клиентский сервис"],
                        effect=moved * r_ready * 7,
                        basis=f"запись и вызов отсутствуют; после вызова приходит около {C.fmt_pct(CALL_RESPONSE)} собственников"))
    # 3. полномочия: односторонние акты
    n_exp = rs["expired"]["n"]
    if n_exp > 0:
        moved = round(UNILATERAL_SHARE * n_exp)
        out.append(dict(key="unilateral", kind="Полномочия", title=f"Разрешить односторонние акты по {C.fmt_int(n_exp)} официальным вызовам с истёкшим сроком",
                        short="Односторонние акты по истёкшим вызовам", roles=["Генеральный директор", "Юридический департамент"],
                        effect=moved * r_ready * 18, basis="срок по вызову истёк, собственник не пришёл"))
    # 4. люди: акты без подписи
    n_ref = rs["refused"]["n"]
    if n_ref > 0:
        moved = round(REFUSAL_RESOLVED * n_ref)
        out.append(dict(key="refused", kind="Люди", title=f"Выделить выездную группу по {C.fmt_int(n_ref)} приёмкам, где акт не подписан",
                        short="Группа по приёмкам без подписи", roles=["Директор по заселению", "Юридический департамент"],
                        effect=moved * r_ready * 14, basis="приёмка проведена или отменена, акт не подписан"))
    # 5. давление на подрядчика
    cr = p["contractor_risk"]
    if cr:
        c0 = cr[0]
        eff = PRESSURE_SHARE * c0["risk"] * 14
        out.append(dict(key="pressure", kind="Давление на подрядчика",
                        title=f"Включить удержания и штрафы по договору {c0['name']} за блокирующие замечания — на него {C.fmt_pct(c0['share'])} риска ЖК",
                        short=f"Удержания по договору {c0['name']}", roles=["Генеральный директор", "Договорной отдел", "Служба качества"],
                        effect=eff, basis=f"замечания в {C.fmt_int(c0['units'])} квартирах, блокирует {C.fmt_int(c0['blocked'])}; потенциал удержаний до {C.fmt_money(c0['claim'])}", claim=c0["claim"]))
    out.sort(key=lambda d: -d["effect"])
    return out
