"""Портфель ЖК: расчёты для отчёта генерального директора (отдельный продукт, не часть отчёта по Бунинским).

Все ЖК считаются одним и тем же конвейером из одной схемы таблиц: помещения, замечания (свёртка), подрядчики.
Персональных данных нет: только счётчики, корпуса и роли исполнителей (без имён и сроков).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import pf_core as C
import pf_stats

NO_DATA = "Нет данных"
# Единственная пометка о происхождении цифр на экранах. Чтобы убрать — присвоить пустую строку.
MODEL_NOTE = "Прокшино и Дзен-кварталы — модельный сценарий."
WEEK0 = pd.Timestamp("2026-08-17")     # первая из 12 недель динамики (понедельник)
N_WEEKS = 12

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


def _problem_rows(groups: list[dict], total_risk: float, total_n: int) -> list[dict]:
    rows = []
    for g in sorted(groups, key=lambda x: -x["risk"])[:3]:
        t = PROBLEMS[g["key"]]
        rows.append(dict(
            key=g["key"], title=t["title"], n=g["n"], share_n=g["n"] / total_n if total_n else 0.0,
            risk=g["risk"], share_risk=g["risk"] / total_risk if total_risk else 0.0,
            korpusa=g["korpusa"], cause=g["cause"], action=t["action"], roles=list(t["roles"]),
            metric=t["metric"], baseline=g["baseline"]))
    return rows


def weekly(A: pd.DataFrame, cd: pd.Timestamp) -> pd.DataFrame:
    """12 недель: передано (квартиры / все помещения) по датам ПА и просрочка по ДДУ (квартиры) на конец недели."""
    tr = C.transferred_mask(A)
    acc = A["Дата принятия собственником"]
    kv = A["Тип объекта"].eq("Квартира")
    rows = []
    for i in range(N_WEEKS):
        ws = WEEK0 + pd.Timedelta(days=7 * i)
        we = ws + pd.Timedelta(days=6)
        m = tr & acc.ge(ws) & acc.lt(ws + pd.Timedelta(days=7))
        st = C.units_state_at(A, min(we, cd))
        rows.append({"ws": ws, "Неделя": f"{ws:%d.%m}–{we:%d.%m}", "Передано, квартир": int((m & kv).sum()), "Передано, всего": int(m.sum()),
                     "Просрочено на конец недели, кв.": int(st["nt_overdue_kv"]), "partial": bool(we > cd - pd.Timedelta(days=5))})
    return pd.DataFrame(rows)


def project(d: dict, P: dict) -> dict:
    """Все показатели одного ЖК: один набор для каждого сегмента портфеля."""
    A, cd = d["units"], d["calc_date"]
    price = P["price"]
    u = C.unit_kpis(A)
    pen = C.penalty(A, **P)
    ready_n, ready_daily = C.ready_overdue_daily(A, price)
    kv = _kv_overdue(A)
    wk = weekly(A, cd)
    full = wk[~wk["partial"]]
    last, prev = full.iloc[-1], (full.iloc[-2] if len(full) > 1 else None)
    now_kv = C.units_state_at(A, cd)["nt_overdue_kv"]
    wk_kv = C.units_state_at(A, cd - pd.Timedelta(days=7))["nt_overdue_kv"]
    groups = _real_groups(kv, cd, price)
    rem = d["remarks"]
    n_rem = int(A["Замечаний открыто"].sum())
    rm = lambda m: int(rem.loc[m, "n"].sum())
    ct = d["contractors"]
    return dict(
        name=d["name"], key=d["key"], groups=groups, weekly=wk,
        overdue_kv=u["nt_overdue_kv"], overdue_all=u["nt_overdue"], ready=ready_n,
        risk_day=pen["daily"], risk_day_total=pen["daily_total"], ready_risk=ready_daily,
        accrued_lo=pen["accrued_lo"], accrued_up=pen["accrued_up"], penalty=pen,
        median_days=u["nt_overdue_median"], units=u["units_total"], units_kv=int(A["Тип объекта"].eq("Квартира").sum()),
        transferred=u["transferred"], late_transferred=u["late_transferred"], refusals=u["refusals"],
        week_fact=int(last["Передано, квартир"]), week_all=int(last["Передано, всего"]),
        week_prev=int(prev["Передано, квартир"]) if prev is not None else None,
        overdue_delta=int(now_kv - wk_kv),
        remarks=n_rem, critical=int(A["Критических"].sum()), remarks_over=int(A["Просрочено (регл)"].sum()),
        blocking=rm(rem["Блокирует"]), remarks_cost=n_rem * pf_stats.COST_PER_REMARK,
        claim_potential=float(ct["Потенциал претензии, ₽"].sum()) if "Потенциал претензии, ₽" in ct else 0.0,
        claims=None, confirmed=None,
        problems=_problem_rows(groups, pen["daily"], u["nt_overdue_kv"]),
        korpusa_top=_korpusa_text(kv, 5),
        by_korpus=(kv.assign(r=_rub_day(kv["Ставка ЦБ на срок ДДУ, %"].fillna(0), price), k=kv["Корпус"].astype(str))
                   .groupby("k").agg(n=("Объект", "size"), risk=("r", "sum")).reset_index().sort_values("risk", ascending=False)),
    )


def build(D: dict, P: dict) -> dict:
    projects = [project(d, P) for d in D.values()]
    return dict(projects=projects, totals=totals(projects))


def totals(projects: list[dict]) -> dict:
    def s(key):
        return sum(p[key] for p in projects)

    top = max(projects, key=lambda p: p["risk_day"]) if projects else None
    wk_prev = [p["week_prev"] for p in projects]
    return dict(
        overdue_kv=s("overdue_kv"), ready=s("ready"), risk_day=s("risk_day"), ready_risk=s("ready_risk"),
        accrued_up=s("accrued_up"), accrued_lo=s("accrued_lo"), week_fact=s("week_fact"), overdue_delta=s("overdue_delta"),
        week_prev=(sum(wk_prev) if all(x is not None for x in wk_prev) else None),
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
            "Передано за неделю, кв.": p["week_fact"],
            "Просрочено по ДДУ, кв.": p["overdue_kv"],
            "Из них готовы": p["ready"],
            "Доля готовых, %": round(100 * p["ready"] / p["overdue_kv"], 1) if p["overdue_kv"] else 0.0,
            "Расчётный риск, ₽/сутки": round(p["risk_day"]),
            "Доля риска портфеля, %": round(100 * p["risk_day"] / tr, 1),
            "Открытых замечаний": p["remarks"],
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
    """Главный вывод и ключевые сообщения по ПОРТФЕЛЮ в целом (ЖК — равные сегменты)."""
    n, rd = tot["overdue_kv"], tot["risk_day"]
    if not projects or not n:
        return "Нет данных для сводки по портфелю", []
    kw = lambda x: f"{C.fmt_int(x)} {C.plural(x, 'квартира', 'квартиры', 'квартир')}"
    head = (f"Портфель: {kw(n)} просрочено по ДДУ, ≈{C.fmt_money(rd)} расчётного риска в сутки; "
            f"{C.fmt_pct(tot['ready'] / n)} просрочки закрывается передачей готовых квартир")
    msgs = [f"Готовы к передаче без замечаний {kw(tot['ready'])} — это {C.fmt_money(tot['ready_risk'])} риска в сутки "
            f"({C.fmt_pct(tot['ready_risk'] / rd if rd else 0)}): самый быстрый эффект от решения на совещании."]
    d = tot["overdue_delta"]
    msgs.append(f"За 7 дней просрочка {'снизилась на' if d < 0 else 'выросла на' if d > 0 else 'не изменилась:'} "
                f"{C.fmt_int(abs(d)) if d else '0'}; за неделю передано {kw(tot['week_fact'])}.")
    msgs.append(f"Открыто {C.fmt_int(tot['remarks'])} замечаний, из них {C.fmt_pct(tot['remarks_over'] / tot['remarks'] if tot['remarks'] else 0)} "
                f"просрочены; {C.fmt_int(tot['critical'])} критических.")
    worst = max(projects, key=lambda p: p["risk_day"] / max(p["units_kv"], 1))
    msgs.append(f"Риск распределён по {len(projects)} ЖК; больше всего на квартиру — в «{worst['name']}» "
                f"({C.fmt_int(worst['risk_day'] / max(worst['units_kv'], 1))} ₽ в сутки на квартиру).")
    return head, msgs


# ---------------------------------------------------------------- сверка Бунинских кварталов с действующим отчётом
def _close(a, b, tol=1e-6) -> bool:
    return math.isclose(float(a), float(b), rel_tol=tol, abs_tol=1.0)


def reconcile(d: dict, P: dict, p: dict) -> list[dict]:
    """Расчёт по общей схеме против независимых файлов действующего отчёта (только для ЖК, где они есть)."""
    A = d["units"]
    cur = d["ref_kpis"]["current"]
    ks = d["ref_korpus"]
    k_price = P["price"] / C.ILLUSTR_PRICE      # kpis.json посчитан при цене 10 млн ₽; риск линеен по цене
    pen = C.penalty(A, **P)
    ready_n, _ = C.ready_overdue_daily(A, P["price"])
    mask_kv = A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].eq(C.NT_OVERDUE)
    tw = d["ref_transfers"]
    last = tw.iloc[-2]
    rows = [
        ("Просрочено по ДДУ, помещений", p["overdue_all"], cur["nt_overdue"]),
        ("То же, сумма по корпусам", p["overdue_all"], int(ks["Не_передано_просрочка"].sum())),
        ("Просрочено по ДДУ, квартир", p["overdue_kv"], cur["nt_overdue_kv"]),
        ("То же, по реестру квартир", p["overdue_kv"], int(mask_kv.sum())),
        ("Помещений всего", p["units"], cur["units_total"]),
        ("Передано", p["transferred"], cur["transferred"]),
        ("Готовые без замечаний (в просрочке)", p["ready"], ready_n),
        ("Накоплено, верхняя оценка", p["accrued_up"], cur["penalty_accrued_est_up"] * k_price),
        ("Накоплено, нижняя оценка", p["accrued_lo"], cur["penalty_accrued_est_lo"] * k_price),
        ("Риск ₽/сутки, квартиры", p["risk_day"], pen["daily"]),
        ("Передано за полную неделю, квартир", p["week_fact"], int(last["ПА, квартиры"])),
        ("Передано за ту же неделю, помещений", p["week_all"], int(last["ПА, все помещения"])),
        ("Открытых замечаний", p["remarks"], cur["remarks_open"]),
        ("Критических замечаний", p["critical"], cur["critical"]),
    ]
    return [dict(name=n, portfolio=float(a), report=float(b), ok=_close(a, b)) for n, a, b in rows]
