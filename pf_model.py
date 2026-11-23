"""Портфель ЖК: расчёты для отчёта генерального директора.

Все ЖК считаются одним и тем же конвейером из одной схемы таблиц: помещения, замечания (свёртка), подрядчики.
Персональных данных нет: только счётчики, корпуса и роли исполнителей (без имён и сроков).
"""
from __future__ import annotations


import numpy as np
import pandas as pd

import pf_core as C
import pf_decide as DC
import pf_remstat as RS
import pf_stats

DASH = "—"
REPORT_SCHEMA = "v23"
PLAN_UPLIFT = 1.10       # план передачи за неделю = средний факт 4 предыдущих недель × 1,10
RISK_MATERIAL = 0.02     # изменение риска за 7 дней от 2% считаем существенным
WEEK0 = pd.Timestamp("2026-08-17")     # первая из 12 недель динамики (понедельник)
N_WEEKS = 12

# --- меры, ответственные роли и контрольные показатели (роли, без имён и сроков) ---
PROBLEMS = {
    "ready": dict(
        title="Готовые к передаче квартиры не переданы",
        action="Согласовать с собственниками графики передачи по списку готовых квартир",
        roles=("Дирекция по заселению", "Клиентский сервис"),
        metric="Число переданных квартир из списка; остаток готовых квартир без замечаний"),
    "keys": dict(
        title="Ключи не переданы в офис заселения",
        action="Подтвердить график передачи ключей в ОЗ по корпусам и устранить препятствия",
        roles=("Генподрядчик по отделке", "Стройконтроль"),
        metric="Число квартир с переданными в ОЗ ключами; остаток квартир без ключей"),
    "refusal": dict(
        title="Мотивированный отказ или снятие готовности",
        action="Проанализировать основания отказов, определить позицию по каждому типу и проверить условия одностороннего акта по ч. 6 ст. 8 214-ФЗ",
        roles=("Юридический департамент", "Дирекция по заселению"),
        metric="Число отказов с определённой позицией; остаток квартир в статусе «Не принята»"),
    "not_open": dict(
        title="Готовность к передаче не открыта",
        action="Установить причины, препятствующие открытию готовности, и закрепить их устранение за ответственной ролью",
        roles=("Стройконтроль", "Генподрядчик по отделке"),
        metric="Число квартир с открытой готовностью; остаток квартир без открытой готовности"),
    "remarks": dict(
        title="Открыта к передаче, но есть открытые замечания",
        action="Устранить замечания, начиная с критических, и повторно предъявить квартиры к приёмке",
        roles=("Генподрядчик по отделке", "Стройконтроль"),
        metric="Остаток открытых замечаний по этим квартирам"),
}

for _k, _s in {"ready": "Согласование графика передачи готовых квартир", "keys": "Подтверждение графика передачи ключей по корпусам",
               "refusal": "Определение позиции по мотивированным отказам", "not_open": "Устранение препятствий к открытию готовности",
               "remarks": "Устранение замечаний, начиная с критических"}.items():
    PROBLEMS[_k]["short"] = _s


def _rub_day(rate_pct, price: float) -> pd.Series | float:
    """Расчётная дневная экспозиция по квартире: 1/300 ключевой ставки × 2 (участник — гражданин) = ставка/100/150 × цена."""
    return rate_pct / 100 / 150 * price


def _kv_overdue(A: pd.DataFrame) -> pd.DataFrame:
    return A[A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].eq(C.NT_OVERDUE)]


def _korpusa_text(df: pd.DataFrame, n: int = 3) -> str:
    vc = df["Корпус"].astype(str).value_counts().head(n)
    return ", ".join(f"{k} — {C.fmt_int(v)}" for k, v in vc.items()) or DASH


def _real_groups(kv: pd.DataFrame, cd: pd.Timestamp, price: float) -> list[dict]:
    st_ = kv["Исходный статус"].fillna("")
    rem = kv["Замечаний открыто"].fillna(0)
    masks = {
        "ready": C.ready_mask(kv),
        "remarks": st_.eq("Открыта к передаче") & rem.gt(0),
        "keys": st_.eq("Ключи в ОЗ не переданы"),
        "refusal": st_.eq("Не принята"),
        "not_open": st_.eq("В ОЗ, готовность не открыта") | (st_.eq("Открыта к передаче") & rem.eq(0) & ~C.ready_mask(kv)),
    }
    out = []
    for key, m in masks.items():
        g = kv[m]
        if not len(g):
            continue
        risk = float(_rub_day(g["Ставка ЦБ на срок ДДУ, %"].fillna(0), price).sum())
        if key == "ready":
            rec = g["Статус записи собственника"].fillna("")
            cause = (f"Статус «Открыта к передаче», открытых замечаний 0; запись собственника: "
                     f"запланирована у {C.fmt_int((rec == 'Запланировано').sum())}, "
                     f"нет записи у {C.fmt_int((rec == '').sum())}")
        elif key == "keys":
            pl = g["Плановая дата ключей в ОЗ"]
            cause = (f"Статус «Ключи в ОЗ не переданы»; плановая дата ключей в ОЗ ещё впереди у "
                     f"{C.fmt_int((pl > cd).sum())}, уже прошла у {C.fmt_int((pl <= cd).sum())}, "
                     f"не указана у {C.fmt_int(pl.isna().sum())}")
        elif key == "refusal":
            cause = (f"Статус «Не принята»; отметка «мотивированный отказ / снятие готовности» у "
                     f"{C.fmt_int(g['Мот. отказ / снятие готовности'].fillna(False).sum())}")
        elif key == "not_open":
            cause = "Статус «В ОЗ, готовность не открыта» либо готовность не подтверждена"
        else:
            cause = (f"Открытых замечаний у этих квартир {C.fmt_int(g['Замечаний открыто'].sum())}, "
                     f"критических {C.fmt_int(g['Критических'].sum())}")
        with_remarks = g[g["Замечаний открыто"].gt(0)]
        out.append(dict(key=key, title=PROBLEMS[key]["title"], n=int(len(g)), risk=risk, korpusa=_korpusa_text(g), cause=cause,
                        with_remarks_n=len(with_remarks),
                        with_remarks_risk=float(_rub_day(with_remarks["Ставка ЦБ на срок ДДУ, %"].fillna(0), price).sum()),
                        baseline=int(len(g)) if key != "remarks" else int(g["Замечаний открыто"].sum())))
    return out


def _top_contractors(ct: pd.DataFrame, n: int = 2) -> list[str]:
    big = ct[ct["Замечаний"] >= 50].sort_values("Балл риска", ascending=False)
    return big["Подрядчик"].head(n).tolist()


def _problem_rows(groups: list[dict], total_risk: float, total_n: int) -> list[dict]:
    rows = []
    for g in sorted(groups, key=lambda x: -x["risk"])[:3]:
        t = PROBLEMS[g["key"]]
        rows.append(dict(
            key=g["key"], title=t["title"], n=g["n"], share_n=g["n"] / total_n if total_n else 0.0,
            risk=g["risk"], share_risk=g["risk"] / total_risk if total_risk else 0.0,
            korpusa=g["korpusa"], cause=g["cause"], action=t["action"], roles=list(t["roles"]),
            metric=t["metric"], baseline=g["baseline"], short=t["short"]))
    return rows


def weekly(A: pd.DataFrame, cd: pd.Timestamp, observed_through: pd.Timestamp | None = None, *, align_to_cutoff: bool = False) -> pd.DataFrame:
    """12 недель: передано (квартиры / все помещения) по датам передаточных актов и просрочка по ДДУ (квартиры) на конец недели."""
    tr = C.transferred_mask(A)
    acc = A["Дата принятия собственником"]
    act_kind = A.get("Односторонний ПА", pd.Series(pd.NA, index=A.index, dtype="boolean"))
    unilateral = act_kind.eq(True).fillna(False)
    bilateral = act_kind.eq(False).fillna(False)
    kv = A["Тип объекта"].eq("Квартира")
    cutoff = observed_through if observed_through is not None else cd - pd.Timedelta(days=5)
    start = cutoff - pd.Timedelta(days=7 * N_WEEKS - 1) if align_to_cutoff else WEEK0
    rows = []
    for i in range(N_WEEKS):
        ws = start + pd.Timedelta(days=7 * i)
        we = ws + pd.Timedelta(days=6)
        m = tr & acc.ge(ws) & acc.lt(ws + pd.Timedelta(days=7))
        if observed_through is not None:
            m &= acc.le(cutoff)
        st = C.units_state_at(A, min(we, cd, observed_through) if observed_through is not None else min(we, cd))
        rows.append({"ws": ws, "Неделя": f"{ws:%d.%m}–{we:%d.%m}", "Передано, квартир": int((m & kv).sum()),
                     "По двусторонним ПА": int((m & kv & bilateral).sum()),
                     "По односторонним ПА": int((m & kv & unilateral).sum()), "Передано, всего": int(m.sum()),
                     "Просрочка на конец недели, квартир": int(st["nt_overdue_kv"]), "partial": bool(we > cutoff)})
    return pd.DataFrame(rows)


def comparison_cutoff(d: dict) -> pd.Timestamp:
    if d.get("observed_through") is not None:
        return min(d["calc_date"], d["observed_through"])
    last_act = d["units"]["Дата принятия собственником"].max()
    return min(d["calc_date"], last_act) if pd.notna(last_act) else d["calc_date"]


def project(d: dict, P: dict, K: dict | None = None, *, comparison_date: pd.Timestamp | None = None) -> dict:
    """Все показатели одного ЖК: один набор для каждого сегмента портфеля."""
    A, cd = d["units"], d["calc_date"]
    price = P["price"]
    u = C.unit_kpis(A)
    pen = C.penalty(A, **P)
    ready_n, ready_daily = C.ready_overdue_daily(A, price)
    kv = _kv_overdue(A)
    ad = comparison_date if comparison_date is not None else comparison_cutoff(d)
    wk = weekly(A, cd, ad, align_to_cutoff=d.get("observed_through") is not None)
    full = wk[~wk["partial"]]
    last = full.iloc[-1] if len(full) else {"Передано, квартир": 0, "Передано, всего": 0}
    prev = full.iloc[-2] if len(full) > 1 else None
    K = {**DC.DEFAULT_K, **(K or {})}
    rate = _rub_day(A["Ставка ЦБ на срок ДДУ, %"].fillna(0), price)
    sts = [C.units_state_at(A, ad - pd.Timedelta(days=7 * k)) for k in range(6)]
    ms = [x["mask_nt_kv"] for x in sts]
    Ns = [int(x["nt_overdue_kv"]) for x in sts]
    Rs = [float(rate[m_].sum()) for m_ in ms]
    now_kv, wk_kv = Ns[0], Ns[1]
    m_now, m_prev = ms[0], ms[1]
    left, entered = m_prev & ~m_now, m_now & ~m_prev
    risk_delta = Rs[0] - Rs[1]
    gross_left = [int((ms[k + 1] & ~ms[k]).sum()) for k in range(5)]
    inflow = [int((ms[k] & ~ms[k + 1]).sum()) for k in range(5)]
    burn_w = [Ns[k + 1] - Ns[k] for k in range(5)]                  # чистое сокращение просрочки за неделю k (0 — последняя)
    burn_pace = float(np.mean(burn_w[:4]))
    target_burn = max(0.0, float(np.mean(burn_w[1:5]))) * PLAN_UPLIFT
    r_start = Rs[1] / Ns[1] if Ns[1] else 0.0
    risk_target = -target_burn * r_start
    base4 = full["Передано, квартир"].iloc[-5:-1]
    week_plan = int(round(float(base4.mean()) * PLAN_UPLIFT)) if len(base4) else None
    due = A["Срок по ДДУ"]
    next_week_due = (~C.transferred_mask(A) & A["Тип объекта"].eq("Квартира")
                     & ~A["Просрочка ДДУ"].isin([C.UNSOLD, C.NO_DDU])
                     & due.ge(cd) & due.lt(cd + pd.Timedelta(days=7)))
    groups = _real_groups(kv, cd, price)
    rem = d["remarks"]
    n_rem = int(A["Замечаний открыто"].sum())
    rm = lambda m: int(rem.loc[m, "n"].sum())
    ct = d["contractors"]
    p = dict(
        name=d["name"], key=d["key"], groups=groups, weekly=wk,
        overdue_kv=u["nt_overdue_kv"], overdue_all=u["nt_overdue"], ready=ready_n,
        risk_day=pen["daily"], risk_day_total=pen["daily_total"], ready_risk=ready_daily,
        accrued_lo=pen["accrued_lo"], accrued_up=pen["accrued_up"], penalty=pen,
        median_days=u["nt_overdue_median"], units=u["units_total"], units_kv=int(A["Тип объекта"].eq("Квартира").sum()),
        transferred=u["transferred"], late_transferred=u["late_transferred"], refusals=u["refusals"],
        week_fact=int(last["Передано, квартир"]), week_all=int(last["Передано, всего"]),
        week_pa_bilateral=int(last.get("По двусторонним ПА", 0)),
        week_pa_unilateral=int(last.get("По односторонним ПА", 0)),
        week_prev=int(prev["Передано, квартир"]) if prev is not None else None,
        overdue_delta=int(now_kv - wk_kv), overdue_week_current=int(now_kv), overdue_prev=int(wk_kv),
        risk_delta=risk_delta, risk_prev=Rs[1], risk_week_current=Rs[0], risk_target=risk_target,
        risk_vs_target=risk_delta - risk_target, burn_pace=burn_pace, target_burn=target_burn, gross_left=float(np.mean(gross_left[:4])),
        inflow=float(np.mean(inflow[:4])), act_date=ad, price=price,
        left_n=int(left.sum()), left_risk=float(rate[left].sum()), entered_n=int(entered.sum()), entered_risk=float(rate[entered].sum()),
        week_plan=week_plan, week_dev=(int(last["Передано, квартир"]) - week_plan) if week_plan is not None else None,
        week_plan_next=int(round(float(full["Передано, квартир"].tail(4).mean()) * PLAN_UPLIFT)) if len(full) else 0,
        next_week_new=int(next_week_due.sum()), next_week_new_risk=float(rate[next_week_due].sum()),
        has_risk=True,
        remarks=n_rem, critical=int(A["Критических"].sum()), remarks_over=int(A["Просрочено (регл)"].sum()),
        blocking=rm(rem["Блокирует"]), remarks_cost=n_rem * pf_stats.COST_PER_REMARK,
        claim_potential=float(ct["Потенциал претензии, ₽"].sum()) if "Потенциал претензии, ₽" in ct else 0.0,
        top_contractors=_top_contractors(ct), blocking_units=int(A.loc[~C.transferred_mask(A) & (A["Критических"] > 0), "Объект"].nunique()),
        problems=_problem_rows(groups, pen["daily"], u["nt_overdue_kv"]),
        korpusa_top=_korpusa_text(kv, 5),
        by_korpus=(kv.assign(r=_rub_day(kv["Ставка ЦБ на срок ДДУ, %"].fillna(0), price), k=kv["Корпус"].astype(str))
                   .groupby("k").agg(n=("Объект", "size"), risk=("r", "sum")).reset_index().sort_values("risk", ascending=False)),
    )
    p["risk_blocked"] = sum(group["with_remarks_risk"] for group in groups)
    p["reasons"] = DC.classify_ready(A, price)
    p["ladder"] = DC.ladder(pen["accrued_up"], pen["accrued_lo"], K)
    p["contractor_risk"] = DC.contractor_risk(p, ct)
    p["rem"] = RS.compute(A, d["key"])
    p["cands"] = DC.candidates(p, ct, d["remarks"])
    p["decisions"] = DC.pick(p["cands"])
    p["forecast"] = DC.forecast(p)
    p["trend"] = [int(x) for x in wk["Просрочка на конец недели, квартир"]]
    p["capacity"] = int(full["Передано, квартир"].iloc[-8:].max()) if len(full) else 0
    return p


DEFAULT_PRICES = {"bunino": 10.0, "proksh": 8.7, "zen": 12.4, "desn": 8.2, "scandc": 9.4, "yuzh": 8.8, "vsev": 6.4, "lag": 6.9, "zorge": 15.2, "scands": 9.9}   # млн ₽ за квартиру; цен ДДУ в данных нет — допущение по каждому ЖК


def build(D: dict, P: dict, K: dict | None = None) -> dict:
    """P: price (по умолчанию для всех ЖК), prices — {папка: цена, ₽} для отдельных ЖК; K — коэффициенты лесенки."""
    prices = P.get("prices") or {}
    projects = []
    comparison_date = min(map(comparison_cutoff, D.values()), default=None)
    for d in D.values():
        Pk = dict(price=prices.get(d["key"], P["price"]), price_mm=P["price_mm"], price_nhp=P["price_nhp"])
        projects.append(project(d, Pk, K, comparison_date=comparison_date))
    assign_decisions(projects)
    return dict(projects=projects, totals=totals(projects))


def assign_decisions(projects: list[dict], skip: tuple = ("crew",)) -> None:
    """Главные решения всех ЖК различны: ЖК обрабатываются по убыванию эффекта лучшей меры, при равенстве — по дневной неустойке. Каждый получает наиболее результативную из ещё не использованных мер.
    Вторая смена приёмки проверяется отдельно перед согласованием и главным решением не назначается."""
    used: set = set()
    eligible = {p["key"]: [c for c in p["cands"] if c["key"] not in skip] for p in projects}
    ordered = sorted(by_risk(projects), key=lambda p: -max((c["effect_day"] for c in eligible[p["key"]]), default=0))
    for p in ordered:
        p["decisions"] = DC.pick(eligible[p["key"]], used)
        if p["decisions"]:
            used.add(p["decisions"][0]["key"])


def totals(projects: list[dict]) -> dict:
    def s(key):
        return sum(p[key] for p in projects)

    top = max(projects, key=lambda p: p["risk_day"]) if projects else None
    wk_prev = [p["week_prev"] for p in projects]
    return dict(
        overdue_kv=s("overdue_kv"), ready=s("ready"), risk_day=s("risk_day"), ready_risk=s("ready_risk"),
        accrued_up=s("accrued_up"), accrued_lo=s("accrued_lo"), week_fact=s("week_fact"), overdue_delta=s("overdue_delta"),
        week_prev=(sum(wk_prev) if all(x is not None for x in wk_prev) else None),
        week_pa_bilateral=s("week_pa_bilateral"), week_pa_unilateral=s("week_pa_unilateral"),
        risk_delta=s("risk_delta"), risk_prev=s("risk_prev"), overdue_prev=s("overdue_prev"),
        overdue_week_current=s("overdue_week_current"), left_n=s("left_n"), left_risk=s("left_risk"),
        entered_n=s("entered_n"), entered_risk=s("entered_risk"), week_plan=s("week_plan"),
        risk_target=s("risk_target"), burn_pace=s("burn_pace"), target_burn=s("target_burn"), gross_left=s("gross_left"), inflow=s("inflow"),
        ladder={k: sum(p["ladder"][k] for p in projects) for k in projects[0]["ladder"]} if projects else {},
        reasons={k: dict(n=sum(p["reasons"][k]["n"] for p in projects), risk=sum(p["reasons"][k]["risk"] for p in projects)) for k in DC.REASON_KEYS},
        capacity=s("capacity"), rem=RS.combine([p["rem"] for p in projects]) if projects else {},
        remarks=s("remarks"), critical=s("critical"), remarks_over=s("remarks_over"), blocking=s("blocking"),
        remarks_cost=s("remarks_cost"), claim_potential=s("claim_potential"), units=s("units"), units_kv=s("units_kv"),
        transferred=s("transferred"),
        top=top, n=len(projects),
        top_share=(top["risk_day"] / s("risk_day")) if top and s("risk_day") else 0.0,
    )


def table(projects: list[dict], sort: str = "risk") -> pd.DataFrame:
    tr = sum(p["risk_day"] for p in projects) or 1.0
    rows = []
    for p in projects:
        pr = p["problems"][0] if p["problems"] else None
        rows.append({
            "ЖК": p["name"],
            "Передано за неделю, квартир": p["week_fact"],
            "Просрочка по ДДУ, квартир": p["overdue_kv"],
            "Из них готовы": p["ready"],
            "Доля готовых, %": round(100 * p["ready"] / p["overdue_kv"], 1) if p["overdue_kv"] else 0.0,
            "Расчётная дневная экспозиция, ₽": round(p["risk_day"]),
            "Доля в экспозиции портфеля, %": round(100 * p["risk_day"] / tr, 1),
            "Открытых замечаний": p["remarks"],
            "Главная проблема": (pr["title"] + f" — {C.fmt_int(pr['n'])} {C.plural(pr['n'], 'квартира', 'квартиры', 'квартир')}") if pr else DASH,
            "Предлагаемая мера": pr["action"] if pr else DASH,
            "_name": p["name"],
        })
    df = pd.DataFrame(rows)
    col = {"risk": "Расчётная дневная экспозиция, ₽", "overdue": "Просрочка по ДДУ, квартир"}.get(sort)
    if col:
        df = df.sort_values(col, ascending=False, kind="stable")
    return df.reset_index(drop=True)


def portfolio_messages(tot: dict, projects: list[dict]) -> tuple[str, list[str]]:
    """Главный вывод и ключевые сообщения по ПОРТФЕЛЮ в целом (ЖК — равные сегменты)."""
    n, rd = tot["overdue_kv"], tot["risk_day"]
    if not projects or not n:
        return "Просрочки по ДДУ в портфеле нет", []
    kw = lambda x: f"{C.fmt_int(x)} {C.plural(x, 'квартира', 'квартиры', 'квартир')}"
    head = (f"Портфель: просрочена передача {kw(n)} по ДДУ, ≈{C.fmt_money(rd)} расчётной дневной экспозиции; "
            f"{C.fmt_pct(tot['ready'] / n)} просрочки закрывается передачей готовых квартир")
    msgs = [f"Готовы к передаче {kw(tot['ready'])} составляют {C.fmt_money(tot['ready_risk'])} дневной экспозиции "
            f"({C.fmt_pct(tot['ready_risk'] / rd if rd else 0)}): наиболее быстрый эффект даёт управленческое решение по этой группе.",
            f"Остаток замечаний — {C.fmt_int(tot['remarks'])}, из них {C.fmt_pct(tot['remarks_over'] / tot['remarks'] if tot['remarks'] else 0)} "
            f"просрочены по регламенту; критических — {C.fmt_int(tot['critical'])}."]
    return head, msgs


# ---------------------------------------------------------------- первый экран
def by_risk(projects: list[dict]) -> list[dict]:
    """ЖК по убыванию риска; ЖК без оценки риска — внизу."""
    return sorted(projects, key=lambda p: (not p.get("has_risk", True), -(p.get("risk_day") or 0.0)))


def risk_change(tot: dict, projects: list[dict]) -> tuple[bool, str]:
    """Отдельное пояснение изменения риска за неделю в деньгах и относительно целевого темпа (по образцу «significant item»)."""
    prev = tot["risk_prev"]
    d, tgt = tot["risk_delta"], tot["risk_target"]
    pct = d / prev if prev else 0.0
    material = abs(pct) >= RISK_MATERIAL
    diff = d - tgt                                  # отрицательное = риск снижается быстрее целевого темпа
    mv = max(projects, key=lambda p: abs(p["risk_delta"]))
    sg = lambda x: ("+" if x > 0 else "−" if x < 0 else "") + C.fmt_k(abs(x))
    verdict = ("опережение целевого темпа на " + C.fmt_k(abs(diff))) if diff < 0 else ("отставание от целевого темпа на " + C.fmt_k(abs(diff))) if diff > 0 else "строго в целевом темпе"
    txt = (f"За неделю расчётная экспозиция {'снизилась' if d < 0 else 'выросла' if d > 0 else 'не изменилась'}"
           + (f" на {C.fmt_k(abs(d))} в день ({C.fmt_pct(abs(pct), 1)} к началу недели)" if d else "")
           + f": вышли из просрочки {C.fmt_int(tot['left_n'])} {C.plural(tot['left_n'], 'квартира', 'квартиры', 'квартир')} (−{C.fmt_k(tot['left_risk'])}), "
           f"новые просрочки {C.fmt_int(tot['entered_n'])} {C.plural(tot['entered_n'], 'квартира', 'квартиры', 'квартир')} (+{C.fmt_k(tot['entered_risk'])}). "
           f"Целевой темп недели — {sg(tgt)} в день (средняя динамика четырёх предыдущих недель с запасом 10%): итог — {verdict}. "
           f"Наибольшее изменение — {mv['name']}: {sg(mv['risk_delta'])} в день.")
    return material, txt


def vs_target(p: dict) -> tuple[str, bool]:
    """Изменение риска за неделю относительно целевого темпа: текст и признак отставания."""
    d, t = p["risk_delta"], p["risk_target"]
    diff = d - t
    sg = lambda x: ("+" if x > 0 else "−" if x < 0 else "") + C.fmt_k(abs(x))
    txt = f"{sg(d)} при целевом темпе {sg(t)}: " + ("опережение" if diff < 0 else "отставание" if diff > 0 else "в рамках целевого темпа")
    return txt, diff > 0


def priority(projects: list[dict], *, preferred_key: str | None = None) -> dict | None:
    """Выбранный управленческий приоритет или ЖК с наибольшей расчётной неустойкой за день."""
    ranked = [p for p in by_risk(projects) if p.get("has_risk", True)]
    if not ranked:
        return None
    p = (ranked[0] if preferred_key is None
         else next((project for project in ranked if project.get("key") == preferred_key), ranked[0]))
    tot_risk = sum(x["risk_day"] for x in ranked) or 1.0
    pr = p["problems"][0] if p["problems"] else None
    if pr:
        cause = (f"{pr['title']}: {C.fmt_int(pr['n'])} {C.plural(pr['n'], 'квартира', 'квартиры', 'квартир')}, ≈{C.fmt_k(pr['risk'])} в день ({C.fmt_pct(pr['share_risk'])} экспозиции ЖК). {pr['cause']}.")
    else:
        cause = "Просрочки по ДДУ нет: риск формируется только накопленной неустойкой по уже переданным квартирам."
    rs = p["reasons"]
    top_r = max(DC.REASONS, key=lambda kv: rs[kv[0]]["n"])
    drivers = [f"Доминирующая причина непередачи готовых квартир: «{top_r[1].lower()}» — {C.fmt_int(rs[top_r[0]]['n'])} из {C.fmt_int(p['ready'])} квартир.",
               f"Блокирующих замечаний {C.fmt_int(p['blocking'])}; у {C.fmt_int(p['blocking_units'])} непереданных помещений есть критические замечания."]
    if p["contractor_risk"]:
        drivers.append("Доля подрядчиков в экспозиции ЖК: " + "; ".join(f"{c['name']} — {C.fmt_pct(c['share'], 1)}" for c in p["contractor_risk"][:3]) + ".")
    decs = p["decisions"][:3]
    return dict(project=p, name=p["name"], risk_day=p["risk_day"], accrued_up=p["accrued_up"], share=p["risk_day"] / tot_risk,
                cause=cause, drivers=drivers, decisions=decs,
                decision=decs[0]["title"] if decs else "Сохранение темпа передачи и контроль сроков по ДДУ",
                roles=decs[0]["roles"] if decs else ["Дирекция по заселению"])


def table_rows(projects: list[dict], style_bad: str = "") -> list[list]:
    """Строки таблицы первого экрана: одна на ЖК, по убыванию риска."""
    ranked = by_risk(projects)
    tr = sum(p["risk_day"] for p in ranked if p.get("has_risk", True)) or 1.0
    f, fm = C.fmt_int, C.fmt_k
    sg = lambda x: ("+" if x > 0 else "−" if x < 0 else "") + f(abs(x))
    rows = []
    for p in ranked:
        ok = p.get("has_risk", True)
        ch_t, bad = vs_target(p) if ok else (DASH, False)
        pf_ = (f"{f(p['week_fact'])} / {f(p['week_plan'])} ({sg(p['week_dev'])})" if p.get("week_plan") is not None else f(p["week_fact"]))
        dec = p["decisions"][0] if p.get("decisions") else None
        dec_t = f"{dec['short']}: −{fm(dec['effect'])} риска за 4 нед." if dec else "Сохранять темп передачи"
        rows.append([p["name"], f(p["overdue_kv"]), f(p["ready"]), (f(round(p["risk_day"])) if ok else DASH),
                     (f(round(p["risk_day"] / p["overdue_kv"])) if ok and p["overdue_kv"] else DASH),
                     (C.fmt_pct(p["risk_day"] / tr, 1) if ok else DASH), (ch_t, style_bad if bad else ""), pf_, dec_t])
    return rows


def headline(projects: list[dict], tot: dict) -> str:
    """Вывод одной фразой для верха экрана."""
    pr = priority(projects)
    if not pr:
        return "Просрочки по ДДУ в портфеле нет"
    worse = sum(1 for p in projects if p["risk_vs_target"] > 0)
    p = pr["project"]
    s = (f"Наибольшая расчётная экспозиция — {pr['name']}: {C.fmt_money(pr['risk_day'])} в день ({C.fmt_pct(pr['share'])} портфеля); просрочена передача {C.fmt_int(p['overdue_kv'])} квартир, "
         f"из них готовы к передаче {C.fmt_int(p['ready'])}.")
    s += f" С отставанием от целевой динамики за неделю — {worse} из {len(projects)} ЖК."
    return s


def screen_rows(projects: list[dict]) -> list[dict]:
    """Строки таблицы первого экрана (по убыванию риска) в виде данных для вёрстки."""
    ranked = by_risk(projects)
    tr = sum(p["risk_day"] for p in ranked) or 1.0
    rows = []
    for p in ranked:
        dec = p["decisions"][0] if p.get("decisions") else None
        rs = p["rem"]
        rows.append(dict(name=p["name"], key=p["key"], over=p["overdue_kv"], d_over=p["overdue_delta"], ready=p["ready"], risk=p["risk_day"], share=p["risk_day"] / tr,
                         worse=p["risk_vs_target"] > 0, vs=vs_target(p)[0], trend=p["trend"], left=rs["left_cum"], fixed_pct=rs["fixed"] / rs["total"] if rs["total"] else 0.0,
                         decision=(dec["short"] if dec else "Сохранение текущего темпа передачи"), dec_day=(dec["effect_day"] if dec else 0.0), dec_4w=(dec["effect"] if dec else 0.0)))
    return rows


def composition(projects: list[dict]) -> list[dict]:
    """Проблемная часть портфеля: доля просроченных квартир сейчас и 7 дней назад; из них готовы."""
    out = []
    for p in projects + [dict(name="Портфель", units_kv=sum(x["units_kv"] for x in projects), overdue_kv=sum(x["overdue_kv"] for x in projects),
                              overdue_prev=sum(x["overdue_prev"] for x in projects), ready=sum(x["ready"] for x in projects), total=True)]:
        kv = max(p["units_kv"], 1)
        out.append(dict(name=p["name"], now=p["overdue_kv"] / kv, prev=p["overdue_prev"] / kv, ready=p["ready"] / kv, total=p.get("total", False),
                        n=p["overdue_kv"], units=p["units_kv"]))
    return out
