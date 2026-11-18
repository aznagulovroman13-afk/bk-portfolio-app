"""Портфель ЖК: расчёты для отчёта генерального директора (отдельный продукт, не часть отчёта по Бунинским).

Факт — только Бунинские кварталы (реальные данные проекта, те же функции, что и в действующем отчёте).
Прокшино и Дзен-кварталы — условные цифры (ДЕМО), всегда помечены и в «Только факт» не участвуют.
Персональных данных нет: только счётчики, корпуса и роли исполнителей (без имён и сроков).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import pf_core as C

REAL_NAME = "Бунинские кварталы"
NO_DATA = "Нет данных"
DEMO_TAG = "ДЕМО"

# --- условные (ДЕМО) исходные цифры: не из данных, служат только для показа структуры раздела ---
DEMO_PROJECTS = (
    dict(name="Прокшино", overdue_kv=214, week_fact=38, week_plan=55, week_prev=41, overdue_prev=231,
         groups=dict(ready=61, keys=88, refusal=27, not_open=38), korpusa=("К.3", "К.5", "К.1"),
         claims=31_000_000, confirmed=9_000_000),
    dict(name="Дзен-кварталы", overdue_kv=96, week_fact=22, week_plan=20, week_prev=19, overdue_prev=101,
         groups=dict(ready=12, keys=41, refusal=9, not_open=34), korpusa=("К.2", "К.4"),
         claims=8_500_000, confirmed=3_000_000),
)
DEMO_DAYS = 120   # условная средняя просрочка для накопленной суммы ДЕМО-ЖК, дн.

# --- что делать, кого подключить, что проверять на следующем совещании (роли, без имён и сроков) ---
PROBLEMS = {
    "ready": dict(
        title="Готовы к передаче, но не переданы",
        action="Проверить список готовых квартир и согласовать ближайшие окна передачи с собственниками",
        roles=("Отдел заселения", "Клиентский сервис"),
        metric="Сколько квартир из списка передано и сколько готовых без замечаний осталось"),
    "keys": dict(
        title="Ключи не переданы в ОЗ (стройготовность)",
        action="Подтвердить график передачи ключей в ОЗ по корпусам и снять препятствия",
        roles=("Генподрядчик по отделке", "Стройконтроль"),
        metric="Сколько квартир получили ключи в ОЗ и сколько осталось без ключей"),
    "refusal": dict(
        title="Мотивированный отказ или снятие готовности",
        action="Разобрать основания отказов, согласовать позицию по каждому типу и проверить право на односторонний акт",
        roles=("Юридический отдел", "Отдел заселения"),
        metric="Сколько отказов с принятой позицией и сколько квартир осталось в статусе «Не принята»"),
    "not_open": dict(
        title="Готовность к передаче не открыта",
        action="Определить, что мешает открыть готовность, и закрепить снятие барьера за ролью",
        roles=("Стройконтроль", "Генподрядчик по отделке"),
        metric="Сколько квартир получили открытую готовность и сколько осталось"),
    "remarks": dict(
        title="Открыта к передаче, но есть открытые замечания",
        action="Закрыть замечания, начиная с критических, и повторно предъявить квартиры к приёмке",
        roles=("Генподрядчик по отделке", "Стройконтроль"),
        metric="Сколько открытых замечаний осталось у этих квартир"),
}


def _rub_day(rate_pct, price: float) -> pd.Series | float:
    """Расчётный риск за сутки по квартире: 1/300 ключевой ставки × 2 (гражданин) = ставка/100/150 × цена."""
    return rate_pct / 100 / 150 * price


def _kv_overdue(A: pd.DataFrame) -> pd.DataFrame:
    return A[A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].eq(C.NT_OVERDUE)]


def _korpusa_text(df: pd.DataFrame, n: int = 3) -> str:
    vc = df["Корпус"].astype(str).value_counts().head(n)
    return ", ".join(f"{k} — {C.fmt_int(v)}" for k, v in vc.items()) or NO_DATA


def _real_groups(kv: pd.DataFrame, cd: pd.Timestamp, price: float) -> list[dict]:
    st_ = kv["Исходный статус"].fillna("")
    rem = kv["Замечаний открыто"].fillna(0)
    masks = {
        "ready": st_.eq("Открыта к передаче") & rem.eq(0),
        "remarks": st_.eq("Открыта к передаче") & rem.gt(0),
        "keys": st_.eq("Ключи в ОЗ не переданы"),
        "refusal": st_.eq("Не принята"),
        "not_open": st_.eq("В ОЗ, готовность не открыта"),
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
            cause = (f"Статус «Не принята»; отметка «мот. отказ / снятие готовности» у "
                     f"{C.fmt_int(g['Мот. отказ / снятие готовности'].fillna(False).sum())}")
        elif key == "not_open":
            cause = "Статус «В ОЗ, готовность не открыта»"
        else:
            cause = (f"Открытых замечаний у этих квартир {C.fmt_int(g['Замечаний открыто'].sum())}, "
                     f"критических {C.fmt_int(g['Критических'].sum())}")
        out.append(dict(key=key, title=PROBLEMS[key]["title"], n=int(len(g)), risk=risk, korpusa=_korpusa_text(g), cause=cause,
                        baseline=int(len(g)) if key != "remarks" else int(g["Замечаний открыто"].sum())))
    return out


def _problem_rows(groups: list[dict], total_risk: float, total_n: int, demo: bool) -> list[dict]:
    rows = []
    for g in sorted(groups, key=lambda x: -x["risk"])[:3]:
        t = PROBLEMS[g["key"]]
        rows.append(dict(
            key=g["key"], title=t["title"], n=g["n"], share_n=g["n"] / total_n if total_n else 0.0,
            risk=g["risk"], share_risk=g["risk"] / total_risk if total_risk else 0.0,
            korpusa=g["korpusa"], cause=g["cause"], action=t["action"], roles=list(t["roles"]),
            metric=t["metric"], baseline=g["baseline"], demo=demo))
    return rows


def real_project(D: dict, P: dict) -> dict:
    """Бунинские кварталы — только реальные данные и функции действующего отчёта."""
    A = D["apartments"]
    cd = D["calc_date"]
    k = D["kpis"]
    price = P["price"]
    u = C.unit_kpis(A)
    pen = C.penalty(A, **P)
    ready_n, ready_daily = C.ready_overdue_daily(A, price)
    kv = _kv_overdue(A)
    tw = D["transfers_weekly"]
    last = tw.iloc[-2] if len(tw) > 1 else tw.iloc[-1]
    prev = tw.iloc[-3] if len(tw) > 2 else None
    now_kv = C.units_state_at(A, cd)["nt_overdue_kv"]
    wk_kv = C.units_state_at(A, cd - np.timedelta64(7, "D"))["nt_overdue_kv"]
    groups = _real_groups(kv, cd, price)
    return dict(
        name=REAL_NAME, demo=False, groups=groups,
        overdue_kv=u["nt_overdue_kv"], overdue_all=u["nt_overdue"], ready=ready_n,
        risk_day=pen["daily"], risk_day_total=pen["daily_total"], ready_risk=ready_daily,
        accrued_lo=pen["accrued_lo"], accrued_up=pen["accrued_up"],
        median_days=u["nt_overdue_median"], units=u["units_total"], transferred=u["transferred"],
        week_fact=int(last["ПА, квартиры"]),
        week_prev=int(prev["ПА, квартиры"]) if prev is not None else None,
        week_all=int(last["ПА, все помещения"]),
        week_plan=None, week_dev=None,
        overdue_delta=int(now_kv - wk_kv),
        prev_snapshot=k.get("previous_snapshot"),
        claims=None, confirmed=None,
        problems=_problem_rows(groups, pen["daily"], u["nt_overdue_kv"], False),
        korpusa_top=_korpusa_text(kv, 5),
        by_korpus=(kv.assign(r=_rub_day(kv["Ставка ЦБ на срок ДДУ, %"].fillna(0), price),
                             k=kv["Корпус"].astype(str))
                   .groupby("k").agg(n=("Объект", "size"), risk=("r", "sum")).reset_index()
                   .sort_values("risk", ascending=False)),
    )


def demo_project(d: dict, rate_pct: float, price: float, cd: pd.Timestamp) -> dict:
    per_apt = float(_rub_day(rate_pct, price))
    n = d["overdue_kv"]
    g = d["groups"]
    ready = g["ready"]
    groups = [dict(key=key, title=PROBLEMS[key]["title"], n=v, risk=v * per_apt,
                   korpusa="условно: " + ", ".join(d["korpusa"]),
                   cause="Условное значение (ДЕМО), причина не из данных", baseline=v)
              for key, v in g.items() if v]
    return dict(
        name=d["name"], demo=True, groups=groups,
        overdue_kv=n, overdue_all=n, ready=ready, risk_day=n * per_apt, risk_day_total=n * per_apt,
        ready_risk=ready * per_apt, accrued_lo=n * per_apt * DEMO_DAYS, accrued_up=n * per_apt * DEMO_DAYS,
        median_days=DEMO_DAYS, units=None, transferred=None,
        week_fact=d["week_fact"], week_prev=d["week_prev"], week_all=None,
        week_plan=d["week_plan"], week_dev=d["week_fact"] - d["week_plan"],
        overdue_delta=n - d["overdue_prev"], prev_snapshot="условный",
        claims=d["claims"], confirmed=d["confirmed"],
        problems=_problem_rows(groups, n * per_apt, n, True),
        korpusa_top=", ".join(d["korpusa"]),
        by_korpus=pd.DataFrame({"k": list(d["korpusa"]), "n": [None] * len(d["korpusa"]),
                                "risk": [None] * len(d["korpusa"])}),
    )


def avg_rate(D: dict, P: dict) -> float:
    kv = _kv_overdue(D["apartments"])
    r = kv["Ставка ЦБ на срок ДДУ, %"].fillna(0)
    return float(r.mean()) if len(kv) else 0.0


def build(D: dict, P: dict, fact_only: bool) -> dict:
    real = real_project(D, P)
    projects = [real]
    if not fact_only:
        rate = avg_rate(D, P)
        projects += [demo_project(d, rate, P["price"], D["calc_date"]) for d in DEMO_PROJECTS]
    return dict(projects=projects, real=real, totals=totals(projects), fact_only=fact_only)


def totals(projects: list[dict]) -> dict:
    real = [p for p in projects if not p["demo"]]
    has_demo = any(p["demo"] for p in projects)

    def s(key, ps):
        return sum(p[key] for p in ps)

    plans = [p["week_plan"] for p in projects]
    top = max(projects, key=lambda p: p["risk_day"]) if projects else None
    return dict(
        overdue_kv=s("overdue_kv", projects), ready=s("ready", projects), risk_day=s("risk_day", projects),
        ready_risk=s("ready_risk", projects), accrued_up=s("accrued_up", projects),
        week_fact=s("week_fact", projects), accrued_lo=s("accrued_lo", projects), overdue_delta=s("overdue_delta", projects),
        week_prev=(s("week_prev", projects) if projects and all(p["week_prev"] is not None for p in projects) else None),
        week_plan=(s("week_plan", projects) if projects and all(x is not None for x in plans) else None),
        has_demo=has_demo,
        fact=dict(overdue_kv=s("overdue_kv", real), ready=s("ready", real), risk_day=s("risk_day", real),
                  ready_risk=s("ready_risk", real), accrued_up=s("accrued_up", real)),
        claims=(s("claims", projects) if projects and all(p["claims"] is not None for p in projects) else None),
        confirmed=(s("confirmed", projects) if projects and all(p["confirmed"] is not None for p in projects) else None),
        top=top, n=len(projects),
        top_share=(top["risk_day"] / s("risk_day", projects)) if top and s("risk_day", projects) else 0.0,
    )


def table(projects: list[dict], sort: str = "risk") -> pd.DataFrame:
    tr = sum(p["risk_day"] for p in projects) or 1.0
    rows = []
    for p in projects:
        pr = p["problems"][0] if p["problems"] else None
        rows.append({
            "ЖК": p["name"] + (" · ДЕМО" if p["demo"] else ""),
            "Данные": DEMO_TAG if p["demo"] else "ФАКТ",
            "Передано за неделю, кв.": p["week_fact"],
            "Отклонение от плана, кв.": (f"{p['week_dev']:+d}".replace("-", "−") + " · ДЕМО") if p["week_dev"] is not None else NO_DATA,
            "Просрочено по ДДУ, кв.": p["overdue_kv"],
            "Из них готовы": p["ready"],
            "Доля готовых, %": round(100 * p["ready"] / p["overdue_kv"], 1) if p["overdue_kv"] else 0.0,
            "Расчётный риск, ₽/сутки": round(p["risk_day"]),
            "Доля риска портфеля, %": round(100 * p["risk_day"] / tr, 1),
            "Главная проблема": (pr["title"] + f" — {C.fmt_int(pr['n'])} кв.") if pr else NO_DATA,
            "Предлагаемое действие": pr["action"] if pr else NO_DATA,
            "_name": p["name"],
        })
    df = pd.DataFrame(rows)
    col = {"risk": "Расчётный риск, ₽/сутки", "overdue": "Просрочено по ДДУ, кв."}.get(sort)
    if col:
        df = df.sort_values(col, ascending=False, kind="stable")
    return df.reset_index(drop=True)


def portfolio_messages(tot: dict, projects: list[dict]) -> tuple[str, list[str]]:
    """Главный вывод и ключевые сообщения по ПОРТФЕЛЮ в целом (ЖК — равные сегменты, без выделения одного)."""
    n, rd = tot["overdue_kv"], tot["risk_day"]
    if not projects or not n:
        return "Нет данных для сводки по портфелю", []
    kw = lambda x: f"{C.fmt_int(x)} {C.plural(x, 'квартира', 'квартиры', 'квартир')}"
    share_ready = tot["ready"] / n
    head = (f"Портфель: {kw(n)} просрочено по ДДУ, ≈{C.fmt_money(rd)} расчётного риска в сутки; "
            f"{C.fmt_pct(share_ready)} просрочки закрывается передачей готовых квартир")
    msgs = [f"Готовы к передаче без замечаний {kw(tot['ready'])} — это {C.fmt_money(tot['ready_risk'])} риска в сутки "
            f"({C.fmt_pct(tot['ready_risk'] / rd if rd else 0)}): самый быстрый эффект от решения на совещании."]
    d = tot["overdue_delta"]
    wk = tot["week_fact"]
    msgs.append(f"За 7 дней просрочка {'снизилась на' if d < 0 else 'выросла на' if d > 0 else 'не изменилась:'} "
                f"{C.fmt_int(abs(d)) if d else '0'}; за неделю передано {kw(wk)}.")
    big = max(projects, key=lambda p: p["risk_day"])
    if len(projects) > 1:
        msgs.append(f"Риск распределён по {len(projects)} ЖК; крупнейший сегмент даёт {C.fmt_pct(big['risk_day'] / rd)} суточного риска.")
    return head, msgs


# ---------------------------------------------------------------- сверка с действующим отчётом
def _close(a, b, tol=1e-6) -> bool:
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=1.0)


def reconcile(D: dict, P: dict, real: dict) -> list[dict]:
    """Каждая цифра раздела против независимого источника действующего отчёта."""
    A = D["apartments"]
    cur = D["kpis"]["current"]
    ks = D["korpus_summary"]
    k_price = P["price"] / C.ILLUSTR_PRICE      # kpis.json посчитан при условной цене 10 млн ₽; риск линеен по цене
    pen = C.penalty(A, **P)
    ready_n, ready_daily = C.ready_overdue_daily(A, P["price"])
    mask_kv = A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].eq(C.NT_OVERDUE)
    tw = D["transfers_weekly"]
    wk = D["kpis"].get("week_transfers") or {}
    last = tw.iloc[-2] if len(tw) > 1 else tw.iloc[-1]
    rows = [
        ("Просрочено по ДДУ, помещений", real["overdue_all"], cur["nt_overdue"], "kpis.json действующего отчёта"),
        ("То же, сумма по корпусам", real["overdue_all"], int(ks["Не_передано_просрочка"].sum()), "сводка по корпусам действующего отчёта"),
        ("Просрочено по ДДУ, квартир", real["overdue_kv"], cur["nt_overdue_kv"], "kpis.json действующего отчёта"),
        ("То же, пересчёт по реестру квартир", real["overdue_kv"], int(mask_kv.sum()), "реестр помещений"),
        ("Из них готовы без замечаний", real["ready"], ready_n, "расчёт действующего отчёта (готовые без замечаний)"),
        ("Готовые входят в просроченные (≤)", min(real["ready"], real["overdue_kv"]), real["ready"], "проверка включения"),
        ("Риск ₽/сутки (квартиры)", real["risk_day"], cur["penalty_daily_est"] * k_price, "kpis.json (цена 10 млн ₽, пересчёт)"),
        ("Риск ₽/сутки — как на главной", real["risk_day"], pen["daily"], "hero главной страницы действующего отчёта"),
        ("Риск готовых входит в общий риск (≤)", min(real["ready_risk"], real["risk_day"]), real["ready_risk"], "проверка включения"),
        ("Накоплено, верхняя оценка", real["accrued_up"], cur["penalty_accrued_est_up"] * k_price, "kpis.json (пересчёт по цене)"),
        ("Накоплено, нижняя оценка", real["accrued_lo"], cur["penalty_accrued_est_lo"] * k_price, "kpis.json (пересчёт по цене)"),
        ("Передано за полную неделю, квартир", real["week_fact"], int(last["ПА, квартиры"]), "ПА по неделям действующего отчёта"),
        ("Передано за ту же неделю, помещений", real["week_all"], wk.get("current", real["week_all"]), "kpis.json действующего отчёта"),
    ]
    out = []
    for name, a, b, src in rows:
        out.append(dict(name=name, portfolio=float(a), report=float(b), source=src, ok=_close(a, b)))
    return out
