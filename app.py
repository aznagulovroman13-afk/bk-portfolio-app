"""Портфель ЖК — отчёт для генерального директора (отдельное закрытое приложение).

Запуск: streamlit run app.py   ·   доступ: SHOW_REAL_DATA = "yes" в secrets (иначе — нейтральная заглушка).
"""
import html

import pandas as pd
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
def _load_projects(schema: str = "v4"):   # schema — часть ключа кэша: при смене формата данных старый кэш не подхватывается
    return pf_data.load(True)


try:
    DA = _load_projects()
except pf_data.LockedError:
    st.error("Данные недоступны: проверьте ключ данных в настройках приложения.")
    st.stop()
with st.sidebar:
    if st.button("Выйти", key="pf_exit"):
        st.session_state.clear()
        st.rerun()
    st.markdown("**Допущения расчёта**")
    price_m = st.number_input("Цена квартиры по ДДУ, млн ₽ (допущение)", min_value=1.0, max_value=60.0, value=10.0, step=0.5, key="pf_price")
    st.caption("Цен по ДДУ в данных нет — риск пересчитывается пропорционально цене. "
               "Машиноместа и кладовые — по расчётным ценам, коммерция не считается.")
pm = f"{price_m:.1f}".replace(".", ",")
P = dict(price=price_m * 1e6, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
f, fm = C.fmt_int, C.fmt_money
pl = lambda n: C.plural(n, "квартира", "квартиры", "квартир")
fr = lambda x: C.fmt_pct(x, 1)

import pf_detail as DT  # noqa: E402

st.markdown('<div class="rh"><div class="kick">Отчёт для генерального директора · закрытая версия</div><div class="ttl">Портфель ЖК</div></div>',
            unsafe_allow_html=True)


@st.cache_data(show_spinner="Расчёт…")
def _build(price_rub: float, schema: str = "v4"):
    return PF.build(DA, dict(price=price_rub, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE))


B = _build(P["price"])
projects, tot = B["projects"], B["totals"]
names = [p["name"] for p in projects]
sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
tr_, to_ = max(tot["risk_day"], 1), max(tot["overdue_kv"], 1)
COLORS = {names[0]: U.NAVY, names[1]: U.GOLD, names[2]: U.SILVER}

# ---------------------------------------------------------------- 1. Сводка по портфелю
head_txt, msgs = PF.portfolio_messages(tot, projects)
lis = "".join(f"<li>{html.escape(m)}</li>" for m in msgs)
st.markdown(f'<div class="concl"><div class="t">{html.escape(head_txt)}</div><ul class="km">{lis}</ul></div>', unsafe_allow_html=True)

U.section("Ключевые показатели портфеля", "", anchor="summary", num="1.")
d_over = tot["overdue_delta"]
d_wk = (tot["week_fact"] - tot["week_prev"]) if tot["week_prev"] is not None else None
U.kpi_cards([
    dict(label="Просрочено по ДДУ, квартир", value=f(tot["overdue_kv"]), risk=True, delta=C.fmt_delta(d_over), foot="Δ за 7 дней"),
    dict(label="Из них готовы без замечаний", value=f(tot["ready"]), delta=("", "flat"), foot=f"{fr(tot['ready'] / to_)} просроченных"),
    dict(label="Расчётный риск, ₽ в сутки", value=fm(tot["risk_day"]), risk=True, delta=("", "flat"),
         foot=f"из них готовые квартиры: {fm(tot['ready_risk'])}"),
    dict(label="Накопленная неустойка, оценка", value=fm(tot["accrued_up"]), risk=True, delta=("", "flat"), foot=f"нижняя оценка {fm(tot['accrued_lo'])}"),
    dict(label="Передано за неделю, квартир", value=f(tot["week_fact"]),
         delta=C.fmt_delta(d_wk, good_when_down=False) if d_wk is not None else ("", "flat"), foot="Δ к прошлой неделе"),
    dict(label="Открытых замечаний", value=f(tot["remarks"]), delta=("", "flat"),
         foot=f"критических {f(tot['critical'])} · просрочено {fr(tot['remarks_over'] / max(tot['remarks'], 1))}"),
])

# ---------------------------------------------------------------- 2. Сегменты
U.section("Сегменты портфеля", "ЖК — равноправные сегменты с одним набором показателей. Выберите строку — ниже откроется разбор",
          anchor="segments", num="2.")
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
        "Открытых замечаний": st.column_config.NumberColumn(format="localized"),
        "Главная проблема": st.column_config.TextColumn(width="large"),
        "Предлагаемое действие": st.column_config.TextColumn(width="large")})
rows = list(ev.selection.rows) if ev is not None and getattr(ev, "selection", None) else []
if rows and rows[0] < len(tdf):
    pick_name = tdf.iloc[rows[0]]["_name"]
    if st.session_state.get("_pf_tsel") != pick_name:
        st.session_state["_pf_tsel"] = pick_name
        st.session_state["pf_sel"] = pick_name
U.fin_table(["", "Передано за неделю", "Просрочено по ДДУ", "Из них готовы", "Доля готовых", "Риск, ₽/сутки", "Доля риска", "Открытых замечаний"],
            [["Итого по портфелю", f(tot["week_fact"]), f(tot["overdue_kv"]), f(tot["ready"]), fr(tot["ready"] / to_),
              f(round(tot["risk_day"])), "100,0%", f(tot["remarks"])]], right=range(1, 8), total_last=True)
st.markdown('<div class="note">«Из них готовы» — готовые к передаче без открытых замечаний, входят в «Просрочено по ДДУ».</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. Вклад сегментов в риск
U.section("Вклад сегментов в риск", "Из чего складывается суточный риск портфеля", anchor="contribution", num="3.")
srt = sorted(projects, key=lambda p: -p["risk_day"])
cum, rows_h = 0.0, []
for p in srt:
    cum += p["risk_day"] / tr_
    rows_h.append([p["name"], f(p["overdue_kv"]), fr(p["overdue_kv"] / to_), f(round(p["risk_day"])), fr(p["risk_day"] / tr_), fr(cum), fm(p["accrued_up"])])
rows_h.append(["Итого", f(tot["overdue_kv"]), "100,0%", f(round(tot["risk_day"])), "100,0%", "", fm(tot["accrued_up"])])
c1, c2 = st.columns([1, 1.4], gap="large")
with c1:
    mln = lambda x: x / 1e6
    fig = go.Figure(go.Waterfall(
        x=[p["name"] for p in srt] + ["Портфель"], measure=["relative"] * len(srt) + ["total"], y=[mln(p["risk_day"]) for p in srt] + [0],
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
            f'{"высокая концентрация" if hhi > 2500 else "умеренная концентрация"}.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 4. Динамика
U.section("Динамика за неделю", "Изменение просрочки и темп передачи к прошлой неделе", anchor="dynamics", num="4.")
v1, v2 = st.columns([1, 1.4], gap="large")
with v1:
    wf = go.Figure(go.Waterfall(
        x=[p["name"] for p in projects] + ["Портфель"], measure=["relative"] * len(projects) + ["total"],
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
    for p in projects + [dict(name="Итого по портфелю", overdue_kv=tot["overdue_kv"], overdue_delta=d_over, week_fact=tot["week_fact"],
                              week_prev=tot["week_prev"], total=True)]:
        prev_o = p["overdue_kv"] - p["overdue_delta"]
        dwk = (p["week_fact"] - p["week_prev"]) if p["week_prev"] is not None else None
        rv.append([p["name"], f(p["overdue_kv"]), f(prev_o), sg(p["overdue_delta"]),
                   fr(p["overdue_delta"] / prev_o) if prev_o else PF.NO_DATA, f(p["week_fact"]), sg(dwk) if dwk is not None else PF.NO_DATA])
    U.fin_table(["Сегмент", "Просрочено сейчас", "7 дн. назад", "Δ", "Δ, %", "Передано за неделю", "Δ к прошлой неделе"], rv, right=range(1, 7), total_last=True)
lf = go.Figure()
for p in projects:
    w = p["weekly"]
    lf.add_scatter(x=w["Неделя"], y=w["Просрочено на конец недели, кв."], mode="lines+markers", name=p["name"], line=dict(color=COLORS[p["name"]], width=2.5))
lf.update_layout(title="Просрочено по ДДУ на конец недели, квартир", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.18),
                 hovermode="x unified")
lf.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
U.chart(lf, key="pf_line", height=300)
st.markdown('<div class="note">Прошлая неделя восстановлена по датам приёма-передачи.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 5. Ориентир
U.section("Ориентир: эффект решения «передать готовые»", "Расчёт при условии, что готовые квартиры передаются, остальное не меняется",
          anchor="outlook", num="5.")
sc = []
for lab, s_ in (("Без изменений", 0.0), ("Передана половина готовых", .5), ("Переданы все готовые", 1.0)):
    n_ = tot["overdue_kv"] - s_ * tot["ready"]
    r_ = tot["risk_day"] - s_ * tot["ready_risk"]
    sc.append([lab, f(round(n_)), sg(-round(s_ * tot["ready"])) if s_ else "—", fm(r_), ("−" + fm(s_ * tot["ready_risk"])) if s_ else "—", fr(r_ / tr_)])
U.fin_table(["Сценарий", "Просрочено, кв.", "Δ просрочки", "Риск в сутки", "Δ риска в сутки", "К текущему риску"], sc, right=range(1, 6))

# ---------------------------------------------------------------- 6. Матрица рисков
U.section("Матрица рисков", "Квартиры по причинам просрочки в каждом ЖК; интенсивность — доля суточного риска портфеля", anchor="matrix", num="6.")
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
U.fin_table(["Причина просрочки"] + names + ["Итого"], mx, right=range(1, len(projects) + 2))
st.markdown('<div class="note">Каждая квартира учтена в одной причине. Чем темнее ячейка, тем больше она в суточном риске портфеля.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 7. Разбор ЖК
U.section("Разбор ЖК", "Одинаковый набор для каждого ЖК: обзор и главные проблемы, шахматка, замечания, подрядчики, деньги, динамика", anchor="drill", num="7.")
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
d = DA[p["key"]]
A_, REM, CT = d["units"], d["remarks"], d["contractors"]
st.markdown(f'<div class="dec-h" style="font-size:20px">{html.escape(p["name"])}</div>', unsafe_allow_html=True)
tabs = st.tabs(["Обзор", "Шахматка", "Замечания", "Подрядчики", "Деньги", "Динамика"])

with tabs[0]:
    U.kpi_cards([
        dict(label="Просрочено по ДДУ, квартир", value=f(p["overdue_kv"]), risk=True, delta=C.fmt_delta(p["overdue_delta"]),
             foot=f"{fr(p['overdue_kv'] / to_)} просрочки портфеля"),
        dict(label="Из них готовы без замечаний", value=f(p["ready"]), delta=("", "flat"),
             foot=f"{fr(p['ready'] / p['overdue_kv']) if p['overdue_kv'] else '—'} просрочки ЖК · риск {fm(p['ready_risk'])}/сутки"),
        dict(label="Расчётный риск, ₽ в сутки", value=fm(p["risk_day"]), risk=True, delta=("", "flat"), foot=f"{fr(p['risk_day'] / tr_)} риска портфеля"),
        dict(label="Передано за неделю, квартир", value=f(p["week_fact"]),
             delta=C.fmt_delta(p["week_fact"] - p["week_prev"], good_when_down=False) if p["week_prev"] is not None else ("", "flat"),
             foot="Δ к прошлой неделе"),
        dict(label="Открытых замечаний", value=f(p["remarks"]), delta=("", "flat"), foot=f"критических {f(p['critical'])}"),
    ])
    st.markdown('<div class="dec-h" style="font-size:17px">Три главные проблемы</div>', unsafe_allow_html=True)
    for i, pr in enumerate(p["problems"], 1):
        roles = "".join(f'<span class="pf-role">{html.escape(r)}</span>' for r in pr["roles"])
        st.markdown(
            f'<div class="dec-h"><span class="no">{i}</span>{html.escape(pr["title"])}</div>'
            f'<div class="dec"><div><div class="k">Масштаб</div><div class="v"><span class="big">{f(pr["n"])} {pl(pr["n"])}</span>'
            f'≈{fm(pr["risk"])} в сутки · {fr(pr["share_risk"])} риска ЖК<br>Корпуса: {html.escape(pr["korpusa"])}</div></div>'
            f'<div><div class="k">Причина по данным</div><div class="v">{html.escape(pr["cause"])}</div></div>'
            f'<div><div class="k">Предлагаемое действие</div><div class="v">{html.escape(pr["action"])}<br><br>'
            f'<span class="k">Подключить</span><br>{roles}</div></div>'
            f'<div><div class="k">Проверим на следующем совещании</div><div class="v">{html.escape(pr["metric"])}<br>'
            f'<b>Сейчас: {f(pr["baseline"])}</b></div></div></div>', unsafe_allow_html=True)
    if len(p["by_korpus"]):
        bk = p["by_korpus"].head(8).iloc[::-1]
        fig = go.Figure(go.Bar(y=bk["k"], x=bk["n"], orientation="h", marker_color=U.NAVY,
                               text=[f"{f(n)} кв. · {fm(r)}/сутки" for n, r in zip(bk["n"], bk["risk"])], textposition="outside", cliponaxis=False,
                               hovertemplate="корпус %{y}: %{x} кв.<extra></extra>"))
        fig.update_layout(title="Корпуса: просрочено квартир и риск в сутки", margin=dict(l=8, r=150, t=34, b=8), bargap=.4)
        fig.update_xaxes(showticklabels=False)
        U.chart(fig, key=f"pf_korp_{p['key']}", height=max(200, 36 * len(bk) + 64))
    st.markdown('<div class="dec-h" style="font-size:17px">Корпуса</div>', unsafe_allow_html=True)
    kt = DT.korpus_table(A_, P["price"])
    st.dataframe(kt, hide_index=True, width="stretch", height=min(44 + 35 * len(kt), 420), key=f"pf_kt_{p['key']}",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in kt.columns if c not in ("Корпус", "Передано, %")}
                 | {"Передано, %": st.column_config.NumberColumn(format="%.1f")})

with tabs[1]:
    ks = DT.korpus_list(A_)
    kt2 = DT.korpus_table(A_, P["price"]).set_index("Корпус")
    dflt = int(kt2["Риск, ₽/сутки"].reset_index(drop=True).idxmax())
    kk = st.selectbox("Корпус", ks, index=dflt, key=f"pf_chess_{p['key']}", format_func=lambda k: f"Корпус {k}")
    row = kt2.loc[kk]
    st.markdown(f'<div class="note">Корпус {html.escape(kk)}: помещений {f(row["Помещений"])}, передано {fr(row["Передано, %"] / 100)}, просрочено по ДДУ {f(row["Просрочено по ДДУ"])}, '
                f'замечаний {f(row["Замечаний"])}. Строки — этажи, колонки — секции.</div>', unsafe_allow_html=True)
    ch, _ = DT.chess_html(A_, kk)
    st.markdown(ch, unsafe_allow_html=True)

with tabs[2]:
    imp = DT.remark_importance(REM)
    U.kpi_cards([
        dict(label="Открытых замечаний", value=f(p["remarks"]), delta=("", "flat"), foot=f"{f(p['remarks'] / max(p['units'], 1))} на помещение"),
        dict(label="Критических", value=f(p["critical"]), risk=True, delta=("", "flat"), foot=fr(p["critical"] / max(p["remarks"], 1)) + " от всех"),
        dict(label="Просрочено по регламенту", value=fr(p["remarks_over"] / max(p["remarks"], 1)), risk=True, delta=("", "flat"), foot=f"{f(p['remarks_over'])} замечаний"),
        dict(label="Блокируют передачу", value=f(p["blocking"]), delta=("", "flat"), foot="замечаний по помещениям без акта"),
        dict(label="Оценка стоимости устранения", value=fm(p["remarks_cost"]), delta=("", "flat"), foot="оценка по средней стоимости замечания"),
    ])
    g = DT.remark_groups(REM)
    r1, r2 = st.columns(2, gap="large")
    with r1:
        fg = go.Figure()
        fg.add_bar(y=g["Группа"][::-1], x=g["Замечаний"][::-1] - g["Просрочено более 45 дн."][::-1], orientation="h", name="В срок", marker_color=U.SILVER)
        fg.add_bar(y=g["Группа"][::-1], x=g["Просрочено более 45 дн."][::-1], orientation="h", name="Просрочено более 45 дн.", marker_color=U.RISK)
        fg.update_layout(barmode="stack", title="Замечания по категориям", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.2))
        U.chart(fg, key=f"pf_rg_{p['key']}", height=300)
    with r2:
        ag = DT.remark_ages(REM)
        fa = go.Figure(go.Bar(x=ag["Возраст замечания"], y=ag["Замечаний"], marker_color=U.NAVY, text=[f(v) for v in ag["Замечаний"]], textposition="outside"))
        fa.update_layout(title="Возраст открытых замечаний", margin=dict(l=8, r=8, t=34, b=8))
        fa.update_yaxes(showticklabels=False)
        U.chart(fa, key=f"pf_ra_{p['key']}", height=300)
    U.fin_table(["Категория", "Замечаний", "Доля", "Критических", "Просрочено более 45 дн.", "% просрочено", "Блокируют передачу"],
                [[r["Группа"], f(r["Замечаний"]), f"{r['Доля, %']:.1f}%".replace(".", ","), f(r["Критических"]), f(r["Просрочено более 45 дн."]),
                  f"{r['% просрочено']:.1f}%".replace(".", ","), f(r["Блокируют передачу"])] for _, r in g.iterrows()]
                + [["Итого", f(g["Замечаний"].sum()), "100,0%", f(g["Критических"].sum()), f(g["Просрочено более 45 дн."].sum()),
                    C.fmt_pct(g["Просрочено более 45 дн."].sum() / max(g["Замечаний"].sum(), 1), 1), f(g["Блокируют передачу"].sum())]],
                right=range(1, 7), total_last=True)
    st.markdown(f'<div class="note">По важности: критических {f(imp["Критическое"])}, значительных {f(imp["Значительное"])}, стандартных {f(imp["Стандартное"])}.</div>',
                unsafe_allow_html=True)
    rk = DT.remark_korpus(REM)
    fk = go.Figure(go.Bar(y=rk["Корпус"][::-1], x=rk["n"][::-1], orientation="h", marker_color=U.NAVY, text=[f(v) for v in rk["n"][::-1]], textposition="outside", cliponaxis=False))
    fk.update_layout(title="Корпуса с наибольшим числом замечаний", margin=dict(l=8, r=40, t=34, b=8), bargap=.4)
    fk.update_xaxes(showticklabels=False)
    U.chart(fk, key=f"pf_rk_{p['key']}", height=max(220, 30 * len(rk) + 64))

with tabs[3]:
    cls = CT["Класс риска"].value_counts()
    U.kpi_cards([
        dict(label="Подрядчиков с замечаниями", value=f(len(CT)), delta=("", "flat"), foot="по числу открытых замечаний"),
        dict(label="Высокий риск", value=f(cls.get("высокий", 0)), risk=True, delta=("", "flat"), foot="балл риска 60 и выше"),
        dict(label="Средний риск", value=f(cls.get("средний", 0)), delta=("", "flat"), foot="балл риска 30–60"),
        dict(label="Низкий риск", value=f(cls.get("низкий", 0)), delta=("", "flat"), foot="балл риска ниже 30"),
        dict(label="Мало данных", value=f(cls.get("мало данных", 0)), delta=("", "flat"), foot="меньше 50 замечаний"),
    ])
    ct = CT.sort_values("Балл риска", ascending=False).reset_index(drop=True)
    top = ct.head(10).iloc[::-1]
    fc = go.Figure(go.Bar(y=top["Подрядчик"], x=top["Балл риска"], orientation="h",
                          marker_color=[U.RISK if c == "высокий" else U.NAVY if c == "средний" else U.SILVER for c in top["Класс риска"]],
                          text=[f"{v:.1f}".replace(".", ",") for v in top["Балл риска"]], textposition="outside", cliponaxis=False))
    fc.update_layout(title="Балл риска подрядчиков (10 крупнейших по баллу)", margin=dict(l=8, r=40, t=34, b=8), bargap=.4)
    fc.update_xaxes(showticklabels=False, range=[0, 110])
    U.chart(fc, key=f"pf_ctr_{p['key']}", height=340)
    view = pd.DataFrame({
        "Подрядчик": ct["Подрядчик"], "Группа": ct["Группа"], "Замечаний": ct["Замечаний"], "Квартир": ct["Квартир"], "Просрочено": ct["Просрочено"],
        "% просрочено": (100 * ct["% просрочено"]).round(1), "Критических": ct["Критических"], "Блокирует квартир": ct["Блок. квартир"].astype(int),
        "Балл риска": ct["Балл риска"], "Класс риска": ct["Класс риска"], "Стоимость устранения, ₽": ct["Оценка стоимости открытых, ₽"].round().astype(int)})
    st.dataframe(view, hide_index=True, width="stretch", height=min(44 + 35 * len(view), 460), key=f"pf_ctt_{p['key']}",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in ("Замечаний", "Квартир", "Просрочено", "Критических", "Блокирует квартир", "Стоимость устранения, ₽")}
                 | {"% просрочено": st.column_config.NumberColumn(format="%.1f"), "Балл риска": st.column_config.NumberColumn(format="%.1f")})
    st.markdown('<div class="note">Балл риска (0–100) собран из доли просроченных и критических замечаний, средней просрочки, числа блокируемых квартир и объёма замечаний. '
                'Названия подрядчиков даны без реквизитов.</div>', unsafe_allow_html=True)

with tabs[4]:
    pen = p["penalty"]
    U.kpi_cards([
        dict(label="Расчётный риск, ₽ в сутки", value=fm(p["risk_day"]), risk=True, delta=("", "flat"), foot=f"из них готовые квартиры: {fm(p['ready_risk'])}"),
        dict(label="Накоплено, верхняя оценка", value=fm(p["accrued_up"]), risk=True, delta=("", "flat"), foot=f"нижняя оценка {fm(p['accrued_lo'])}"),
        dict(label="Стоимость устранения замечаний", value=fm(p["remarks_cost"]), delta=("", "flat"), foot=f"{f(p['remarks'])} замечаний"),
        dict(label="Потенциал претензий к подрядчикам", value=fm(p["claim_potential"]), delta=("", "flat"), foot="по просроченным замечаниям, оценка"),
        dict(label="Предъявленные требования", value=PF.NO_DATA, delta=("", "flat"), foot="нет предъявленных требований и исков"),
        dict(label="Подтверждённые суммы", value=PF.NO_DATA, delta=("", "flat"), foot="нет подтверждённых сумм"),
    ])
    bk_ = pen["by_korpus"].head(10)
    U.fin_table(["Корпус", "Квартир с неустойкой", "из них не переданы", "Накоплено, верхняя оценка", "Накоплено, нижняя оценка"],
                [[r["Корпус"], f(r["kv"]), f(r["nt"]), fm(r["up"]), fm(r["lo"])] for _, r in bk_.iterrows()], right=range(1, 5))
    st.markdown('<div class="note">Риск, требования и подтверждённые суммы — разные показатели, суммировать их нельзя. Показаны 10 корпусов с наибольшей накопленной суммой.</div>',
                unsafe_allow_html=True)

with tabs[5]:
    w = p["weekly"]
    z1, z2 = st.columns(2, gap="large")
    with z1:
        fw = go.Figure(go.Bar(x=w["Неделя"], y=w["Передано, квартир"], marker_color=U.NAVY, text=w["Передано, квартир"], textposition="outside"))
        fw.update_layout(title="Передано квартир по неделям", margin=dict(l=8, r=8, t=34, b=8))
        fw.update_yaxes(showticklabels=False)
        fw.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        U.chart(fw, key=f"pf_wt_{p['key']}", height=300)
    with z2:
        fo = go.Figure(go.Scatter(x=w["Неделя"], y=w["Просрочено на конец недели, кв."], mode="lines+markers", line=dict(color=U.RISK, width=2.5)))
        fo.update_layout(title="Просрочено по ДДУ на конец недели, квартир", margin=dict(l=8, r=8, t=34, b=8))
        fo.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
        fo.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        U.chart(fo, key=f"pf_wo_{p['key']}", height=300)
    U.fin_table(["Неделя", "Передано, квартир", "Передано, всего", "Просрочено на конец недели, кв."],
                [[r["Неделя"] + (" (неполная)" if r["partial"] else ""), f(r["Передано, квартир"]), f(r["Передано, всего"]), f(r["Просрочено на конец недели, кв."])]
                 for _, r in w.iterrows()], right=range(1, 4))

# ---------------------------------------------------------------- 8. Деньги по портфелю
U.section("Деньги: риск, требования, подтверждённые суммы", "Три разных показателя — суммировать их нельзя", anchor="money", num="8.")
U.kpi_cards([
    dict(label="Расчётный риск: накоплено (верхняя оценка)", value=fm(tot["accrued_up"]), risk=True, delta=("", "flat"),
         foot=f"нижняя оценка {fm(tot['accrued_lo'])} · в сутки ≈{fm(tot['risk_day'])}"),
    dict(label="Стоимость устранения замечаний", value=fm(tot["remarks_cost"]), delta=("", "flat"), foot=f"{f(tot['remarks'])} замечаний"),
    dict(label="Предъявленные требования", value=PF.NO_DATA, delta=("", "flat"), foot="Нет предъявленных требований и исков"),
    dict(label="Подтверждённые суммы", value=PF.NO_DATA, delta=("", "flat"), foot="Нет подтверждённых сумм"),
])
U.fin_table(["ЖК", "Риск, ₽/сутки", "Накоплено, верхняя", "Накоплено, нижняя", "Стоимость устранения замечаний", "Потенциал претензий", "Требования", "Подтверждено"],
            [[x["name"], f(round(x["risk_day"])), fm(x["accrued_up"]), fm(x["accrued_lo"]), fm(x["remarks_cost"]), fm(x["claim_potential"]), PF.NO_DATA, PF.NO_DATA]
             for x in projects] + [["Итого", f(round(tot["risk_day"])), fm(tot["accrued_up"]), fm(tot["accrued_lo"]), fm(tot["remarks_cost"]), fm(tot["claim_potential"]),
                                    PF.NO_DATA, PF.NO_DATA]], right=range(1, 8), total_last=True)

# ---------------------------------------------------------------- 9. Поручения
U.section("Контроль поручений", "Что поручено, кого подключить и какой показатель проверим на следующем совещании", anchor="orders", num="9.")
ro = [[str(i), p_["name"], pr["action"], ", ".join(pr["roles"]), pr["metric"], f(pr["baseline"])]
      for i, (p_, pr) in enumerate(((p_, pr) for p_ in projects for pr in p_["problems"]), 1)]
U.fin_table(["№", "ЖК", "Поручение", "Кого подключить", "Показатель на следующем совещании", "Сейчас"], ro, right=(5,))
st.markdown('<div class="note">Исполнители указаны ролями, сроки не задаются: на следующем совещании сравниваем «Сейчас» с новым значением.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 10. Допущения
U.section("Допущения модели", "", anchor="notes", num="10.")
U.sources(
    f"Расчётный риск в сутки = ключевая ставка / 300 × 2 (участник — гражданин, ч.2 ст.6 214-ФЗ) × цена квартиры; цена принята {pm} млн ₽ (допущение) "
    "(меняется в боковой панели, риск пересчитывается пропорционально). Коммерческие помещения не считаются; машиноместа и кладовые — отдельно по расчётным ценам. "
    "«Накоплено» — сумма за весь период просрочки (верхняя и нижняя оценка), не начислено и не предъявлено. "
    "«Готовы» — открыты к передаче и без открытых замечаний; входят в просрочку, их риск — часть общего. "
    "Стоимость устранения и потенциал претензий — оценка по средней стоимости замечания; потенциал — трёхкратная стоимость просроченных замечаний. "
    "Персональные данные в отчёт не входят.")
if PF.MODEL_NOTE:
    st.markdown(f'<div class="src" style="font-size:10.5px;margin-top:2px">{html.escape(PF.MODEL_NOTE)}</div>', unsafe_allow_html=True)
