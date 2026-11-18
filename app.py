"""Портфель ЖК — отчёт для генерального директора (отдельное закрытое приложение).

Запуск: streamlit run app.py   ·   доступ: SHOW_REAL_DATA = "yes" в secrets (иначе — нейтральная заглушка).
"""
import html

import plotly.graph_objects as go
import streamlit as st

from data_gate import LOCKED_MESSAGE, real_data_allowed

# Шлюз до любой загрузки данных: без секрета — только заглушка.
_ALLOWED = real_data_allowed()
st.set_page_config(page_title="Портфель ЖК" if _ALLOWED else "Приложение",
                   page_icon="🏢" if _ALLOWED else "🔒", layout="wide" if _ALLOWED else "centered",
                   initial_sidebar_state="collapsed")
if not _ALLOWED:
    st.markdown(LOCKED_MESSAGE)
    st.stop()

import pf_auth  # noqa: E402
import pf_ui as U  # noqa: E402

if not pf_auth.authenticated():
    pf_auth.login_screen(U.CSS)
    st.stop()

import pf_core as C  # noqa: E402
import pf_data  # noqa: E402
import pf_model as PF  # noqa: E402

st.markdown(U.CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="pfnav"><b>ПОРТФЕЛЬ ЖК</b><a href="#summary">Сводка</a><a href="#segments">Сегменты</a>'
    '<a href="#contribution">Вклад в риск</a><a href="#dynamics">Динамика</a><a href="#outlook">Ориентир</a>'
    '<a href="#matrix">Матрица рисков</a><a href="#drill">Разбор ЖК</a><a href="#money">Деньги</a>'
    '<a href="#orders">Поручения</a><a href="#notes">Допущения</a></div>', unsafe_allow_html=True)


@st.cache_data(show_spinner="Загрузка…")
def _load():
    return pf_data.load(True)


try:
    DA = _load()
except pf_data.LockedError:
    st.error("Данные недоступны: проверьте ключ данных в настройках приложения.")
    st.stop()
with st.sidebar:
    if st.button("Выйти", key="pf_exit"):
        st.session_state.clear()
        st.rerun()
    st.markdown("**Допущения расчёта**")
    price_m = st.number_input("Цена квартиры по ДДУ, млн ₽ (условно)", min_value=1.0, max_value=60.0, value=10.0, step=0.5, key="pf_price")
    st.caption("Цен по ДДУ в данных нет — риск пересчитывается пропорционально цене. "
               "Машиноместа и кладовые — по условным ценам, коммерция не считается.")
pm = f"{price_m:.1f}".replace(".", ",")
P = dict(price=price_m * 1e6, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
f, fm = C.fmt_int, C.fmt_money
pl = lambda n: C.plural(n, "квартира", "квартиры", "квартир")
fr = lambda x: C.fmt_pct(x, 1)

# ---------------------------------------------------------------- режим «Все ЖК / Только факт»
MODES = ("Все ЖК", "Только факт")
try:
    q = st.query_params.get("mode")
    if q and st.session_state.get("_pf_q") != q:
        st.session_state["_pf_q"] = q
        st.session_state["pf_mode"] = "Только факт" if q == "fact" else "Все ЖК"
except Exception:
    pass
st.markdown('<div class="rh"><div class="kick">Отчёт для генерального директора · закрытая версия</div><div class="ttl">Портфель ЖК</div></div>',
            unsafe_allow_html=True)
with st.container(horizontal=True, key="pf_bar"):
    st.markdown('<span style="font-size:13px;color:#4A5568;font-weight:600">Выборка:</span>', unsafe_allow_html=True)
    st.segmented_control("Режим", MODES, key="pf_mode", label_visibility="collapsed", selection_mode="single")
mode = st.session_state.get("pf_mode") or MODES[0]
fact_only = mode == "Только факт"

B = PF.build(DA, P, fact_only)
projects, real, tot = B["projects"], B["real"], B["totals"]
names = [p["name"] for p in projects]
nm = lambda p: p["name"] + (" · ДЕМО" if p["demo"] else "")
tag = lambda p: U.badge("ДЕМО") if p["demo"] else U.badge("ФАКТ")
dm = ("ДЕМО",) if tot["has_demo"] else ()
sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
tr_, to_ = max(tot["risk_day"], 1), max(tot["overdue_kv"], 1)

# ---------------------------------------------------------------- 1. Сводка по портфелю
head_txt, msgs = PF.portfolio_messages(tot, projects)
lis = "".join(f"<li>{html.escape(m)}</li>" for m in msgs)
st.markdown(f'<div class="concl"><div class="t">{html.escape(head_txt)}</div><ul class="km">{lis}</ul></div>', unsafe_allow_html=True)

U.section("Ключевые показатели портфеля", "", ("ФАКТ", "ОЦЕНКА") + dm, anchor="summary", num="1.")
d_over = tot["overdue_delta"]
d_wk = (tot["week_fact"] - tot["week_prev"]) if tot["week_prev"] is not None else None
k_f, k_e = ("ФАКТ",) + dm, ("ОЦЕНКА",) + dm
U.kpi_cards([
    dict(label="Просрочено по ДДУ, квартир", value=f(tot["overdue_kv"]), risk=True, kind=k_f, delta=C.fmt_delta(d_over), foot="Δ за 7 дней"),
    dict(label="Из них готовы без замечаний", value=f(tot["ready"]), kind=k_f, delta=("", "flat"),
         foot=f"{fr(tot['ready'] / to_)} просроченных"),
    dict(label="Расчётный риск, ₽ в сутки", value=fm(tot["risk_day"]), risk=True, kind=k_e, delta=("", "flat"),
         foot=f"из них готовые квартиры: {fm(tot['ready_risk'])}"),
    dict(label="Накопленная неустойка, оценка", value=fm(tot["accrued_up"]), risk=True, kind=k_e, delta=("", "flat"),
         foot=f"нижняя оценка {fm(tot['accrued_lo'])}"),
    dict(label="Передано за неделю, квартир", value=f(tot["week_fact"]), kind=k_f,
         delta=C.fmt_delta(d_wk, good_when_down=False) if d_wk is not None else ("", "flat"),
         foot="План: " + (f(tot["week_plan"]) if tot["week_plan"] is not None else PF.NO_DATA)),
])

# ---------------------------------------------------------------- 2. Сегменты
U.section("Сегменты портфеля", "ЖК — равноправные сегменты с одним набором показателей. Выберите строку — ниже откроется разбор",
          ("ФАКТ",) + dm, anchor="segments", num="2.")
sort_lbl = {"По риску ₽/сутки": "risk", "По просрочке ДДУ": "overdue"}
sort_pick = st.radio("Сортировка", list(sort_lbl), horizontal=True, key="pf_sort")
tdf = PF.table(projects, sort_lbl[sort_pick])
ev = st.dataframe(
    tdf.drop(columns=["_name"]), hide_index=True, width="stretch", height=44 + 35 * len(tdf), key="pf_tbl",
    on_select="rerun", selection_mode="single-row",
    column_config={
        "Передано за неделю, кв.": st.column_config.NumberColumn(format="localized"),
        "Просрочено по ДДУ, кв.": st.column_config.NumberColumn(format="localized"),
        "Из них готовы": st.column_config.NumberColumn(format="localized"),
        "Доля готовых, %": st.column_config.NumberColumn(format="%.1f"),
        "Расчётный риск, ₽/сутки": st.column_config.NumberColumn(format="localized"),
        "Доля риска портфеля, %": st.column_config.NumberColumn(format="%.1f"),
        "Главная проблема": st.column_config.TextColumn(width="large"),
        "Предлагаемое действие": st.column_config.TextColumn(width="large")})
rows = list(ev.selection.rows) if ev is not None and getattr(ev, "selection", None) else []
if rows and rows[0] < len(tdf):
    pick_name = tdf.iloc[rows[0]]["_name"]
    if st.session_state.get("_pf_tsel") != pick_name:
        st.session_state["_pf_tsel"] = pick_name
        st.session_state["pf_sel"] = pick_name
U.fin_table(["", "Передано за неделю", "Просрочено по ДДУ", "Из них готовы", "Доля готовых", "Риск, ₽/сутки", "Доля риска"],
            [["Итого по портфелю", f(tot["week_fact"]), f(tot["overdue_kv"]), f(tot["ready"]), fr(tot["ready"] / to_),
              f(round(tot["risk_day"])), "100,0%"]], right=range(1, 7), total_last=True)
st.markdown(f'<div class="note">«Отклонение от плана»: плана передач по неделям у ЖК с фактическими данными нет — «{PF.NO_DATA}». '
            '«Из них готовы» — готовые к передаче без открытых замечаний, входят в «Просрочено по ДДУ».</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. Вклад сегментов в риск
U.section("Вклад сегментов в риск", "Из чего складывается суточный риск портфеля", ("ОЦЕНКА",) + dm, anchor="contribution", num="3.")
srt = sorted(projects, key=lambda p: -p["risk_day"])
cum, rows_h = 0.0, []
for p in srt:
    cum += p["risk_day"] / tr_
    rows_h.append([nm(p), f(p["overdue_kv"]), fr(p["overdue_kv"] / to_), f(round(p["risk_day"])), fr(p["risk_day"] / tr_), fr(cum), fm(p["accrued_up"])])
rows_h.append(["Итого" + (" (с ДЕМО)" if tot["has_demo"] else ""), f(tot["overdue_kv"]), "100,0%", f(round(tot["risk_day"])), "100,0%", "", fm(tot["accrued_up"])])
c1, c2 = st.columns([1, 1.4], gap="large")
with c1:
    mln = lambda x: x / 1e6
    fig = go.Figure(go.Waterfall(
        x=[nm(p) for p in srt] + ["Портфель"], measure=["relative"] * len(srt) + ["total"], y=[mln(p["risk_day"]) for p in srt] + [0],
        text=[f"{mln(p['risk_day']):.1f}".replace(".", ",") for p in srt] + [f"{mln(tot['risk_day']):.1f}".replace(".", ",")],
        textposition="outside", connector=dict(line=dict(color=U.LINE, width=1)),
        increasing=dict(marker=dict(color=U.NAVY)), totals=dict(marker=dict(color=U.RISK))))
    fig.update_layout(title="Риск в сутки, млн ₽: вклад ЖК в итог", margin=dict(l=8, r=8, t=34, b=8))
    fig.update_yaxes(showticklabels=False, range=[0, mln(tot["risk_day"]) * 1.18])
    fig.update_xaxes(tickfont=dict(size=11))
    U.chart(fig, key="pf_contrib", height=300)
with c2:
    U.fin_table(["Сегмент", "Просрочено, кв.", "Доля", "Риск, ₽/сутки", "Доля риска", "Накопл. доля", "Накоплено"], rows_h, right=range(1, 7), total_last=True)
hhi = sum((p["risk_day"] / tr_) ** 2 for p in projects) * 10000
big = srt[0]
st.markdown(f'<div class="note">Крупнейший сегмент — {fr(big["risk_day"] / tr_)} суточного риска. Индекс концентрации (HHI, 0–10 000): <b>{f(hhi)}</b> — '
            f'{"высокая концентрация" if hhi > 2500 else "умеренная концентрация"}'
            f'{"; в режиме «Только факт» сегмент один" if len(projects) == 1 else ""}.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 4. Динамика
U.section("Динамика за неделю", "Изменение просрочки и темп передачи к прошлой неделе", ("ФАКТ",) + dm, anchor="dynamics", num="4.")
v1, v2 = st.columns([1, 1.4], gap="large")
with v1:
    wf = go.Figure(go.Waterfall(
        x=[nm(p) for p in projects] + ["Портфель"], measure=["relative"] * len(projects) + ["total"],
        y=[p["overdue_delta"] for p in projects] + [0], text=[sg(p["overdue_delta"]) for p in projects] + [sg(d_over)],
        textposition="outside", connector=dict(line=dict(color=U.LINE, width=1)),
        increasing=dict(marker=dict(color=U.RISK)), decreasing=dict(marker=dict(color=U.NAVY)), totals=dict(marker=dict(color=U.SILVER))))
    lo_, hi_ = min(0, d_over, *[p["overdue_delta"] for p in projects]), max(0, *[p["overdue_delta"] for p in projects])
    wf.update_layout(title="Δ просрочки по ДДУ за 7 дней, кв.", margin=dict(l=8, r=8, t=34, b=8))
    wf.update_yaxes(showticklabels=False, range=[lo_ * 1.35 - 4, hi_ * 1.35 + 6], zeroline=True, zerolinecolor=U.LINE)
    wf.update_xaxes(tickfont=dict(size=11))
    U.chart(wf, key="pf_wf", height=300)
with v2:
    rv = []
    for p in projects + [dict(name="Итого по портфелю", demo=False, overdue_kv=tot["overdue_kv"], overdue_delta=d_over, week_fact=tot["week_fact"],
                              week_prev=tot["week_prev"], week_plan=tot["week_plan"], week_dev=None, total=True)]:
        prev_o = p["overdue_kv"] - p["overdue_delta"]
        dwk = (p["week_fact"] - p["week_prev"]) if p["week_prev"] is not None else None
        dev = p.get("week_dev")
        if p.get("total") and p["week_plan"] is not None:
            dev = p["week_fact"] - p["week_plan"]
        rv.append([nm(p) if not p.get("total") else p["name"], f(p["overdue_kv"]), f(prev_o), sg(p["overdue_delta"]),
                   fr(p["overdue_delta"] / prev_o) if prev_o else PF.NO_DATA, f(p["week_fact"]),
                   sg(dwk) if dwk is not None else PF.NO_DATA, f(p["week_plan"]) if p["week_plan"] is not None else PF.NO_DATA,
                   sg(dev) if dev is not None else PF.NO_DATA])
    U.fin_table(["Сегмент", "Просрочено сейчас", "7 дн. назад", "Δ", "Δ, %", "Передано за неделю", "Δ к прошлой неделе", "План", "Откл. от плана"],
                rv, right=range(1, 9), total_last=True)
st.markdown('<div class="note">Прошлая неделя восстановлена по датам приёма-передачи. Для ДЕМО-ЖК все значения условные.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 5. Ориентир
U.section("Ориентир: эффект решения «передать готовые»", "Расчёт при условии, что готовые квартиры передаются, остальное не меняется", ("ОЦЕНКА",) + dm,
          anchor="outlook", num="5.")
sc = []
for lab, s_ in (("Без изменений", 0.0), ("Передана половина готовых", .5), ("Переданы все готовые", 1.0)):
    n_ = tot["overdue_kv"] - s_ * tot["ready"]
    r_ = tot["risk_day"] - s_ * tot["ready_risk"]
    sc.append([lab, f(round(n_)), sg(-round(s_ * tot["ready"])) if s_ else "—", fm(r_), ("−" + fm(s_ * tot["ready_risk"])) if s_ else "—",
               fr(r_ / tr_)])
U.fin_table(["Сценарий", "Просрочено, кв.", "Δ просрочки", "Риск в сутки", "Δ риска в сутки", "К текущему риску"], sc, right=range(1, 6))

# ---------------------------------------------------------------- 6. Матрица рисков
U.section("Матрица рисков", "Квартиры по причинам просрочки в каждом ЖК; интенсивность — доля суточного риска портфеля", ("ФАКТ",) + dm, anchor="matrix", num="6.")
kinds = [k for k in PF.PROBLEMS if any(g["key"] == k for p in projects for g in p["groups"])]
mx = []
for k in kinds:
    row = [PF.PROBLEMS[k]["title"]]
    tot_n = 0
    for p in projects:
        g = next((g for g in p["groups"] if g["key"] == k), None)
        if g is None:
            row.append("—")
            continue
        a = min(.5, g["risk"] / tr_ * 1.6)
        row.append((f(g["n"]), f"background:rgba(179,38,30,{a:.2f});font-weight:600"))
        tot_n += g["n"]
    row.append(f(tot_n))
    mx.append(row)
U.fin_table(["Причина просрочки"] + [nm(p) for p in projects] + ["Итого"], mx, right=range(1, len(projects) + 2))
st.markdown('<div class="note">Каждая квартира учтена в одной причине. Чем темнее ячейка, тем больше она в суточном риске портфеля.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 7. Разбор ЖК
U.section("Разбор ЖК", "До трёх главных проблем: масштаб, корпуса, причина по данным, действие, роли и показатель контроля", ("ФАКТ",) + dm, anchor="drill", num="7.")
try:
    qj = st.query_params.get("jk")
    if qj and qj in names and st.session_state.get("_pf_qj") != qj:
        st.session_state["_pf_qj"] = qj
        st.session_state["pf_sel"] = qj
except Exception:
    pass
if st.session_state.get("pf_sel") not in names:
    st.session_state["pf_sel"] = names[0]
sel = st.radio("ЖК для разбора", names, horizontal=True, key="pf_sel")
p = next(x for x in projects if x["name"] == sel)
st.markdown(f'<div class="dec-h" style="font-size:20px">{html.escape(p["name"])}{tag(p)}</div>', unsafe_allow_html=True)
if p["demo"]:
    st.markdown(f'<div class="note">{U.badge("ДЕМО")} Условные цифры для показа структуры отчёта: в фактический итог не входят.</div>', unsafe_allow_html=True)
kd = ("ДЕМО",) if p["demo"] else ("ФАКТ",)
ke = ("ОЦЕНКА", "ДЕМО") if p["demo"] else ("ОЦЕНКА",)
U.kpi_cards([
    dict(label="Просрочено по ДДУ, квартир", value=f(p["overdue_kv"]), risk=True, kind=kd, delta=C.fmt_delta(p["overdue_delta"]),
         foot=f"{fr(p['overdue_kv'] / to_)} просрочки портфеля"),
    dict(label="Из них готовы без замечаний", value=f(p["ready"]), kind=kd, delta=("", "flat"),
         foot=f"{fr(p['ready'] / p['overdue_kv']) if p['overdue_kv'] else '—'} просрочки ЖК · риск {fm(p['ready_risk'])}/сутки"),
    dict(label="Расчётный риск, ₽ в сутки", value=fm(p["risk_day"]), risk=True, kind=ke, delta=("", "flat"), foot=f"{fr(p['risk_day'] / tr_)} риска портфеля"),
    dict(label="Передано за неделю, квартир", value=f(p["week_fact"]), kind=kd,
         delta=C.fmt_delta(p["week_fact"] - p["week_prev"], good_when_down=False) if p["week_prev"] is not None else ("", "flat"),
         foot=(f"план {f(p['week_plan'])}, отклонение {sg(p['week_dev'])}" if p["week_plan"] is not None else f"План: {PF.NO_DATA}")),
])
for i, pr in enumerate(p["problems"], 1):
    roles = "".join(f'<span class="pf-role">{html.escape(r)}</span>' for r in pr["roles"])
    st.markdown(
        f'<div class="dec-h"><span class="no">{i}</span>{html.escape(pr["title"])}{tag(p)}</div>'
        f'<div class="dec"><div><div class="k">Масштаб</div><div class="v"><span class="big">{f(pr["n"])} {pl(pr["n"])}</span>'
        f'≈{fm(pr["risk"])} в сутки · {fr(pr["share_risk"])} риска ЖК<br>Корпуса: {html.escape(pr["korpusa"])}</div></div>'
        f'<div><div class="k">Причина по данным</div><div class="v">{html.escape(pr["cause"])}</div></div>'
        f'<div><div class="k">Предлагаемое действие</div><div class="v">{html.escape(pr["action"])}<br><br>'
        f'<span class="k">Подключить</span><br>{roles}</div></div>'
        f'<div><div class="k">Проверим на следующем совещании</div><div class="v">{html.escape(pr["metric"])}<br>'
        f'<b>Сейчас: {f(pr["baseline"])}</b></div></div></div>', unsafe_allow_html=True)
if not p["demo"] and len(p["by_korpus"]):
    bk = p["by_korpus"].head(8).iloc[::-1]
    fig = go.Figure(go.Bar(y=bk["k"], x=bk["n"], orientation="h", marker_color=U.NAVY,
                           text=[f"{f(n)} кв. · {fm(r)}/сутки" for n, r in zip(bk["n"], bk["risk"])], textposition="outside", cliponaxis=False,
                           hovertemplate="корпус %{y}: %{x} кв.<extra></extra>"))
    fig.update_layout(title="Корпуса: просрочено квартир и риск в сутки", margin=dict(l=8, r=150, t=34, b=8), bargap=.4)
    fig.update_xaxes(showticklabels=False)
    U.chart(fig, key="pf_korp", height=max(200, 36 * len(bk) + 64))

# ---------------------------------------------------------------- 8. Деньги
U.section("Деньги: риск, требования, подтверждённые суммы", "Три разных показателя — суммировать их нельзя", ("ОЦЕНКА",) + dm, anchor="money", num="8.")
dem_ps = [x for x in projects if x["demo"]]
claims_txt = fm(tot["claims"]) if tot["claims"] is not None else PF.NO_DATA
conf_txt = fm(tot["confirmed"]) if tot["confirmed"] is not None else PF.NO_DATA
cl_note = "Нет предъявленных требований и исков" if not dem_ps else "Для ЖК с фактическими данными — нет; у ДЕМО-ЖК условно " + fm(sum(x["claims"] for x in dem_ps))
cf_note = "Нет подтверждённых сумм" if not dem_ps else "Для ЖК с фактическими данными — нет; у ДЕМО-ЖК условно " + fm(sum(x["confirmed"] for x in dem_ps))
U.kpi_cards([
    dict(label="Расчётный риск: накоплено (верхняя оценка)", value=fm(tot["accrued_up"]), risk=True, kind=k_e, delta=("", "flat"),
         foot=f"нижняя оценка {fm(tot['accrued_lo'])} · в сутки ≈{fm(tot['risk_day'])}"),
    dict(label="Предъявленные требования", value=claims_txt, kind="ФАКТ" if tot["claims"] is None else "ДЕМО", delta=("", "flat"), foot=cl_note),
    dict(label="Подтверждённые суммы", value=conf_txt, kind="ФАКТ" if tot["confirmed"] is None else "ДЕМО", delta=("", "flat"), foot=cf_note),
])

# ---------------------------------------------------------------- 9. Поручения
U.section("Контроль поручений", "Что поручено, кого подключить и какой показатель проверим на следующем совещании", ("ФАКТ",) + dm, anchor="orders", num="9.")
ro = [[str(i), nm(p_), pr["action"], ", ".join(pr["roles"]), pr["metric"], f(pr["baseline"])]
      for i, (p_, pr) in enumerate(((p_, pr) for p_ in projects for pr in p_["problems"]), 1)]
U.fin_table(["№", "ЖК", "Поручение", "Кого подключить", "Показатель на следующем совещании", "Сейчас"], ro, right=(5,))
st.markdown('<div class="note">Исполнители указаны ролями, сроки не задаются: на следующем совещании сравниваем «Сейчас» с новым значением.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 10. Допущения
U.section("Допущения модели", "", ("ОЦЕНКА",), anchor="notes", num="10.")
U.sources(
    f"Расчётный риск в сутки = ключевая ставка / 300 × 2 (участник — гражданин, ч.2 ст.6 214-ФЗ) × цена квартиры; цена принята условно {pm} млн ₽ "
    "(меняется в боковой панели, риск пересчитывается пропорционально). Коммерческие помещения не считаются; машиноместа и кладовые — отдельно по условным ценам. "
    "«Накоплено» — сумма за весь период просрочки (верхняя и нижняя оценка), не начислено и не предъявлено. "
    "«Готовы» — открыты к передаче и без открытых замечаний; входят в просрочку, их риск — часть общего."
    + ("" if fact_only else f" ДЕМО-ЖК: условное число квартир × средняя ставка по ЖК с фактическими данными × та же цена; накопленная сумма — условные {PF.DEMO_DAYS} дн.")
    + " Персональные данные в отчёт не входят.")
