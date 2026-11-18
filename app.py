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
    '<div class="pfnav"><b>ПОРТФЕЛЬ ЖК</b><a href="#summary">Сводка</a><a href="#portfolio">Портфель</a>'
    '<a href="#concentration">Концентрация</a><a href="#variance">Отклонения</a><a href="#drill">Разбор ЖК</a>'
    '<a href="#money">Деньги</a><a href="#orders">Поручения</a><a href="#recon">Сверка</a><a href="#notes">Примечания</a>'
    '<span class="pfr">закрытая версия</span></div>', unsafe_allow_html=True)


@st.cache_data(show_spinner="Загрузка среза…")
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
B0 = None
real0 = PF.real_project(DA, P)
hdr_slot = st.empty()
_demo_meta = lambda fo: "" if fo else '<span>Прокшино и Дзен-кварталы: <b>условные цифры (ДЕМО)</b></span>'
_hdr = lambda fo: (
    f'<div class="rh"><div class="kick">Отчёт для генерального директора · закрытая версия</div><div class="ttl">Портфель ЖК</div>'
    f'<div class="meta"><span>Дата среза: <b>{real0["snapshot"]}</b></span><span>Источник: <b>действующий отчёт по Бунинским кварталам</b> '
    f'({html.escape(real0["snapshot_parts"])})</span>{_demo_meta(fo)}'
    f'<span>Цена квартиры в модели: <b>{pm} млн ₽</b> (допущение)</span></div></div>')
with st.container(horizontal=True, key="pf_bar"):
    st.markdown('<span style="font-size:13px;color:#4A5568;font-weight:600">Выборка:</span>', unsafe_allow_html=True)
    st.segmented_control("Режим", MODES, key="pf_mode", label_visibility="collapsed", selection_mode="single")
mode = st.session_state.get("pf_mode") or MODES[0]
fact_only = mode == "Только факт"
hdr_slot.markdown(_hdr(fact_only), unsafe_allow_html=True)

B = PF.build(DA, P, fact_only)
projects, real, tot = B["projects"], B["real"], B["totals"]
names = [p["name"] for p in projects]
tag = lambda p: U.badge("ДЕМО") if p["demo"] else U.badge("ФАКТ")
dm = ("ДЕМО",) if tot["has_demo"] else ()

# ---------------------------------------------------------------- 1. Executive summary
head, decision = PF.main_conclusion(tot)
sub = html.escape(decision)
if tot["has_demo"]:
    sub += " В сводке есть условные цифры ДЕМО; фактический итог — в режиме «Только факт» и в строке «из них факт»."
st.markdown(f'<div class="concl"><div class="t">{html.escape(head)}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)

U.section("Сводка для совещания", "Четыре ключевых показателя и решения", ("ФАКТ", "ОЦЕНКА") + dm, anchor="summary", num="1.")
d_over = sum(p["overdue_delta"] for p in projects)
wk_prev = [p["week_prev"] for p in projects]
d_wk = (tot["week_fact"] - sum(wk_prev)) if all(x is not None for x in wk_prev) else None
fact = tot["fact"]
k_f = ("ФАКТ",) + dm
k_e = ("ОЦЕНКА",) + dm
U.kpi_cards([
    dict(label="Просрочено по ДДУ, квартир", value=f(tot["overdue_kv"]), risk=True, kind=k_f, delta=C.fmt_delta(d_over),
         foot="Δ за 7 дней по датам ПА" + (f" · факт {f(fact['overdue_kv'])}" if tot["has_demo"] else "")),
    dict(label="Из них готовы без замечаний", value=f(tot["ready"]), kind=k_f, delta=("", "flat"),
         foot=f"{fr(tot['ready'] / max(tot['overdue_kv'], 1))} просроченных; риск готовых {fm(tot['ready_risk'])}/сутки"),
    dict(label="Расчётный риск, ₽ в сутки", value=fm(tot["risk_day"]), risk=True, kind=k_e, delta=("", "flat"),
         foot="неустойка по ДДУ, ч.2 ст.6 214-ФЗ" + (f" · факт {fm(fact['risk_day'])}" if tot["has_demo"] else "")),
    dict(label="Передано за неделю, квартир", value=f(tot["week_fact"]), kind=k_f,
         delta=C.fmt_delta(d_wk, good_when_down=False) if d_wk is not None else ("Нет данных о прошлой неделе", "flat"),
         foot="План: " + (f(tot["week_plan"]) if tot["week_plan"] is not None else
                          "Нет данных" + (" (у Бунинских плана нет)" if tot["has_demo"] else ""))),
])
cand = sorted(((p, pr) for p in projects for pr in p["problems"]), key=lambda x: -x[1]["risk"])[:3]
for i, (p, pr) in enumerate(cand, 1):
    roles = "".join(f'<span class="pf-role">{html.escape(r)}</span>' for r in pr["roles"])
    st.markdown(
        f'<div class="card{" risk" if i == 1 else ""}"><div class="h">Решение {i}. {html.escape(pr["title"])} · {html.escape(p["name"])}{tag(p)}</div>'
        f'<div class="t"><b>{f(pr["n"])} {pl(pr["n"])}</b>, ≈{fm(pr["risk"])} в сутки ({fr(pr["share_risk"])} риска ЖК). '
        f'<b>Решение:</b> {html.escape(pr["action"])}. <b>Подключить:</b> {roles} '
        f'<b>На следующем совещании проверим:</b> {html.escape(pr["metric"])} (сейчас {f(pr["baseline"])}).</div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 2. Таблица портфеля
U.section("Портфель: таблица по ЖК", "Одна строка — один ЖК. Выберите строку — ниже откроется разбор", ("ФАКТ",) + dm, anchor="portfolio", num="2.")
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
        "Расчётный риск, ₽/сутки": st.column_config.NumberColumn(format="localized"),
        "Главная проблема": st.column_config.TextColumn(width="large"),
        "Предлагаемое действие": st.column_config.TextColumn(width="large")})
rows = list(ev.selection.rows) if ev is not None and getattr(ev, "selection", None) else []
if rows and rows[0] < len(tdf):
    pick_name = tdf.iloc[rows[0]]["_name"]
    if st.session_state.get("_pf_tsel") != pick_name:
        st.session_state["_pf_tsel"] = pick_name
        st.session_state["pf_sel"] = pick_name
st.markdown(f'<div class="note">«Отклонение от плана»: плана передач по неделям в данных Бунинских нет — показываем «{PF.NO_DATA}»; у ДЕМО-ЖК план условный. '
            '«Из них готовы» — готовые к передаче без открытых замечаний, входят в «Просрочено по ДДУ».</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. Концентрация риска
U.section("Концентрация риска", "Доля каждого ЖК в просрочке и в суточном риске", ("ОЦЕНКА",) + dm, anchor="concentration", num="3.")
tr_, to_ = max(tot["risk_day"], 1), max(tot["overdue_kv"], 1)
srt = sorted(projects, key=lambda p: -p["risk_day"])
cum = 0.0
rows_h = []
for p in srt:
    cum += p["risk_day"] / tr_
    rows_h.append([p["name"] + (" · ДЕМО" if p["demo"] else ""), f(p["overdue_kv"]), fr(p["overdue_kv"] / to_), f(p["ready"]),
                   f(round(p["risk_day"])), fr(p["risk_day"] / tr_), fr(cum), fm(p["accrued_up"])])
rows_h.append(["Итого" + (" (с ДЕМО)" if tot["has_demo"] else ""), f(tot["overdue_kv"]), "100,0%", f(tot["ready"]), f(round(tot["risk_day"])),
               "100,0%", "", fm(tot["accrued_up"])])
cc1, cc2 = st.columns([1, 1.5], gap="large")
with cc1:
    fig = go.Figure(go.Bar(y=[p["name"] + (" · ДЕМО" if p["demo"] else "") for p in srt[::-1]], x=[p["risk_day"] / tr_ * 100 for p in srt[::-1]],
                           orientation="h", marker=dict(color=[U.GOLD if p["demo"] else U.NAVY for p in srt[::-1]]),
                           text=[f"{p['risk_day'] / tr_ * 100:.1f}%".replace(".", ",") for p in srt[::-1]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:.1f}% суточного риска<extra></extra>"))
    fig.update_layout(title="Доля суточного риска, %", margin=dict(l=8, r=50, t=34, b=8), bargap=.45)
    fig.update_xaxes(showticklabels=False, range=[0, 112])
    U.chart(fig, key="pf_conc", height=max(180, 62 * len(srt) + 60))
with cc2:
    U.fin_table(["ЖК", "Просрочено, кв.", "Доля", "Из них готовы", "Риск, ₽/сутки", "Доля риска", "Накопл. доля", "Накоплено"],
                rows_h, right=range(1, 8), total_last=True)
hhi = sum((p["risk_day"] / tr_) ** 2 for p in projects) * 10000
st.markdown(f'<div class="note">Индекс концентрации риска (HHI, 0–10 000): <b>{f(hhi)}</b> — '
            f'{"высокая концентрация: риск в основном у одного ЖК" if hhi > 2500 else "умеренная концентрация"}'
            f'{"; в режиме «Только факт» один ЖК, индекс 10 000" if fact_only else ""}. Доли считаются от суточного риска выборки.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 4. Отклонения
U.section("Разбор отклонений", "Откуда изменилась просрочка за 7 дней и как передача соотносится с планом", ("ФАКТ",) + dm, anchor="variance", num="4.")
v1, v2 = st.columns([1, 1.5], gap="large")
with v1:
    sgn = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
    wf = go.Figure(go.Waterfall(
        x=[p["name"] + (" · ДЕМО" if p["demo"] else "") for p in projects] + ["Итого"],
        measure=["relative"] * len(projects) + ["total"], y=[p["overdue_delta"] for p in projects] + [0],
        text=[sgn(p["overdue_delta"]) for p in projects] + [sgn(d_over)],
        textposition="outside", connector=dict(line=dict(color=U.LINE, width=1)),
        increasing=dict(marker=dict(color=U.RISK)), decreasing=dict(marker=dict(color=U.NAVY)), totals=dict(marker=dict(color=U.SILVER))))
    lo_, hi_ = min(0, d_over, *[p["overdue_delta"] for p in projects]), max(0, *[p["overdue_delta"] for p in projects])
    wf.update_layout(title=f"Δ просрочки по ДДУ за 7 дней, кв. (было {f(sum(p['overdue_kv'] - p['overdue_delta'] for p in projects))}, стало {f(tot['overdue_kv'])})",
                     margin=dict(l=8, r=8, t=34, b=8))
    wf.update_yaxes(showticklabels=False, showgrid=False, range=[lo_ * 1.35 - 4, hi_ * 1.35 + 6], zeroline=True, zerolinecolor=U.LINE)
    wf.update_xaxes(tickfont=dict(size=11))
    U.chart(wf, key="pf_wf", height=320)
with v2:
    rv = []
    for p in projects:
        dwk = (p["week_fact"] - p["week_prev"]) if p["week_prev"] is not None else None
        sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
        rv.append([p["name"] + (" · ДЕМО" if p["demo"] else ""), f(p["week_fact"]),
                   f(p["week_plan"]) if p["week_plan"] is not None else PF.NO_DATA,
                   (sg(p["week_dev"]) if p["week_dev"] is not None else PF.NO_DATA),
                   sg(dwk) if dwk is not None else PF.NO_DATA, sg(p["overdue_delta"]),
                   PF.NO_DATA if not p["prev_snapshot"] else sg(p["overdue_delta"]) + " (условно)"])
    U.fin_table(["ЖК", "Передано за неделю", "План", "Отклонение от плана", "Δ к прошлой неделе", "Δ просрочки, 7 дн.", "Δ к пред. срезу"],
                rv, right=range(1, 7))
    st.markdown(f'<div class="note">Передача и просрочка прошлой недели — реконструкция по датам ПА (ФАКТ). Предыдущий срез отчёта не сохранён — {PF.NO_DATA}; '
                'для ДЕМО-ЖК все отклонения условные. Неделя передачи: ' + html.escape(real["week_label"]) + '.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 5. Разбор ЖК
U.section("Разбор ЖК", "До трёх главных проблем: масштаб, корпуса, причина по данным, действие, роли и показатель контроля", ("ФАКТ",) + dm, anchor="drill", num="5.")
try:
    qj = st.query_params.get("jk")
    if qj and qj in names and st.session_state.get("_pf_qj") != qj:
        st.session_state["_pf_qj"] = qj
        st.session_state["pf_sel"] = qj
except Exception:
    pass
if st.session_state.get("pf_sel") not in names:
    st.session_state["pf_sel"] = tot["top"]["name"] if tot["top"] else names[0]
sel = st.radio("ЖК для разбора", names, horizontal=True, key="pf_sel")
p = next(x for x in projects if x["name"] == sel)
st.markdown(f'<div class="dec-h" style="font-size:20px">{html.escape(p["name"])}{tag(p)}</div>', unsafe_allow_html=True)
if p["demo"]:
    st.markdown(f'<div class="note">{U.badge("ДЕМО")} Условные цифры для показа структуры отчёта: не из данных проекта, в фактический итог не входят.</div>',
                unsafe_allow_html=True)
kd = ("ДЕМО",) if p["demo"] else ("ФАКТ",)
ke = ("ОЦЕНКА", "ДЕМО") if p["demo"] else ("ОЦЕНКА",)
prev_txt = (PF.NO_DATA if not p["prev_snapshot"] else C.fmt_delta(p["overdue_delta"])[0])
U.kpi_cards([
    dict(label="Просрочено по ДДУ, квартир", value=f(p["overdue_kv"]), risk=True, kind=kd, delta=C.fmt_delta(p["overdue_delta"]),
         foot=(f"помещений всего {f(p['overdue_all'])} · медиана {f(p['median_days'])} дн." if not p["demo"] else "Δ к условному прошлому срезу")),
    dict(label="Из них готовы без замечаний", value=f(p["ready"]), kind=kd, delta=("", "flat"), foot=f"риск готовых {fm(p['ready_risk'])}/сутки — часть общего"),
    dict(label="Расчётный риск, ₽ в сутки", value=fm(p["risk_day"]), risk=True, kind=ke, delta=("", "flat"),
         foot=(f"с м/м и кладовыми {fm(p['risk_day_total'])}" if not p["demo"] else "по средней ставке Бунинских, условно")),
    dict(label="Передано за неделю, квартир", value=f(p["week_fact"]), kind=kd,
         delta=C.fmt_delta(p["week_fact"] - p["week_prev"], good_when_down=False) if p["week_prev"] is not None else ("Нет данных", "flat"),
         foot=(f"план {f(p['week_plan'])}, отклонение {p['week_dev']:+d}".replace("-", "−") if p["week_plan"] is not None
               else f"План: {PF.NO_DATA} · {p['week_label']}")),
    dict(label="Изменение к предыдущему срезу", value=prev_txt, kind=kd, delta=("", "flat"),
         foot=("предыдущий срез не сохранён; за 7 дней по датам ПА: " + C.fmt_delta(p["overdue_delta"])[0]) if not p["demo"] else "условное значение"),
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

# ---------------------------------------------------------------- 6. Деньги
U.section("Деньги: риск, требования, подтверждённые суммы", "Три разных показателя — суммировать их нельзя", ("ОЦЕНКА",) + dm, anchor="money", num="6.")
dem_ps = [x for x in projects if x["demo"]]
claims_txt = fm(tot["claims"]) if tot["claims"] is not None else PF.NO_DATA
conf_txt = fm(tot["confirmed"]) if tot["confirmed"] is not None else PF.NO_DATA
cl_note = ("В реестрах проекта нет предъявленных требований и исков" if not dem_ps else
           "У Бунинских данных нет; у ДЕМО-ЖК — условные " + fm(sum(x["claims"] for x in dem_ps)))
cf_note = ("В реестрах проекта нет подтверждённых сумм" if not dem_ps else
           "У Бунинских данных нет; у ДЕМО-ЖК — условные " + fm(sum(x["confirmed"] for x in dem_ps)))
U.kpi_cards([
    dict(label="Расчётный риск: накоплено (верхняя оценка)", value=fm(tot["accrued_up"]), risk=True, kind=k_e, delta=("", "flat"),
         foot=f"нижняя оценка Бунинских {fm(real['accrued_lo'])} · в сутки ≈{fm(tot['risk_day'])}"),
    dict(label="Предъявленные требования", value=claims_txt, kind="ФАКТ" if tot["claims"] is None else "ДЕМО", delta=("", "flat"), foot=cl_note),
    dict(label="Подтверждённые суммы", value=conf_txt, kind="ФАКТ" if tot["confirmed"] is None else "ДЕМО", delta=("", "flat"), foot=cf_note),
])

# ---------------------------------------------------------------- 7. Поручения
U.section("Контроль поручений", "Что поручено, кого подключить и какой показатель проверим на следующем совещании", ("ФАКТ",) + dm, anchor="orders", num="7.")
ro = [[str(i), p_["name"] + (" · ДЕМО" if p_["demo"] else ""), pr["action"], ", ".join(pr["roles"]), pr["metric"], f(pr["baseline"])]
      for i, (p_, pr) in enumerate(((p_, pr) for p_ in projects for pr in p_["problems"]), 1)]
if ro:
    U.fin_table(["№", "ЖК", "Поручение", "Кого подключить", "Показатель на следующем совещании", "Сейчас"], ro, right=(5,))
else:
    st.info(PF.NO_DATA)
st.markdown('<div class="note">Исполнители указаны ролями, сроки не задаются: на следующем совещании сравниваем «Сейчас» с новым срезом.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 8. Сверка
U.section("Сверка с действующим отчётом", "Цифры Бунинских в этом приложении против сводных данных действующего отчёта", ("ФАКТ",), anchor="recon", num="8.")
checks = PF.reconcile(DA, P, real)
n_ok = sum(c["ok"] for c in checks)
U.fin_table(["Показатель", "Портфель", "Отчёт", "Источник", "Результат"],
            [[c["name"], f"{c['portfolio']:,.0f}".replace(",", " "), f"{c['report']:,.0f}".replace(",", " "), c["source"],
              '<span class="ok">✓ совпало</span>' if c["ok"] else '<span class="bad">✗ расхождение</span>'] for c in checks], right=(1, 2))
st.markdown(f'<div class="note"><b>Совпало {n_ok} из {len(checks)} проверок.</b></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 9. Примечания
c2 = lambda x: f"{float(x):.2f}".replace(".", ",")
rates = DA["apartments"].pipe(lambda a: a.loc[a["Тип объекта"].eq("Квартира") & a["Просрочка ДДУ"].eq(C.NT_OVERDUE), "Ставка ЦБ на срок ДДУ, %"])
U.section("Примечания и допущения модели", "", ("ФАКТ",), anchor="notes", num="9.")
U.sources(
    "<b>1. Формула.</b> Расчётный риск за сутки = ключевая ставка ЦБ / 300 × 2 (участник — гражданин, ч.2 ст.6 214-ФЗ) × цена квартиры, "
    "т.е. ставка/100/150 × цена, по каждой непереданной квартире с нарушенным сроком ДДУ.<br>"
    f"<b>2. Ставка.</b> Ключевая ставка ЦБ на последний день срока ДДУ — своя у каждой квартиры, из данных проекта "
    f"({c2(rates.min())}–{c2(rates.max())}%, в среднем {c2(rates.mean())}%).<br>"
    f"<b>3. Цена.</b> Цен по ДДУ в данных нет (реестр ДДУ с ценами отсутствует), принята условная цена {pm} млн ₽ за квартиру "
    "(меняется в боковой панели; риск пересчитывается пропорционально).<br>" +
    f"<b>4. Что не входит.</b> Коммерческие нежилые помещения не считаются; машиноместа и кладовые считаются отдельно по условным ценам "
    f"({c2(P['price_mm'] / 1e6)} и {c2(P['price_nhp'] / 1e6)} млн ₽) и показаны только отдельной строкой «с м/м и кладовыми».<br>"
    "<b>5. «Накоплено».</b> Сумма за весь период просрочки по коэффициентам из данных (верхняя и нижняя оценка); не начислено и не предъявлено.<br>" +
    (f"<b>6. ДЕМО.</b> Прокшино и Дзен-кварталы: условное число квартир × средняя ставка Бунинских ({c2(PF.avg_rate(DA, P))}%) × та же цена; "
    f"накопленная сумма — условные {PF.DEMO_DAYS} дн. просрочки. В фактический итог не входят.<br>" if not fact_only else "") +
    f"<b>7. Требования и подтверждённые суммы.</b> По Бунинским: {PF.NO_DATA} — реестра претензий, исков и актов признания в данных нет.<br>"
    "<b>8. Готовые квартиры.</b> «Готовы» = статус «Открыта к передаче» и 0 открытых замечаний; входят в «Просрочено по ДДУ», их риск — часть общего.<br>"
    "<b>9. Источники.</b> Срез действующего отчёта по Бунинским кварталам: реестр помещений (срок по ДДУ, статусы), график готовности, реестр ПА, "
    "счётчики реестра замечаний 1С. Персональные данные, свободный текст из комментариев графика и подрядчики в приложение не переносятся.")
