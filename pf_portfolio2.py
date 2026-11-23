"""«Портфель 2» — альтернативная версия отчёта ГД в том же приложении (маршрут ?view=portfolio2).

Основа — архив стороннего автора (pages/Портфель_2.py): главный экран с концентрацией дневного риска,
независимый выбор меры с наибольшим расчётным эффектом по каждому ЖК (мера может повторяться между ЖК),
эффект до затрат / оценка затрат / эффект после затрат, сверка итогов, решения и поручения по ролям.
Данные и расчёты — те же, что у «Портфеля ЖК» (app.py передаёт готовые projects, PEN, GANTT, детализацию).
Все суммы — расчётная оценка по реестру квартир, не предъявленные требования и не выплаты.
"""
from __future__ import annotations

import html
import math
from typing import Any

import pandas as pd
import streamlit as st

import pf_core as C
import pf_decide as DC
import pf_drill as DR
import pf_gantt as GT
import pf_nav as N
import pf_roles as R
import pf_ui as U

P2_SCHEMA = "q1"
VIEW = "portfolio2"
TITLE = "Портфель 2"

CSS = """<style>
.pf-ver { display: inline-flex; margin-right: 14px; border: 1px solid #3B5374; border-radius: 5px; overflow: hidden; flex: none; }
.pfnav .pf-ver a { padding: 5px 10px; border-radius: 0; font-weight: 600; color: #C5CEDA !important; white-space: nowrap; }
.pfnav .pf-ver a[aria-current="page"] { background: #F2F5F9; color: #0B1F3A !important; }
.p2-head { background: #0B1F3A; color: #fff; border-radius: 6px; padding: 18px 24px; margin: 4px 0 12px; border-bottom: 3px solid #A67C00; }
.p2-head .kick { font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #B9C4D3; }
.p2-head .ttl { font-size: clamp(24px, 3vw, 34px); font-weight: 700; margin-top: 2px; }
.p2-note { background: #F7F9FC; border: 1px solid #C9D2DF; border-left: 4px solid #8A97AA; padding: 9px 13px; font-size: 12.5px; color: #3A4658; margin: 6px 0 12px; }
.p2-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 6px 0 12px; }
.p2-kpi { background: #fff; border: 1px solid #D5DBE3; border-radius: 6px; padding: 10px 14px; }
.p2-kpi span { display: block; font-size: 11.5px; color: #4A5568; font-weight: 600; }
.p2-kpi b { display: block; font-size: clamp(20px, 2.2vw, 30px); color: #14213D; font-variant-numeric: tabular-nums; }
.p2-kpi i { display: block; font-style: normal; font-size: 11px; color: #596577; }
.p2-focus { background: #fff; border: 1px solid #C9D2DF; border-left: 4px solid #A52C28; border-radius: 6px; padding: 12px 16px; margin: 4px 0 14px; }
.p2-focus .lbl { font-size: 11px; color: #596577; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; }
.p2-focus h3 { margin: 2px 0 4px; font-size: 19px; color: #14213D; }
.p2-focus strong { color: #A52C28; font-size: 20px; font-variant-numeric: tabular-nums; }
.p2-focus p { margin: 5px 0 0; font-size: 13.5px; color: #3A4658; }
.p2-sec { scroll-margin-top: 56px; font-weight: 700; font-size: 16px; color: #14213D; margin: 18px 0 6px; border-bottom: 1px solid #14213D; padding-bottom: 4px; }
.p2-card { background: #fff; border: 1px solid #C9D2DF; border-radius: 6px; padding: 12px 16px; margin: 8px 0 12px; scroll-margin-top: 60px; }
.p2-card h3 { margin: 0 0 6px; font-size: 18px; color: #14213D; }
.p2-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px 16px; margin: 8px 0; }
.p2-grid div { font-size: 13px; } .p2-grid span { display: block; font-size: 11px; color: #596577; text-transform: uppercase; letter-spacing: .03em; }
.p2-grid b { display: block; font-size: 16px; color: #14213D; }
.p2-links { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 8px 0; font-size: 13px; }
.p2-ok { font-size: 12px; color: #2F6B3A; margin: 2px 0 8px; } .p2-bad { font-size: 12.5px; color: #A52C28; margin: 2px 0 8px; font-weight: 600; }
.pf-ver .pv-s { display: none; }
@media (max-width: 640px) { .pf-ver { margin-right: 4px; } .pf-ver .pv-f { display: none; } .pf-ver .pv-s { display: inline; } }
@media (max-width: 720px) { .p2-kpis { grid-template-columns: 1fr 1fr; } .p2-grid { grid-template-columns: 1fr; } .p2-head { padding: 14px; }
  .pfnav .pf-ver a { padding: 5px 7px; font-size: 12px; } }
</style>"""


def menu(view: str | None) -> str:
    """Верхнее меню обеих версий: переключатель «Портфель ЖК / Портфель 2» вместо статичного названия, разделы — как в «Портфеле ЖК»."""
    p1 = N.link("Портфель ЖК", content='<span class="pv-f">Портфель ЖК</span><span class="pv-s">П1</span>', current=view != VIEW)
    p2 = N.link(TITLE, content='<span class="pv-f">Портфель 2</span><span class="pv-s">П2</span>', current=view == VIEW, view=VIEW)
    switch = f'<span class="pf-ver" role="group" aria-label="Версия отчёта">{p1}{p2}</span>'
    if view == VIEW:       # разделы «Портфеля 2» — переходы внутри страницы
        own = "".join(f'<a href="#{a}">{t}</a>' for a, t in (("p2-table", "Сводка"), ("p2-decisions", "Решения"),
                                                            ("p2-orders", "Поручения"), ("p2-card", "Карточка ЖК"), ("p2-fin", "Финансы")))
        return CSS + f'<nav class="pfnav" aria-label="Разделы портфеля 2">{switch}{own}</nav>'
    base = N.menu(view if view in N.REPORT_VIEWS else None)
    return CSS + base.replace("<b>ПОРТФЕЛЬ ЖК</b>", switch, 1)


# ---------------------------------------------------------------- форматирование
def fmt_rub(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return "не оценено"
    return f"{round(value):,}".replace(",", " ") + " ₽"


def fmt_mln(value: float | None, nd: int = 2) -> str:
    if value is None or not math.isfinite(float(value)):
        return "не оценено"
    return f"{value / 1_000_000:,.{nd}f}".replace(",", " ").replace(".", ",").replace("-", "−") + " млн ₽"


def fmt_int(value: int | float) -> str:
    return f"{int(value):,}".replace(",", " ")


def pct(part: float, whole: float) -> str:
    return f"{part / whole * 100:.1f}".replace(".", ",") + "%" if whole else "—"


# ---------------------------------------------------------------- решения (логика архива)
def budget_estimate(p: dict, d: dict) -> tuple[float | None, str]:
    """Неизвестный бюджет не подменяется нулём. Тарифы — pf_decide.PACKAGE_RATES."""
    if d["key"] == "crew" and d.get("cost") is not None:
        return float(d["cost"]), "расчётная стоимость второй смены приёмки"
    tariff = DC.PACKAGE_RATES.get(d["key"])
    if tariff is None:
        return None, "затраты не оценены: для меры не задан тариф"
    group = p["reasons"].get(d.get("pool", ""), {})
    count, risk = int(group.get("n", 0)), float(group.get("risk", 0))
    if not count or not risk:
        return None, "затраты не оценены: не определена группа квартир"
    forecast_units = min(count, max(0, round(d["effect_day"] / (risk / count))))
    return forecast_units * tariff, f"расчёт: {forecast_units} кв. × расчётный тариф {fmt_rub(tariff)}"


def best_decision(p: dict) -> dict[str, Any] | None:
    """Каждый ЖК оценивается независимо: одинаковая мера допускается для нескольких ЖК.
    Отбор — по наибольшему расчётному эффекту до затрат; при неизвестных затратах мера — гипотеза для проверки, не утверждённый план."""
    variants = [d for d in p.get("cands", []) if d.get("effect", 0) > 0]
    if not variants:
        return None
    measure = max(variants, key=lambda d: (d["effect"], d["effect_day"]))
    cost, cost_basis = budget_estimate(p, measure)
    roles = [r_ for r_ in measure.get("roles", []) if r_ != R.CEO]
    return {
        "measure": measure,
        "role": R.role(R.DECISION_ROLE.get(measure["key"], roles[0] if roles else R.SETTLE)),
        "effect": float(measure["effect"]),
        "cost": cost,
        "net": float(measure["effect"]) - cost if cost is not None else None,
        "cost_basis": cost_basis,
        "needs_gd": bool(measure.get("needs_gd", False)),
    }


def _short(m: dict) -> str:
    return R.DECISION_SHORT.get(m["key"], m.get("short3") or m.get("short") or m["title"])


# ---------------------------------------------------------------- экран
def render(ctx: dict) -> None:
    """ctx: projects (по риску), totals, DA, PEN, GANTT, main_row(p) → строка сводки, drill(key) → детализация, slice_text, route."""
    projects, DA, PEN, GANTT = ctx["projects"], ctx["DA"], ctx["PEN"], ctx["GANTT"]
    totals, route = ctx["totals"], ctx["route"]
    rows = []
    for p in projects:
        k = p["key"]
        mr = ctx["main_row"](p)
        rows.append(dict(key=k, name=p["name"], project=p, overdue=int(p["overdue_kv"]), ready=int(p["ready"]),
                         daily=float(p["risk_day"]), ddu_2026=float(PEN[k]["ddu"][2026]), remarks_2026=float(PEN[k]["remarks"][2026]),
                         mr=mr, decision=best_decision(p)))
    rows.sort(key=lambda r: (-r["daily"], -r["overdue"], r["name"]))
    by_key = {r["key"]: r for r in rows}
    overall_daily = sum(r["daily"] for r in rows)
    overall_overdue = sum(r["overdue"] for r in rows)
    overall_ready = sum(r["ready"] for r in rows)
    overall_ddu = sum(r["ddu_2026"] for r in rows)
    overall_rem = sum(r["remarks_2026"] for r in rows)
    leader = rows[0]
    lead = leader["decision"]

    st.markdown(f'<div class="p2-head"><div class="kick">Отчёт для генерального директора · альтернативная версия</div>'
                f'<div class="ttl">{TITLE}</div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="p2-note">Срез <b>{html.escape(ctx["slice_text"])}</b> · {len(rows)} ЖК · все ЖК в одной таблице по убыванию дневного риска. '
                'Суммы неустойки и эффект мер — расчётная оценка по реестру квартир: не предъявленные требования, не выплаты и не '
                'подтверждённые результаты; до решения о расходах требуют юридической и финансовой сверки.</div>', unsafe_allow_html=True)

    kpi = [("Нарушен срок передачи", f"{fmt_int(overall_overdue)} кв.", "не переданы, срок по ДДУ нарушен"),
           ("Неустойка за +1 день", fmt_rub(overall_daily), "расчётная оценка на дату среза"),
           ("Неустойка 2026 за передачу", fmt_mln(overall_ddu, 1), "начислено по модели, не подтверждено"),
           ("Готовы к передаче", f"{fmt_int(overall_ready)} кв.", "из квартир с нарушенным сроком")]
    st.markdown('<div class="p2-kpis">' + "".join(f'<div class="p2-kpi"><span>{a}</span><b>{b}</b><i>{c}</i></div>' for a, b, c in kpi)
                + '</div>', unsafe_allow_html=True)

    if lead:
        m = lead["measure"]
        st.markdown(f'<div class="p2-focus"><span class="lbl">Наибольший дневной риск</span>'
                    f'<h3>{N.link(leader["name"], view=VIEW, card=leader["key"])}</h3>'
                    f'<strong>{fmt_rub(leader["daily"])}/день · {pct(leader["daily"], overall_daily)} портфеля</strong>'
                    f'<p>Нарушен срок передачи — {fmt_int(leader["overdue"])} кв.; готовы к передаче — {fmt_int(leader["ready"])} кв.</p>'
                    f'<p><b>Мера:</b> {html.escape(_short(m))}. <b>Роль:</b> {html.escape(lead["role"])}. '
                    f'<b>Основание:</b> {html.escape(m["basis"])}.</p></div>', unsafe_allow_html=True)

    # сверка на неокруглённых значениях
    errors = []
    for r in rows:
        a, p = DA[r["key"]]["units"], r["project"]
        actual_over = int((a["Тип объекта"].eq("Квартира") & a["Просрочка ДДУ"].eq(C.NT_OVERDUE)).sum())
        if actual_over != r["overdue"]:
            errors.append(f'{r["name"]}: квартиры с нарушенным сроком')
        if C.ready_overdue_daily(a, p["price"])[0] != r["ready"]:
            errors.append(f'{r["name"]}: готовые к передаче')
        if not math.isclose(p["accrued_up"], r["ddu_2026"], abs_tol=1):
            errors.append(f'{r["name"]}: неустойка 2026 за передачу')
    if overall_overdue != totals["overdue_kv"]:
        errors.append("портфель: квартиры с нарушенным сроком")
    if not math.isclose(overall_daily, totals["risk_day"], abs_tol=1):
        errors.append("портфель: неустойка в день")
    if not math.isclose(overall_ddu, totals["accrued_up"], abs_tol=1):
        errors.append("портфель: неустойка 2026")
    st.markdown('<div class="p2-bad">Расхождение расчётов: ' + html.escape("; ".join(errors)) + "</div>" if errors else
                '<div class="p2-ok">Сверка: квартиры с нарушенным сроком, готовые к передаче, неустойка в день и неустойка 2026 '
                'по ЖК совпадают с итогами портфеля до округления.</div>', unsafe_allow_html=True)

    # ------------------------------------------------ главная таблица
    st.markdown('<div class="p2-sec" id="p2-table">ЖК по дневному риску</div>', unsafe_allow_html=True)
    body = []
    for r in rows:
        dcs = r["decision"]
        body.append([
            N.link(r["name"], view=VIEW, card=r["key"]), fmt_int(r["overdue"]), fmt_int(r["ready"]), fmt_rub(r["daily"]),
            pct(r["daily"], overall_daily), _short(dcs["measure"]) if dcs else "мера не выбрана",
            dcs["role"] if dcs else "—", fmt_mln(dcs["effect"]) if dcs else "—",
            fmt_mln(dcs["cost"]) if dcs else "—", fmt_mln(dcs["net"]) if dcs else "—"])
    body.append(["Итого портфель", fmt_int(overall_overdue), fmt_int(overall_ready), fmt_rub(overall_daily), "100,0%",
                 "", "", "не суммируется", "", ""])
    U.fin_table(["ЖК", "Нарушен срок, кв.", "Готовы, кв.", "Неустойка, ₽/день", "Доля", "Мера с наибольшим эффектом", "Роль",
                 "Эффект за 4 нед. до затрат", "Затраты за 4 нед.", "Эффект после затрат"],
                body,
                right=(1, 2, 3, 4, 7, 8, 9), total_last=True, hide=(2, 4, 6, 9),
                tips={7: "Расчётный эффект меры за 4 недели, до затрат", 8: "«не оценено» — тариф или группа квартир не заданы; это не нулевая стоимость"})
    st.caption("Нажмите на ЖК — откроется карточка с решением, корпусами, квартирами и замечаниями. Эффекты мер разных ЖК не суммируются: "
               "меры пересекаются по квартирам. «Не оценено» в затратах означает отсутствие расчёта, а не нулевую стоимость.")

    # ------------------------------------------------ решения ГД
    approvals = [r for r in rows if r["decision"] and (r["decision"]["needs_gd"] or (r["decision"]["cost"] or 0) > 0)]
    st.markdown('<div class="p2-sec" id="p2-decisions">Решения ГД</div>', unsafe_allow_html=True)
    if approvals:
        U.fin_table(["ЖК", "Утвердить", "Роль", "Основание", "Эффект за 4 нед.", "Затраты за 4 нед."],
                    [[N.link(r["name"], view=VIEW, card=r["key"]), _short(r["decision"]["measure"]), r["decision"]["role"],
                      "полномочие ГД" if r["decision"]["needs_gd"] else "требуется бюджет",
                      fmt_mln(r["decision"]["effect"]), fmt_mln(r["decision"]["cost"])] for r in approvals], right=(4, 5))
    else:
        st.caption("Мер, требующих утверждения ГД или бюджета, модель не выявила.")

    # ------------------------------------------------ поручения
    st.markdown('<div class="p2-sec" id="p2-orders">Поручения по ролям</div>', unsafe_allow_html=True)
    by_role: dict[str, list] = {}
    for r in rows:
        if r["decision"]:
            by_role.setdefault(r["decision"]["role"], []).append(r)
    U.fin_table(["Роль", "Поручение", "ЖК", "Контроль: было → цель", "Эффект за 4 нед."],
                [[role, "; ".join(dict.fromkeys(_short(x["decision"]["measure"]) for x in items)),
                  ", ".join(N.link(x["name"], view=VIEW, card=x["key"]) for x in items),
                  (" · ".join(f'{x["name"]}: {fmt_rub(x["daily"])} → {fmt_rub(max(0.0, x["daily"] - x["decision"]["measure"]["effect_day"]))} в день'
                                         for x in items)) + " — на следующем срезе",
                  fmt_mln(sum(x["decision"]["effect"] for x in items))]
                 for role, items in sorted(by_role.items(), key=lambda kv: -sum(x["decision"]["effect"] for x in kv[1]))], right=(4,))
    st.caption("Без сроков и без имён: исполнитель — роль. Контроль — дневная неустойка ЖК на следующем срезе против расчёта при исполнении меры.")

    # ------------------------------------------------ карточка ЖК
    keys = [r["key"] for r in rows]
    sel = route.get("card") if route.get("card") in by_key else leader["key"]

    def pick():
        N.set_route(view=VIEW, card=st.session_state["p2_card"])

    st.markdown(f'<div class="p2-sec" id="p2-card"><span id="card-{sel}"></span>Карточка ЖК</div>', unsafe_allow_html=True)
    if st.session_state.get("p2_card") != sel:
        st.session_state["p2_card"] = sel
    st.selectbox("ЖК", keys, key="p2_card", format_func=lambda k: by_key[k]["name"], on_change=pick)
    r = by_key[sel]
    p, dcs = r["project"], r["decision"]
    head = (f'<div class="p2-card" id="p2-card-{sel}"><h3>{html.escape(r["name"])}</h3>'
            f'<div class="p2-grid"><div><span>Нарушен срок передачи</span><b>{fmt_int(r["overdue"])} кв.</b></div>'
            f'<div><span>Неустойка в день</span><b>{fmt_rub(r["daily"])}</b>расчётная оценка</div>'
            f'<div><span>Неустойка 2026</span><b>{fmt_mln(r["ddu_2026"] + r["remarks_2026"], 1)}</b>начислено по модели, не подтверждено</div></div>')
    if dcs:
        m = dcs["measure"]
        head += (f'<p><b>Мера:</b> {html.escape(_short(m))} — {html.escape(dcs["role"])}.<br><b>Что сделать:</b> {html.escape(m["title"])}.'
                 f'<br><b>Основание:</b> {html.escape(m["basis"])}.<br><b>Механизм:</b> {html.escape(m["mechanism"])}.'
                 f'<br><b>Контрольный показатель:</b> {html.escape(m["metric"])}; '
                 f'неустойка в день {fmt_rub(r["daily"])} → {fmt_rub(max(0.0, r["daily"] - m["effect_day"]))} к концу 4-й недели при исполнении — на следующем срезе.</p>'
                 f'<div class="p2-grid"><div><span>Эффект за 4 недели до затрат</span><b>{fmt_mln(dcs["effect"])}</b>расчётная оценка</div>'
                 f'<div><span>Затраты за 4 недели</span><b>{fmt_mln(dcs["cost"])}</b>{html.escape(dcs["cost_basis"])}</div>'
                 f'<div><span>Эффект после затрат</span><b>{fmt_mln(dcs["net"])}</b>{"затраты не оценены" if dcs["net"] is None else "до сверки смет"}</div></div>'
                 + ('<p class="p2-bad">Нужно решение ГД или подтверждение бюджета.</p>' if dcs["needs_gd"] or (dcs["cost"] or 0) > 0 else
                    f'<p class="p2-ok">Рабочее поручение роли «{html.escape(dcs["role"])}».</p>'))
    else:
        head += '<p>Мер с положительным расчётным эффектом нет.</p>'
    st.markdown(U.gloss(head + "</div>"), unsafe_allow_html=True)
    if dcs:
        with st.expander("Почему эта мера и какие есть альтернативы"):
            m = dcs["measure"]
            other = sorted((x for x in p.get("cands", []) if x["key"] != m["key"]), key=lambda x: -x["effect"])[:5]
            U.fin_table(["Мера", "Роль", "Эффект за 4 нед. до затрат", "Затраты за 4 нед."],
                        [[_short(x) + (" — выбрана" if x is m else ""), R.role(R.DECISION_ROLE.get(x["key"], dcs["role"])),
                          fmt_mln(x["effect"]), fmt_mln(budget_estimate(p, x)[0])] for x in [m, *other]], right=(2, 3))
            st.caption("Мера выбрана по наибольшему расчётному эффекту до затрат независимо по каждому ЖК, поэтому одна мера может быть "
                       "главной в нескольких ЖК. Наибольший эффект до затрат не означает наибольший эффект после затрат, пока сметы не сверены.")

    # корпус → квартира → замечания
    dr = ctx["drill"](sel)
    st.markdown('<div class="p2-sec">Корпуса, квартиры, замечания</div>', unsafe_allow_html=True)
    top_apt = next((a for a in sorted(dr["apts"], key=lambda a: (-a["open"], -a["total"], a["id"])) if a["open"]), None)
    links = [N.link("Страница ЖК", jk=sel), N.link("Шахматка", jk=sel, tab="chess"), N.link("Замечания ЖК", jk=sel, tab="remarks"),
             N.link("Финансы ЖК", jk=sel, tab="money")]
    links += [N.link(f"Корпус {h['house']}", jk=sel, tab="chess", corpus=h["house"]) for h in dr["houses"]]
    if top_apt:
        links.append(N.link(f"Квартира {top_apt['id']} · замечаний {top_apt['open']}", jk=sel, tab="chess", corpus=top_apt["house"], unit=top_apt["id"]))
    st.markdown('<div class="p2-links">' + "".join(links) + '</div>', unsafe_allow_html=True)
    st.markdown(U.gloss(DR.houses_html(dr, "all", "p2")), unsafe_allow_html=True)
    st.caption("Корпус раскрывается до квартир, квартира — до хронологии (уведомление, осмотр, замечания, акт) и расчёта неустойки. "
               "Шахматка и реестр замечаний — общие страницы ЖК обеих версий.")

    # ------------------------------------------------ финансовая сверка
    st.markdown('<div class="p2-sec" id="p2-fin">Финансы</div>', unsafe_allow_html=True)
    with st.expander("Финансовая сверка и передача по годам"):
        U.fin_table(["ЖК", "Передано 2024", "Передано 2025", "Передано 2026", "Неустойка 2024–2026, млн ₽", "в т. ч. 2026, млн ₽"],
                    [[N.link(x["name"], view=VIEW, card=x["key"]), fmt_int(x["mr"]["t2024"]), fmt_int(x["mr"]["t2025"]), fmt_int(x["mr"]["t2026"]),
                      fmt_mln(x["mr"]["pen_delay"] + x["mr"]["pen_remarks"], 1).replace(" млн ₽", ""),
                      fmt_mln(x["ddu_2026"] + x["remarks_2026"], 1).replace(" млн ₽", "")] for x in rows]
                    + [["Итого портфель", fmt_int(sum(x["mr"]["t2024"] for x in rows)), fmt_int(sum(x["mr"]["t2025"] for x in rows)),
                        fmt_int(sum(x["mr"]["t2026"] for x in rows)),
                        fmt_mln(sum(x["mr"]["pen_delay"] + x["mr"]["pen_remarks"] for x in rows), 1).replace(" млн ₽", ""),
                        fmt_mln(overall_ddu + overall_rem, 1).replace(" млн ₽", "")]],
                    right=(1, 2, 3, 4, 5), total_last=True)
        st.caption("Неустойка начислена по модели (214-ФЗ, мораторий ПП № 326 исключён) и не подтверждена претензиями или выплатами. "
                   "Передачи 2024–2025 и их неустойка — по профилю допущений модели, 2026 — по датам актов в реестре. "
                   "Накопленная сумма и неустойка в день — разные показатели и не складываются.")

    with st.expander("График этапов — реконструкция по реестру"):
        st.caption("План и факт этапов (РВЭ, ключи в ОЗ, осмотры, устранение замечаний, АПП) восстановлены моделью по реестру квартир; "
                   "это не подтверждённый календарный план.")
        U.chart(GT.project_figure(GANTT[sel]), key=f"p2_gantt_{sel}", height=430)

    with st.expander("Методика и пределы применимости"):
        st.markdown(
            "- **Неустойка в день** — расчётная оценка за один дополнительный день просрочки по квартирам с нарушенным сроком на дату среза.\n"
            "- **Финансовая база** — расчётная цена квартиры по ЖК, а не индивидуальные цены ДДУ.\n"
            "- **Неустойка 2026** — расчёт по модели по срокам передачи и устранения недостатков; не равна предъявленным требованиям или выплатам.\n"
            "- **Мера** выбирается по наибольшему расчётному эффекту за 4 недели независимо по каждому ЖК; мера может повторяться между ЖК.\n"
            "- **Затраты** показаны, если задан тариф и определена группа квартир; иначе — «не оценено».\n"
            "- **Сокращение задержки в днях** не показывается: календарный план этапов не подтверждён.\n"
            "- **Роли** — должности и подразделения, без имён.\n"
            "- **Правовая применимость** по 214-ФЗ, договорные цены и фактические выплаты требуют юридической и финансовой сверки.")
