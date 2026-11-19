"""Портфель ЖК — отчёт для генерального директора с доступом по паролю."""
import html
from importlib import reload
from math import ceil
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="Портфель ЖК", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

import pf_ui as U  # noqa: E402

import pf_core as C  # noqa: E402
import pf_data  # noqa: E402
import pf_decide as DC  # noqa: E402
import pf_demo  # noqa: E402
import pf_model as PF  # noqa: E402

# Streamlit может выполнить новый app.py в процессе, где ещё загружены старые модули.
REPORT_SCHEMA = "v13"
if getattr(PF, "REPORT_SCHEMA", None) != REPORT_SCHEMA:
    for module in (U, DC, pf_demo, PF):
        reload(module)

st.markdown(U.CSS, unsafe_allow_html=True)
st.markdown(
    '<style>header[data-testid="stHeader"], header[data-testid="stHeader"] * {pointer-events: none !important;} '
    'header[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] {pointer-events: auto !important;}'
    '.fin.ready-reasons td:first-child {width: 48%;} '
    '.ready-reasons .reason-track {display: block; height: 5px; margin-top: 6px; background: #E9EDF2; border-radius: 3px;} '
    '.ready-reasons .reason-fill {display: block; height: 100%; background: #5B7BA6; border-radius: inherit;}'
    '.week-priority {padding: 13px 18px; margin: 4px 0 8px; border-left: 4px solid var(--navy);}'
    '.week-priority .h {font-size: 17px;}'
    '.week-priority .deadlines {display: flex; gap: 4px 22px; flex-wrap: wrap; margin-top: 5px;}'
    '.brief-row {padding: 10px 0; font-size: 15px; line-height: 1.5; color: var(--ink);}'
    '.brief-row + .brief-row {border-top: 1px solid var(--line);}'
    '.priority-label {display: block; font-size: 11px; color: #234F7A; font-weight: 700;}'
    '.contrib-row.focus .contrib-track i {background: #0B1F3A;}'
    '.contrib-row.focus a {font-weight: 700;}'
    '.weekly {scroll-margin-top: 58px; padding: clamp(14px, 2.2vw, 30px); background: var(--navy); border-radius: 6px; color: #E3EBF5;}'
    '.weekly h2, .weekly h3 {color: #fff; margin: 0; padding: 0;}'
    '.weekly h2 {font-size: clamp(22px, 2.4vw, 32px); line-height: 1.2;}'
    '.weekly h3 {font-size: 16px; line-height: 1.35; padding: 11px 14px; border-bottom: 1px solid #38506A;}'
    '.weekly .intro, .weekly .links {font-size: 13px; margin-top: 8px;}'
    '.weekly .item {margin: 12px 0; border: 1px solid #38506A; border-radius: 6px; background: #142B46;}'
    '.weekly .fields {display: grid; grid-template-columns: 1fr .85fr 1.1fr 1.25fr;}'
    '.weekly .fields > div {min-width: 0; padding: 10px 14px 12px; font-size: 13px; line-height: 1.45;}'
    '.weekly .fields > div + div {border-left: 1px solid #38506A;}'
    '.weekly .label, .weekly .subline {display: block; color: #C2D0E2;}'
    '.weekly .label {font-size: 11px; font-weight: 700; margin-bottom: 5px;}'
    '.weekly .fields .approval {background: #1D3958;}'
    '.weekly .approval .label {color: #B8E4FF; font-size: 12px;}'
    '.weekly .approval strong {color: #FFF; font-weight: 600;}'
    '.weekly .subline {font-size: 12px; margin-top: 4px;}'
    '.weekly .amount {display: block; color: #B8E4FF; font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums;}'
    '.weekly .fields a, .weekly .links a {color: #B8E4FF !important; text-underline-offset: 3px;}'
    '.weekly .links {display: flex; gap: 6px 20px; flex-wrap: wrap;}'
    '@media (max-width: 930px) {.weekly .fields {grid-template-columns: 1fr 1fr;}'
    '.weekly .fields > div:nth-child(3) {border-left: 0;}'
    '.weekly .fields > div:nth-child(n+3) {border-top: 1px solid #38506A;}}'
    '@media (max-width: 490px) {.weekly .fields {grid-template-columns: 1fr;}'
    '.weekly .fields > div + div {border-left: 0; border-top: 1px solid #38506A;}}</style>'
    + U.NAVIGATION, unsafe_allow_html=True)


@st.cache_data(show_spinner="Загрузка данных…")
def _load_demo_projects(projects: tuple, schema: str = REPORT_SCHEMA):
    return pf_demo.build(projects)


DA = _load_demo_projects(pf_data.PROJECTS, REPORT_SCHEMA)
with st.sidebar:
    st.markdown("**Допущения расчёта**")
    pr_in = {}
    for k_, nm_ in pf_data.PROJECTS:
        pr_in[k_] = st.number_input(f"Цена квартиры по ДДУ, млн ₽: {nm_}", min_value=1.0, max_value=60.0, value=PF.DEFAULT_PRICES[k_], step=0.1, key=f"pf_price_{k_}")
    st.caption("Цена квартиры по ДДУ принята допущением по каждому ЖК; неустойка пересчитывается пропорционально. "
               "Машиноместа и кладовые учитываются по расчётным ценам, коммерческие помещения не включены.")
    with st.expander("Сценарий выплат: коэффициенты"):
        k_claim = st.slider("Доля неустойки, по которой предъявляются претензии и иски, %", 5, 100, int(DC.DEFAULT_K["claim"] * 100), 5, key="pf_k_claim")
        k_cut = st.slider("Снижение неустойки судом по ст. 333 ГК, %", 0, 90, int(DC.DEFAULT_K["cut"] * 100), 5, key="pf_k_cut")
P = dict(price=sum(PF.DEFAULT_PRICES.values()) / len(PF.DEFAULT_PRICES) * 1e6, prices={k_: v_ * 1e6 for k_, v_ in pr_in.items()}, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
K = dict(claim=k_claim / 100, cut=k_cut / 100)
f, fm = C.fmt_int, C.fmt_money
DAILY_PENALTY = "Расчётная неустойка, ₽/день"
EXACT_MONEY_BELOW = 1_000
pl = lambda n: C.plural(n, "квартира", "квартиры", "квартир")
fr = lambda x: C.fmt_pct(x, 1)


def weeks_text(weeks):
    return f"{weeks:.1f}".removesuffix(".0").replace(".", ",") if weeks is not None else f"более {DC.HORIZON_W}"


def pace_text(weekly_average):
    return f"{weekly_average:.2f}".rstrip("0").rstrip(".").replace(".", ",").replace("-", "−")


def project_link(key, label):
    url = f'/?{urlencode({"jk": key})}#drill'
    return f'<a href="{html.escape(url)}" data-project-link>{html.escape(label)}</a>'


def signed_money(value):
    sign = "+" if value > 0 else "−" if value < 0 else ""
    amount = f"{f(round(abs(value)))} ₽" if abs(value) < EXACT_MONEY_BELOW else C.fmt_k(abs(value))
    return sign + amount


def measure_links(measure):
    return ", ".join(project_link(item["project"]["key"], item["project"]["name"]) for item in measure["items"])


def result_text(measure):
    indicator = "Односторонних актов" if measure["key"] == "unilateral" else "Передано из группы"
    return f"{indicator} 0 → {f(measure['week_units'])}"


def scope_label(measure):
    return dict(DC.REASONS)[measure["subreason"]] if measure["subreason"] else PF.PROBLEMS[measure["group"]]["title"]


import pf_detail as DT  # noqa: E402

st.markdown('<div class="rh"><div class="kick">Отчёт для генерального директора · Демо-данные</div><div class="ttl">Портфель ЖК</div></div>',
            unsafe_allow_html=True)
project_keys = tuple(DA)
if not project_keys:
    st.info("Перечень ЖК не задан.")
    st.stop()


@st.cache_data(show_spinner="Расчёт показателей…")
def _build(prices: tuple, coefs: tuple, keys: tuple, schema: str = REPORT_SCHEMA):
    return PF.build({key: DA[key] for key in keys}, dict(price=sum(v for _, v in prices) / len(prices), prices=dict(prices), price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE),
                    dict(zip(("claim", "cut"), coefs)))


B = _build(tuple(sorted(P["prices"].items())), (K["claim"], K["cut"]), project_keys, REPORT_SCHEMA)
projects, tot = PF.by_risk(B["projects"]), B["totals"]
names = [p["name"] for p in projects]
projects_by_key = {p["key"]: p for p in projects}
keys_by_name = {p["name"]: p["key"] for p in projects}


def request_drill_scroll():
    jump = st.session_state.get("_pf_jump_count", 0) + 1
    st.session_state["_pf_jump_count"] = jump
    st.session_state["_pf_scroll"] = jump


route_key = st.query_params.get("jk")
if route_key in projects_by_key and route_key != st.session_state.get("_pf_applied_jk"):
    st.session_state["pf_sel"] = st.session_state["pf_goto"] = projects_by_key[route_key]["name"]
    st.session_state["_pf_applied_jk"] = st.session_state["_pf_sync_route"] = route_key
    st.session_state["_pf_initial_route"] = True
    request_drill_scroll()


def update_project_route(name):
    key = keys_by_name[name]
    st.session_state["_pf_applied_jk"] = st.session_state["_pf_sync_route"] = key
    st.query_params["jk"] = key


sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
tr_, to_ = max(tot["risk_day"], 1), max(tot["overdue_kv"], 1)

# ---------------------------------------------------------------- 1. Верхняя сводка
slice_dates = [DA[key]["calc_date"] for key in project_keys]
act_d = projects[0]["act_date"]
dd = lambda t: t.strftime("%d.%m.%Y")
has = [p_ for p_ in projects if p_.get("has_risk", True)]
d_over = tot["overdue_delta"]
n_cov = len(has)
rk_d, rk_t = tot["risk_delta"], tot["risk_target"]
sgm = signed_money
RS = f"color:{U.NAVY};font-weight:600"
portfolio_lag = rk_d > 0 or rk_d > rk_t
LD = tot["ladder"]
RSN = tot["reasons"]
lagging = sum(p["risk_vs_target"] > 0 for p in projects)
review_date = act_d + pd.Timedelta(days=7)
package_date = act_d + pd.Timedelta(days=DC.MONTH_W * 7)
period_start = act_d - pd.Timedelta(days=7)
focus = max(projects, key=lambda project: project["decisions"][0]["effect_day"] if project["decisions"] else 0)
pri = PF.priority(projects, preferred_key=focus["key"])
priority_measure = focus["decisions"][0] if focus["decisions"] else None
package = DC.week_package(projects, focus)
priority_package = next((measure for measure in package if measure["key"] == "unilateral"), None)
if priority_package and (not priority_measure or priority_measure["key"] != "unilateral"):
    package.remove(priority_package)
    priority_package = None
priority_owner = priority_package["owner"] if priority_package else next((role for role in pri["roles"] if role != "Генеральный директор"), "Директор по заселению")
priority_request = "Утвердить оформление односторонних актов по квартирам после подтверждения оснований юристами" if priority_package else f"Утвердить проверку применимости меры «{priority_measure['short']}»" if priority_measure else "Принять к сведению статус портфеля"
priority_due = dd(review_date)
pack_effect = sum(measure["effect"] for measure in package)
pack_cost = sum(measure["cost"] for measure in package)
pack_daily = sum(measure["effect_day"] for measure in package)
plan = DC.handover_plan(projects, package, PF.PROBLEMS)
plan_total, plan_new, plan_closing = (sum(row[key] for row in plan) for key in ("total", "new", "closing"))
plan_title = "Утвердить недельный план передач по каждому ЖК"
plan_owner = "Директор по заселению"
pack_status = "окупается по расчётной неустойке" if pack_effect >= pack_cost else "не окупается по расчётной неустойке"
U.section("Сводка по портфелю", anchor="summary", num="1.")
slice_text = dd(slice_dates[0]) if min(slice_dates) == max(slice_dates) else f"{dd(min(slice_dates))}–{dd(max(slice_dates))}"
priority_cost = fm(priority_package["cost"]) if priority_package else "не предусмотрены"
priority_effect = f'−{fm(priority_measure["effect_day"])}/день к концу 4-й недели' if priority_measure else "без отдельного эффекта"
priority_check = (f'односторонних актов в ЖК «{focus["name"]}» 0 → {f(priority_package["week_units"])}'
                  if priority_package else "проверка применимости 0 → 1")
if not priority_package and priority_measure:
    priority_effect += ", потенциал вне пакета"
links_brief = f'<a href="#orders">Открыть поручение</a> · {project_link(focus["key"], "Открыть карточку ЖК")}'
st.markdown(
    '<div class="card week-priority">'
    f'<div class="brief-row"><b>Что происходит</b> · Факт на {slice_text} — {f(tot["overdue_kv"])} квартир в просрочке, '
    f'{f(tot["ready"])} из них готовы к передаче. Расчётная неустойка — {fm(tot["risk_day"])}/день.</div>'
    f'<div class="brief-row"><b>Что согласовать</b> · {html.escape(focus["name"])} — {html.escape(priority_request)}. '
    f'{html.escape(priority_owner)}. Расчёт до затрат: {priority_effect}. Затраты: {priority_cost}. '
    f'План и бюджет пакета — {fm(pack_cost)}.</div>'
    f'<div class="brief-row"><b>Когда проверяем</b> · {priority_due}. Просрочка {f(tot["overdue_kv"])} → {f(plan_closing)}, '
    f'передано из текущей просрочки 0 → {f(plan_total)}{f", {priority_check}" if priority_check else ""}. {links_brief}</div></div>',
    unsafe_allow_html=True)
with st.expander("Показатели портфеля и динамика за неделю"):
    st.markdown(f'<div class="slice">Факт на <b>{slice_text}</b> · сравнение с <b>{dd(period_start)}</b> '
                f'за полные 7 дней по <b>{dd(act_d)}</b></div>', unsafe_allow_html=True)
    U.kpi_cards([
        dict(label="Просрочка по ДДУ", value=f(tot["overdue_kv"]), delta=(f"{sg(d_over)} {pl(abs(d_over))} за неделю", "bad" if d_over > 0 else "good" if d_over < 0 else "flat"),
             foot=f"{fr(tot['overdue_kv'] / max(tot['units_kv'], 1))} от всех квартир по ДДУ в портфеле"),
        dict(label="Из них готовы к передаче", value=f(tot["ready"]), foot=f"{fr(tot['ready'] / to_)} просрочки"),
        dict(label=DAILY_PENALTY, value=fm(tot["risk_day"]),
             delta=(f"{sgm(rk_d)}/день к {dd(period_start)}", "bad" if portfolio_lag else "good" if rk_d < 0 else "flat"),
             foot=f"Цель на эту неделю: {sgm(rk_t)}/день · изменение по срезам: {sgm(rk_d)}/день"),
    ], big=True)
    st.markdown(f'<div class="dev">Из просрочки за неделю вышло <b>{f(tot["left_n"])}</b>, новых просрочек — <b>{f(tot["entered_n"])}</b>. '
                f'Отстают от цели <b>{lagging} из {len(projects)} ЖК</b>. <a href="#dynamics">Динамика по ЖК</a>.</div>', unsafe_allow_html=True)
week_cards = []
for measure in package:
    status = "Утвердить" if measure is priority_package else "Принять к сведению"
    week_cards.append(
        f'<article class="item"><h3>{html.escape(measure["title"])}</h3><div class="fields">'
        f'<div><span class="label">Группа квартир</span>{html.escape(scope_label(measure))} · {f(measure["eligible"])} квартир'
        f'<span class="subline">{measure_links(measure)}</span></div>'
        f'<div><span class="label">Расчёт, до затрат</span><strong class="amount">−{fm(measure["effect_day"])}/день</strong>'
        f'<span class="subline">к концу 4-й недели · −{fm(measure["effect"])} за 4 недели</span></div>'
        f'<div><span class="label">Затраты</span>{fm(measure["cost"])}. План за 4 недели — {f(measure["units"])} квартир.</div>'
        f'<div class="approval"><span class="label">{status}</span><strong>{html.escape(measure["owner"])}</strong>'
        f'<span class="subline">Контроль {priority_due} · {result_text(measure)}.</span></div></div></article>')
n_direct = 1 if priority_package else 0
priority_card = "".join(week_cards[:n_direct])
if not priority_package and priority_measure:
    priority_card = (f'<article class="item"><h3>{html.escape(priority_request)}</h3><div class="fields">'
                     f'<div>{project_link(focus["key"], focus["name"])}</div><div>{priority_effect}</div>'
                     f'<div>{html.escape(priority_owner)}</div><div class="approval">Контроль {priority_due} · '
                     f'{priority_check}</div></div></article>')
portal_plan = (f'<article class="item"><h3>{plan_title}</h3><div class="fields"><div>Утвердить бюджет пакета</div>'
               f'<div>{fm(pack_cost)}</div><div>{plan_owner}</div><div class="approval">Контроль {priority_due} · '
               f'передано 0 → {f(plan_total)} квартир из текущей просрочки</div></div></article>')
st.markdown('<section class="weekly" id="weekly-decisions"><h2>Решения недели по портфелю · расчёт до учёта затрат</h2>'
            '<h3>Нужно решение ГД</h3>' + priority_card + portal_plan
            + '<h3>В рабочем порядке</h3>' + "".join(week_cards[n_direct:])
            + f'<div class="intro"><strong>Итого за 4 недели</strong> · снижение {fm(pack_effect)}, затраты {fm(pack_cost)}, '
            f'разница {fm(pack_effect - pack_cost)} · {pack_status}.</div>'
            '<div class="links"><a href="#orders">Поручения и план по ЖК</a><a href="#decisions">Все меры по ЖК</a></div></section>',
            unsafe_allow_html=True)
st.markdown('<div class="note">Дневная неустойка — расчётная сумма за один дополнительный день просрочки по квартирам на дату среза. '
            f'Охват расчёта — {n_cov} из {len(projects)} ЖК. Цены квартир приняты как допущение (см. «Методология»). '
            '«Готовы к передаче» — часть просроченных квартир: объект не передан, готовность подтверждена, открытых замечаний нет.</div>', unsafe_allow_html=True)

with st.expander("Доля просроченных квартир по ЖК"):
    comp = PF.composition(projects)
    mx_ = max(c["now"] for c in comp) * 1.15 or 1
    cb = []
    for c in comp:
        w_ = lambda v: f"{100 * v / mx_:.1f}%"
        cb.append(f'<div class="cmp{" tot" if c["total"] else ""}"><div class="nm">{html.escape(c["name"])}</div>'
                  f'<div class="trk"><div class="rdy" style="width:{w_(c["ready"])}"></div><div class="now" style="width:{w_(c["now"])}"></div>'
                  f'</div><div class="vl">{fr(c["now"])} <span>(из них готовы к передаче {fr(c["ready"])})</span></div></div>')
    st.markdown('<div class="cmph">Доля квартир по ДДУ, просроченных на дату среза</div>' + "".join(cb),
                unsafe_allow_html=True)

# ---------------------------------------------------------------- 2. Приоритетный объект портфеля
U.section("Приоритетный объект портфеля", "Критерий выбора — наибольшее расчётное снижение неустойки за день к концу 4-й недели среди главных мер по ЖК.", anchor="priority", num="2.")
if pri:
    drv = "".join(f"<li>{html.escape(x)}</li>" for x in pri["drivers"])
    decs = "".join(
        f'<div class="dc"><div class="dt">{html.escape(d_["title"])}</div>'
        f'<div class="de">−{fm(d_["effect_day"])} в день к концу 4-й недели · −{fm(d_["effect"])} за 4 недели</div>'
        f'<div class="dr">{html.escape(d_["mechanism"])}. Контрольный показатель: {html.escape(d_["metric"].lower())}.</div>'
        f'<div class="dr">{html.escape(d_["kind"])} · {html.escape(", ".join(d_["roles"]))}</div></div>' for d_ in pri["decisions"])
    st.markdown(
        f'<div class="prio"><div class="ph"><div class="pn">{html.escape(pri["name"])}'
        f'{": " + html.escape(priority_package["title"]) if priority_package else ""}</div>'
        f'<div class="pm"><b>{f(priority_package["units"]) + " квартир · " if priority_package else ""}'
        f'{priority_effect}</b><span>Расчёт, до затрат.</span> '
        f'<div>Весь ЖК: {fm(pri["risk_day"])}/день · {fr(pri["share"])} портфеля</div></div></div>'
        f'<div class="pc"><div class="pl">Основная причина</div><div class="pt">{html.escape(pri["cause"])}</div><ul>{drv}</ul></div>'
        f'<div class="pc"><div class="pl">Предлагаемые решения и ожидаемый эффект</div>{decs}</div></div>', unsafe_allow_html=True)

attention = sorted((p for p in projects if p["risk_delta"] > 0 or p["risk_vs_target"] > 0),
                   key=lambda p: (p["risk_delta"] > 0, p["risk_vs_target"]), reverse=True)
if attention:
    st.markdown("**ЖК, требующие внимания по недельной динамике**")
    U.fin_table(["ЖК", "Сигнал", "Изменение дневной неустойки", "Отклонение от целевого темпа"],
                [[p["name"], "Дневная неустойка выросла" if p["risk_delta"] > 0 else "Отставание от целевой динамики",
                  f"{sgm(p['risk_delta'])} в день", f"{sgm(p['risk_vs_target'])} в день"] for p in attention], right=(2, 3))

# ---------------------------------------------------------------- 3. Таблица по ЖК
U.section("Структура портфеля по ЖК", "По убыванию расчётной неустойки за день. Нажмите на ЖК, чтобы открыть его карточку.", anchor="segments", num="3.")
srows = PF.screen_rows(projects)
arrow = lambda d_: "▲" if d_ > 0 else "▼" if d_ < 0 else "•"
trend_scale = max(v for row in srows for v in row["trend"]) or 1
trend_dates = projects[0]["weekly"]["Неделя"].tolist()
tb = []
for r_ in srows:
    bad_ = r_["worse"]
    wk_cls = ' class="wr"' if bad_ else ""
    change_cls = " wr" if r_["d_over"] > 0 else " improved" if r_["d_over"] < 0 else ""
    project = projects_by_key[r_["key"]]
    target = max(0, project["overdue_prev"] - project["target_burn"])
    focus_label = '<span class="priority-label">Приоритет недели</span>' if r_["key"] == focus["key"] else ""
    tb.append([
        f'<b>{project_link(r_["key"], r_["name"])}</b>{focus_label}',
        f'{f(r_["over"])}<span class="sub{change_cls}">{arrow(r_["d_over"])} {sg(r_["d_over"])} за неделю</span>',
        f(r_["ready"]), f(round(r_["risk"])), fr(r_["share"]),
        f'<span class="nw">{U.spark(r_["trend"], bad_, scale=trend_scale, dates=trend_dates, target=target)}</span>'
        f'<span class="sub"><span{wk_cls}>{"ниже целевого темпа" if bad_ else "в рамках целевого темпа"}</span></span>',
        f(r_["left"]),
        f'{html.escape(r_["decision"])}<span class="sub">−{fm(r_["dec_day"])} в день · −{fm(r_["dec_4w"])} за 4 недели</span>' if r_["dec_day"] else html.escape(r_["decision"])])
portfolio_target = max(0, tot["overdue_prev"] - tot["target_burn"])
tb.append(["Итого по портфелю", f'{f(tot["overdue_kv"])}<span class="sub">{arrow(d_over)} {sg(d_over)} за неделю</span>', f(tot["ready"]), f(round(tot["risk_day"])), "100%",
           f'<span class="nw">{U.spark([sum(p_["trend"][i] for p_ in projects) for i in range(len(trend_dates))], portfolio_lag, dates=trend_dates, target=portfolio_target)}</span>',
           f(tot["rem"]["left_cum"]), ""])
U.fin_table(["ЖК", "Просрочка по ДДУ", "Готовы к передаче", DAILY_PENALTY, "Доля в дневной неустойке", "Динамика просрочки за 12 недель", "Остаток замечаний", "Главное решение и ожидаемый эффект"],
            tb, right=(1, 2, 3, 4, 6), total_last=True, cls="pt3", hide=(2, 4, 6, 7))
st.markdown(f'<div class="note">Спарклайны ЖК: {trend_dates[0]} → {trend_dates[-1]}, общая шкала 0–{f(trend_scale)} квартир; '
            'пунктир на последнем интервале — целевой остаток на конец недели. Для портфеля показан собственный масштаб. '
            'Красный — отставание от недельной цели по неустойке или рост просрочки; зелёная стрелка — снижение просрочки. '
            'Эффекты мер — расчёт до затрат.</div>', unsafe_allow_html=True)


def _go():
    selected = st.session_state["pf_goto"]
    if selected is not None:
        st.session_state["pf_sel"] = selected
        update_project_route(selected)
        request_drill_scroll()


if st.session_state.get("pf_goto") not in names:
    st.session_state.pop("pf_goto", None)
goto = st.selectbox("Перейти к детализации ЖК (шахматка, замечания, подрядчики, финансы, динамика)", names,
                    index=None, placeholder="Выберите ЖК", key="pf_goto", on_change=_go)
if goto:
    st.markdown(project_link(keys_by_name[goto], f"Открыть карточку ЖК «{goto}»"), unsafe_allow_html=True)
with st.expander("Расширенные показатели по ЖК: неустойка, темп и сроки"):
    fall = []
    for p_ in PF.by_risk(projects):
        fc_ = p_["forecast"]
        fall.append([p_["name"], f(p_["overdue_kv"]), f(p_["ready"]), f(round(p_["risk_day"])), f(round(p_["risk_day"] / max(p_["overdue_kv"], 1))), fr(p_["risk_day"] / tr_),
                     f"{sgm(p_['risk_delta'])} при целевом темпе {sgm(p_['risk_target'])}", f"{f(p_['week_fact'])} / {f(p_['week_plan'])} ({sg(p_['week_dev'])})",
                     weeks_text(fc_["base"]["weeks"]), fm(fc_["base"]["accrued"])])
    fall.append(["Итого по портфелю", f(tot["overdue_kv"]), f(tot["ready"]), f(round(tot["risk_day"])), f(round(tot["risk_day"] / max(tot["overdue_kv"], 1))), "100,0%",
                 f"{sgm(rk_d)} при целевом темпе {sgm(rk_t)}", f"{f(tot['week_fact'])} / {f(tot['week_plan'])} ({sg(tot['week_fact'] - tot['week_plan'])})", "", ""])
    U.fin_table(["ЖК", "Просрочка по ДДУ", "Готовы к передаче", DAILY_PENALTY, "Неустойка на просроченную квартиру, ₽/день", "Доля в дневной неустойке портфеля", "Изменение за неделю к целевому темпу",
                 "Передано за неделю: факт / целевой темп", "Срок закрытия, недель", "Будущая расчётная неустойка до закрытия"], fall, right=range(1, 10), total_last=True)

# ---------------------------------------------------------------- 4. Причины непередачи готовых квартир
U.section("Причины непередачи готовых квартир",
          "В каждой строке — количество квартир, их доля среди готовых и расчётная неустойка за день.",
          anchor="reasons", num="4.")
reason_scope = st.selectbox("Причины по ЖК", ["Весь портфель"] + names, key="pf_reason_scope")
reason_data = tot if reason_scope == "Весь портфель" else next(p_ for p_ in projects if p_["name"] == reason_scope)
reason_groups = reason_data["reasons"]
reason_count = reason_data["ready"]
if reason_count:
    reason_rows = []
    ordered_reasons = sorted(DC.REASONS, key=lambda item: reason_groups[item[0]]["n"], reverse=True)
    for key, label in ordered_reasons:
        group = reason_groups[key]
        share = group["n"] / reason_count
        reason_rows.append([
            f'<span>{html.escape(label)}</span><span class="reason-track" aria-hidden="true">'
            f'<span class="reason-fill" style="width:{share:.1%}"></span></span>',
            f(group["n"]), fr(share), fm(group["risk"]),
        ])
    reason_rows.append(["Итого", f(reason_count), "100%", fm(reason_data["ready_risk"])])
    U.fin_table(["Причина", "Квартир", "Доля готовых", DAILY_PENALTY],
                reason_rows, right=(1, 2, 3), total_last=True, cls="ready-reasons")
else:
    st.info("В выбранном срезе нет готовых к передаче квартир с просрочкой по ДДУ.")

with st.expander("Сравнение ЖК по причинам и темпу передачи"):
    rows_r = []
    for key, label in DC.REASONS:
        rows_r.append([label] + [f"{f(p_['reasons'][key]['n'])} · {fm(p_['reasons'][key]['risk'])}" for p_ in projects]
                      + [f"{f(RSN[key]['n'])} · {fm(RSN[key]['risk'])}"])
    U.fin_table(["Причина (квартир · неустойка за день)"] + names + ["Портфель"], rows_r, right=range(1, len(projects) + 2))
    capacity_rows = []
    for p_ in projects + [tot]:
        required = ceil(p_["ready"] / DC.MONTH_W)
        capacity_rows.append([p_.get("name", "Портфель"), f(p_["week_fact"]), f(p_["capacity"]), f(required),
                              f(max(0, required - p_["capacity"]))])
    U.fin_table(["ЖК", "Передано за последнюю неделю", "Максимум за 8 недель", "Нужно в неделю для передачи за 4 недели",
                 "Не хватает передач в неделю к максимуму"], capacity_rows, right=range(1, 5), total_last=True)
    st.caption("Каждая квартира учтена в одной группе. Запись позже семи дней показывает дату визита. "
               "Доступность более ранних слотов проверяется отдельно.")

# ---------------------------------------------------------------- 5. Прогноз и целевой темп
U.section("Прогноз и целевой темп", "Текущий чистый темп, целевой темп по истории и сценарий ускоренной передачи готовых квартир", anchor="forecast", num="5.")
rw = st.radio("Срок передачи всех готовых квартир, недель", [2, 4, 8], index=1, horizontal=True, key="pf_ready_w")
rw_w = C.plural(rw, "неделю", "недели", "недель")
PFC = DC.portfolio_forecast(projects, rw)
frows = []
for p_ in projects:
    fc_ = DC.forecast(p_, rw)
    frows.append([p_["name"], f(p_["overdue_kv"]), pace_text(p_["burn_pace"]), weeks_text(fc_["base"]["weeks"]), weeks_text(fc_["target"]["weeks"]),
                  (fm(fc_["base"]["accrued"]), RS), weeks_text(fc_["scn"]["weeks"]), fm(fc_["saving"])])
frows.append(["Портфель", f(tot["overdue_kv"]), pace_text(tot["burn_pace"]), weeks_text(PFC["base"]["weeks"]), weeks_text(PFC["target"]["weeks"]),
              (fm(PFC["base"]["accrued"]), RS), weeks_text(PFC["scn"]["weeks"]), fm(PFC["saving"])])
U.fin_table(["ЖК", "Просрочка на дату среза", "Чистый темп, квартир в неделю", "Срок закрытия, недель (текущий темп)", "При целевом темпе, недель",
             "Будущая расчётная неустойка до закрытия", f"Срок закрытия при передаче всех готовых за {rw} {rw_w}", "Снижение расчётной неустойки за весь прогноз"], frows, right=range(1, 8), total_last=True)
cut_ = min(max(len(PFC["base"]["path"]), len(PFC["scn"]["path"]), len(PFC["target"]["path"])), 60)
fg = go.Figure()
for key_, lab_, col_, dash_ in (("base", "Текущий темп", U.NAVY, "solid"), ("target", "Целевой темп", U.GRAPH, "dash"), ("scn", f"Все готовые за {rw} {rw_w}", U.GOOD, "solid")):
    pth = PFC[key_]["path"][:cut_]
    fg.add_scatter(x=[x_[0] for x_ in pth], y=[x_[2] / 1e9 for x_ in pth], mode="lines", name=lab_, line=dict(color=col_, width=2.5, dash=dash_))
fg.update_layout(title="Будущая расчётная неустойка с даты среза нарастающим итогом, млрд ₽", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.18), hovermode="x unified")
fg.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
fg.update_xaxes(title_text="недель от даты среза")
with st.expander("График накопленной неустойки"):
    U.chart(fg, key="pf_fc_chart", height=320)
closed_base, closed_scenario = PFC["base"]["weeks"], PFC["scn"]["weeks"]
weeks_saved = weeks_text(closed_base - closed_scenario) if closed_base is not None and closed_scenario is not None else "—"
st.markdown(f'<div class="note">При передаче всех готовых квартир за {rw} {rw_w} сокращение срока закрытия просрочки по портфелю, недель: {weeks_saved}; '
            f'будущая расчётная неустойка снижается на ≈{fm(PFC["saving"])} (за первые 4 недели — на {fm(PFC["saving_4w"])}). Чистый темп — среднее число квартир, вышедших из просрочки, за вычетом новых просрочек за последние 4 недели. '
            'Целевой темп — неотрицательный средний темп за предыдущие четыре недели с запасом 10%. В сценарии новые просрочки вычитаются из числа передач. Доступные слоты и ресурсы требуют подтверждения по каждому ЖК.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 6. Управленческие решения и ожидаемый эффект
U.section("Управленческие решения и ожидаемый эффект", "Рекомендации по ЖК · расчёт до учёта затрат. Итог этого раздела относится к главным мерам по ЖК. Бюджет пакета недели показан в блоке «Решения недели» и разделе «Поручения».", anchor="decisions", num="6.")
ranked_d = PF.by_risk(projects)
mrows = [[project_link(p_["key"], p_["name"]), d_["kind"], d_["title"], d_["basis"], d_["metric"], ", ".join(d_["roles"]), f"−{fm(d_['effect_day'])}", f"−{fm(d_['effect'])}"]
         for p_ in ranked_d for d_ in p_["decisions"][:1]]
msum_d = sum(p_["decisions"][0]["effect_day"] for p_ in ranked_d if p_["decisions"])
msum_4 = sum(p_["decisions"][0]["effect"] for p_ in ranked_d if p_["decisions"])
mrows.append(["Итого по главным решениям", "", "", "", "", "", f"−{fm(msum_d)}", f"−{fm(msum_4)}"])
DH = ["ЖК", "Группа мер", "Главное решение", "Основание", "Контрольный показатель", "Ответственные роли", "Расчётный эффект, ₽/день", "Расчётный эффект за 4 недели, ₽"]
U.fin_table(DH, mrows, right=(6, 7), total_last=True, cls="pt3", hide=(1, 3, 4, 5))
xrows = [[project_link(p_["key"], p_["name"]), d_["kind"], d_["title"], d_["basis"], d_["metric"], ", ".join(d_["roles"]), f"−{fm(d_['effect_day'])}", f"−{fm(d_['effect'])}"]
         for p_ in ranked_d for d_ in p_["decisions"][1:]]
if xrows:
    with st.expander(f"Дополнительные решения по ЖК ({len(xrows)})"):
        U.fin_table(DH, xrows, right=(6, 7), cls="pt3", hide=(1, 3, 4, 5))
shift_rows = [[p_["name"], f(p_["reasons"]["queue"]["n"]), fm(measure["effect"]), f(measure["moved"]), f(measure["extra"]), fm(measure["cost"])]
              for p_ in ranked_d for measure in p_["cands"] if measure["key"] == "crew"]
if shift_rows:
    with st.expander("Вторая смена приёмки · проверка перед согласованием"):
        st.caption("Поздняя запись показывает дату визита. Перед согласованием директору по заселению предлагается проверить спрос на ранние визиты и доступные слоты, "
                   f"а финансовому директору — стоимость второй смены (расчётно {fm(DC.SHIFT_UNIT_COST)} за дополнительную приёмку, горизонт — 4 недели).")
        U.fin_table(["ЖК", "Записаны позже 7 дней", "Сценарное снижение неустойки за 4 недели", "Могут прийти раньше, квартир",
                     "Дополнительные передачи в неделю", "Стоимость второй смены за 4 недели"], shift_rows, right=range(1, 6))
cl_ = [(p_["name"], p_["contractor_risk"][0]) for p_ in projects if p_["contractor_risk"]]
if cl_:
    with st.expander("Подрядчики: доля дневной неустойки и потенциал удержаний"):
        U.fin_table(["ЖК", "Подрядчик", "Квартир с замечаниями", "Доля в дневной неустойке ЖК", DAILY_PENALTY, "Потенциал удержаний"],
                    [[p_["name"], c_["name"], f(c_["units"]), fr(c_["share"]), fm(c_["risk"]), fm(c_["claim"])] for p_ in projects for c_ in p_["contractor_risk"]],
                    right=range(2, 6))
st.markdown('<div class="note">Эффект по каждому решению — доля соответствующей причины в дневной неустойке ЖК, которую снимает мера: число квартир причины × средняя дневная ставка этой причины × доля, '
            'переходящая к передаче за 4 недели. Показан эффект к концу 4-й недели (₽/день) и накопленный за 4 недели (₽). '
            f'Допущения по долям: явка на приёмку +{C.fmt_pct(DC.NO_SHOW_SHARE)}; дополнительные бригады +{C.fmt_pct(DC.EXTRA_CAPACITY)} к фактическому темпу; сквозная приёмка закрывает {C.fmt_pct(DC.REFUSAL_RESOLVED)} приёмок без подписи; '
            f'после обзвона приходит {C.fmt_pct(DC.CALL_RESPONSE)} собственников; односторонние акты — по {C.fmt_pct(DC.UNILATERAL_SHARE)} вызовов с истёкшим сроком (при соблюдении условий ч. 6 ст. 8 214-ФЗ); '
            f'удержания и претензионная работа снимают {C.fmt_pct(DC.PRESSURE_SHARE)} дневной неустойки по квартирам с замечаниями подрядчика. '
            'Снижение за 4 недели = снижение в день к концу 4-й недели × 28 / 2, предполагается линейное нарастание. '
            'Даты исполнения выбранного пакета указаны в поручениях.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. Вклад сегментов в риск
U.section("Концентрация дневной неустойки по ЖК", "Вклад каждого ЖК в расчётную неустойку портфеля за день", anchor="contribution", num="7.")
srt = sorted(projects, key=lambda p: -p["risk_day"])
cum, rows_h = 0.0, []
for p in srt:
    cum += p["risk_day"] / tr_
    focus_label = '<span class="priority-label">Приоритет недели</span>' if p["key"] == focus["key"] else ""
    rows_h.append([project_link(p["key"], p["name"]) + focus_label, f(p["overdue_kv"]), fr(p["overdue_kv"] / to_), f(round(p["risk_day"])), fr(p["risk_day"] / tr_), fr(cum), fm(p["accrued_up"])])
rows_h.append(["Итого", f(tot["overdue_kv"]), "100,0%", f(round(tot["risk_day"])), "100,0%", "", fm(tot["accrued_up"])])
c1, c2 = st.columns([1, 1.25], gap="large")
with c1:
    max_risk = srt[0]["risk_day"] or 1
    contribution_bars = "".join(
        f'<div class="contrib-row{" focus" if project["key"] == focus["key"] else ""}"><div>{project_link(project["key"], project["name"])}'
        f'{"<span class=priority-label>Приоритет недели</span>" if project["key"] == focus["key"] else ""}</div>'
        f'<span class="contrib-track" aria-hidden="true"><i style="width:{project["risk_day"] / max_risk:.2%}"></i></span>'
        f'<div class="contrib-value"><strong>{fm(project["risk_day"])}/день</strong> '
        f'<span>· {fr(project["risk_day"] / tr_)}</span></div></div>'
        for project in srt)
    st.markdown(f'<div class="contrib-bars">{contribution_bars}</div>', unsafe_allow_html=True)
with c2:
    U.fin_table(["ЖК", "Просрочка, квартир", "Доля квартир", DAILY_PENALTY, "Доля в дневной неустойке", "Доля первых ЖК по рейтингу", "Начислено и не выплачено, расчёт"], rows_h, right=range(1, 7), total_last=True)
st.markdown(f'<div class="note">Расчёт с {dd(pf_demo.ACCRUAL_START)} по {slice_text}: {fm(tot["accrued_up"])} по портфелю. '
            'Сумма включает начисления по просроченным квартирам до даты передачи или среза. Выплаты в сценарии приняты равными нулю. '
            'Доля первых ЖК — сумма долей строк сверху до текущего ЖК включительно.</div>', unsafe_allow_html=True)
hhi = sum((p["risk_day"] / tr_) ** 2 for p in projects) * 10000
big = srt[0]
st.markdown(f'<div class="note">Наибольшая доля — у ЖК «{big["name"]}»: {fr(big["risk_day"] / tr_)} дневной неустойки. Индекс концентрации (HHI, 0–10 000): <b>{f(hhi)}</b> — '
            f'{"высокая концентрация" if hhi > 2500 else "умеренная концентрация"}.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 4. Динамика
U.section("Динамика: неделя к неделе", f"Изменение с {dd(period_start)} по {dd(act_d)}. Красный — рост просрочки, зелёный — снижение.", anchor="dynamics", num="8.")
v1, v2 = st.columns([1, 1.4], gap="large")
with v1:
    wf = go.Figure(go.Waterfall(
        x=[p["name"] for p in projects] + ["Портфель"], measure=["relative"] * len(projects) + ["total"],
        y=[p["overdue_delta"] for p in projects] + [0], text=[sg(p["overdue_delta"]) for p in projects] + [sg(d_over)],
        textposition="outside", connector=dict(line=dict(color=U.LINE, width=1)),
        increasing=dict(marker=dict(color=U.RISK)), decreasing=dict(marker=dict(color=U.GOOD)), totals=dict(marker=dict(color=U.NAVY))))
    lo_, hi_ = min(0, d_over, *[p["overdue_delta"] for p in projects]), max(0, *[p["overdue_delta"] for p in projects])
    wf.update_layout(title="Изменение просрочки по ДДУ за 7 дней, квартир", margin=dict(l=8, r=8, t=34, b=72))
    wf.update_yaxes(showticklabels=False, range=[lo_ * 1.35 - 4, hi_ * 1.35 + 6], zeroline=True, zerolinecolor=U.LINE)
    wf.update_xaxes(tickfont=dict(size=10), tickangle=-35)
    U.chart(wf, key="pf_wf", height=360)
with v2:
    rv = []
    for p in [*projects, dict(tot, name="Итого по выбранным ЖК")]:
        prev_o = p["overdue_prev"]
        dwk = (p["week_fact"] - p["week_prev"]) if p["week_prev"] is not None else None
        tone = U.RISK if p["risk_delta"] > p["risk_target"] else U.INK2
        rv.append([p["name"], f(p["overdue_week_current"]), f(prev_o), sg(p["overdue_delta"]),
                   f(p["week_fact"]), sg(dwk) if dwk is not None else PF.DASH, sgm(p["risk_delta"]),
                   sgm(p["risk_target"]), (sgm(p["risk_delta"] - p["risk_target"]), f"color:{tone};font-weight:600")])
    U.fin_table(["ЖК", f"Просрочка на {dd(act_d)}", f"Просрочка на {dd(period_start)}", "Изменение просрочки",
                 "Передано за 7 дней", "Δ передач к предыдущей неделе", "Изменение неустойки, ₽/день",
                 "Цель на неделю, ₽/день", "Отклонение от цели, ₽/день"], rv, right=range(1, 9), total_last=True)
lf = go.Figure()
for p in projects:
    w = p["weekly"]
    below_target = p["risk_vs_target"] > 0
    lf.add_scatter(x=w["Неделя"], y=w["Просрочка на конец недели, квартир"], mode="lines+markers", name=p["name"],
                   line=dict(color=U.RISK if below_target else U.NAVY, width=2.6 if below_target else 1.4))
lf.update_layout(title="Просрочка по ДДУ на конец недели, квартир", margin=dict(l=8, r=8, t=34, b=8),
                 legend=dict(orientation="h", y=-0.18), hovermode="x unified")
lf.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
U.chart(lf, key="pf_line", height=300)
st.markdown('<div class="note">Красный — ЖК отстаёт от недельной цели по дневной неустойке. Синий — цель выполнена. Зелёная стрелка в сводке и детализации — улучшение показателя. Передачи за 7 дней включают все переданные квартиры, в том числе переданные в срок.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 6. Матрица рисков
U.section("Просрочка и неустойка по причинам", "Сравнение причин просрочки по ЖК", anchor="matrix", num="9.")
matrix_mode = st.radio("Показатель матрицы", ("Квартиры", "₽ в день"), horizontal=True, key="pf_matrix_metric")
matrix_value = "n" if matrix_mode == "Квартиры" else "risk"
project_groups = [{group["key"]: group for group in project["groups"]} for project in projects]
kinds = [key for key in PF.PROBLEMS if any(key in groups for groups in project_groups)]
targeted_groups = {measure["group"] for measure in package}
mx = []
for k in kinds:
    label = PF.PROBLEMS[k]["title"]
    row = [f'<b>{html.escape(label)}</b><span class="priority-label">В пакете мер недели</span>' if k in targeted_groups else label]
    values = [groups[k][matrix_value] if k in groups else 0 for groups in project_groups]
    row_max = max(values) or 1
    for value in values:
        alpha = 0.06 + 0.28 * value / row_max if value else 0
        row.append((f(round(value)), f"background:rgba(49,87,125,{alpha:.2f});font-weight:600"))
    row.append(f(round(sum(values))))
    mx.append(row)
matrix_totals = [sum(group[matrix_value] for group in groups.values()) for groups in project_groups]
mx.append(["Итого по ЖК", *[f(round(value)) for value in matrix_totals], f(round(sum(matrix_totals)))])
U.fin_table(["Причина просрочки"] + names + [f"Итого, {matrix_mode.lower()}"], mx,
            right=range(1, len(projects) + 2), cls="risk-matrix", total_last=True)
matrix_legend = "тем больше квартир" if matrix_mode == "Квартиры" else "тем выше расчётная неустойка в ₽/день"
st.markdown(f'<div class="note">В пределах строки: чем темнее ячейка, {matrix_legend}. Каждая квартира учтена в одной причине. ОЗ — офис заселения.</div>', unsafe_allow_html=True)
with st.expander("Группы из решений и связь с матрицей"):
    U.fin_table(["Группа из решения", "Строка матрицы", "Квартир в группе", "ЖК"],
                [[scope_label(measure), PF.PROBLEMS[measure["group"]]["title"], f(measure["eligible"]),
                  "<span>" + measure_links(measure) + "</span>"] for measure in package], right=(2,))
    st.caption("Группы готовых квартир с просроченным вызовом, поздней записью, приёмкой без акта и без записи взаимоисключающие. Квартиры с открытыми замечаниями составляют отдельную строку матрицы. Пакет суммируется без повторного учёта.")
with st.expander("Где учтена неустойка квартир с замечаниями"):
    remark_rows = []
    for key in kinds:
        groups = [project.get(key, {}) for project in project_groups]
        remark_rows.append([PF.PROBLEMS[key]["title"], f(sum(group.get("with_remarks_n", 0) for group in groups)),
                            f(round(sum(group.get("with_remarks_risk", 0) for group in groups)))])
    remark_rows.append(["Итого по квартирам с замечаниями",
                        f(sum(group["with_remarks_n"] for project in project_groups for group in project.values())),
                        f(round(sum(project["risk_blocked"] for project in projects)))])
    U.fin_table(["Строка матрицы", "Квартир с замечаниями", DAILY_PENALTY], remark_rows, right=(1, 2), total_last=True)

# ---------------------------------------------------------------- 10. Замечания портфеля
RM = tot["rem"]
U.section("Реестр замечаний по портфелю", "Открытые и просроченные замечания на дату среза", anchor="remarks", num="10.")
pc = lambda a_, b_: C.fmt_pct(a_ / b_) if b_ else PF.DASH
blocked = sum(p_["risk_blocked"] for p_ in projects)
U.kpi_cards([
    dict(label="Открытые замечания", value=f(RM["left_cum"]), foot="Остаток на дату среза"),
    dict(label="Просроченные замечания", value=f(RM["overdue"]), foot=f"{C.fmt_pct(RM['overdue_share'])} открытых"),
    dict(label="Квартиры с открытыми замечаниями", value=f(RM["flats_unfixed"]), foot=f"{pc(RM['flats_unfixed'], RM['flats_total'])} из {f(RM['flats_total'])} квартир"),
], big=True)
st.markdown(f'<div class="dev"><b>Связь с финансовыми показателями.</b> На просроченные квартиры с открытыми замечаниями '
            f'приходится <b>{fm(blocked)}/день</b> расчётной неустойки, или {fr(blocked / tr_)} по выбранным ЖК.</div>', unsafe_allow_html=True)
with st.expander("История замечаний"):
    st.caption("Оценка истории замечаний по профилям ЖК.")
    sel_q = st.selectbox("Динамика замечаний по кварталам", ["Весь портфель"] + names, key="pf_qsel")
    Q = RM["quarters"] if sel_q == "Весь портфель" else next(p_ for p_ in projects if p_["name"] == sel_q)["rem"]["quarters"]
    qf = make_subplots(specs=[[{"secondary_y": True}]])
    qf.add_bar(x=Q["Квартал"], y=Q["Поступило"], name="Поступило", marker_color="#9DB0CA", secondary_y=False)
    qf.add_bar(x=Q["Квартал"], y=Q["Устранено"], name="Устранено", marker_color=U.NAVY, secondary_y=False)
    qf.add_scatter(x=Q["Квартал"], y=Q["Остаток на конец"], name="Остаток на конец квартала (правая шкала)", mode="lines+markers+text", line=dict(color=U.NAVY, width=2.2),
                   marker=dict(size=6), text=[f(v_) for v_ in Q["Остаток на конец"]], textposition="top center", textfont=dict(size=10), secondary_y=True)
    qf.update_layout(barmode="group", margin=dict(l=8, r=8, t=30, b=8), legend=dict(orientation="h", y=-0.15), title=f"Динамика замечаний: {sel_q}", hovermode="x unified")
    qf.update_yaxes(title_text="Поступило / устранено, замечаний", gridcolor=U.LINE, secondary_y=False, rangemode="tozero")
    qf.update_yaxes(title_text="Остаток, замечаний", showgrid=False, secondary_y=True, rangemode="tozero")
    U.chart(qf, key="pf_qchart", height=380)
    st.markdown('<div class="note">Остаток на дату среза и число квартир с открытыми замечаниями определены по реестру замечаний. Поквартальный ход, разбивка закрытых замечаний (устранено, отменено, приостановлено) и доля квартир, где всё устранено, рассчитаны по накопленной статистике ЖК.</div>', unsafe_allow_html=True)
    with st.expander("Расширенные показатели по замечаниям и квартирам"):
        rr = lambda r_: [f(r_["total"]), f(r_["fixed"]), f(r_["cancelled"]), f(r_["suspended"]), f(r_["left"]), f(r_["left_cum"]), pc(r_["fixed"], r_["total"]), pc(r_["cancelled"], r_["total"]),
                         f"{r_['avg_days']:.0f}", C.fmt_pct(r_["overdue_share"])]
        ranked_ = PF.by_risk(projects)
        t1 = [[p_["name"]] + rr(p_["rem"]) for p_ in ranked_] + [["Итого по портфелю"] + rr(RM)]
        U.fin_table(["ЖК", "Всего замечаний", "Устранено", "Отменено", "Приостановлено", "Остаток к устранению", "Остаток нарастающим итогом", "Доля устранённых", "Доля отменённых",
                     "Средний срок устранения, дней", "Доля просроченных"], t1, right=range(1, 11), total_last=True, hide=(2, 3, 4, 7, 8))
        kr = lambda r_: [f(r_["flats_with"]), f(r_["flats_fixed_any"]), f(r_["flats_all_fixed"]), f(r_["flats_unfixed"]), f(r_["flats_one_unfixed"]), f(r_["flats_total"])]
        t2 = [[p_["name"]] + kr(p_["rem"]) + [fm(p_["risk_blocked"]), fr(p_["risk_blocked"] / p_["risk_day"]) if p_["risk_day"] else PF.DASH] for p_ in ranked_] + \
             [["Итого по портфелю"] + kr(RM) + [fm(blocked), fr(blocked / tr_)]]
        U.fin_table(["ЖК", "Квартир с замечаниями", "С хотя бы одним устранённым", "Все замечания устранены", "С неустранёнными", "С одним неустранённым замечанием", "Всего квартир", "Неустойка по квартирам с замечаниями, ₽/день", "Доля в дневной неустойке ЖК"],
                    t2, right=range(1, 9), total_last=True, hide=(2, 3, 5, 6))

# ---------------------------------------------------------------- 7. Разбор ЖК
U.section("Детализация по ЖК", "Единый набор показателей для каждого ЖК: обзор и ключевые проблемы, шахматка, замечания, подрядчики, финансы, динамика", anchor="drill", num="11.")
if st.session_state.get("pf_sel") not in names:
    st.session_state["pf_sel"] = names[0]


def _sync_project():
    st.session_state["pf_goto"] = st.session_state["pf_sel"]
    update_project_route(st.session_state["pf_sel"])


sel = st.selectbox("ЖК для детализации", names, key="pf_sel", on_change=_sync_project)
p = next(x for x in projects if x["name"] == sel)
d = DA[p["key"]]
A_, REM, CT = d["units"], d["remarks"], d["contractors"]
st.markdown(f'<div class="dec-h" style="font-size:20px">{html.escape(p["name"])}</div>', unsafe_allow_html=True)
tabs = st.tabs(["Обзор", "Шахматка", "Замечания", "Подрядчики", "Финансы", "Динамика"])

with tabs[0]:
    U.kpi_cards([
        dict(label="Просрочка по ДДУ, квартир", value=f(p["overdue_kv"]), delta=C.fmt_delta(p["overdue_delta"]),
             foot=f"{fr(p['overdue_kv'] / to_)} просрочки портфеля"),
        dict(label="Из них готовы к передаче без замечаний", value=f(p["ready"]), delta=("", "flat"),
             foot=f"{fr(p['ready'] / p['overdue_kv']) if p['overdue_kv'] else '—'} просрочки ЖК · неустойка {fm(p['ready_risk'])}/день"),
        dict(label=DAILY_PENALTY, value=fm(p["risk_day"]), delta=("", "flat"), foot=f"{fr(p['risk_day'] / tr_)} дневной неустойки портфеля"),
        dict(label="Передано за неделю, квартир", value=f(p["week_fact"]),
             delta=C.fmt_delta(p["week_fact"] - p["week_prev"], good_when_down=False) if p["week_prev"] is not None else ("", "flat"),
             foot="Изменение к предыдущей неделе"),
        dict(label="Открытых замечаний", value=f(p["remarks"]), delta=("", "flat"), foot=f"критических {f(p['critical'])}"),
    ])
    st.markdown('<div class="dec-h" style="font-size:17px">Решения по ЖК</div>', unsafe_allow_html=True)
    for i, d_ in enumerate(p["decisions"], 1):
        roles_ = "".join(f'<span class="pf-role">{html.escape(r)}</span>' for r in d_["roles"])
        st.markdown(
            f'<div class="dec-h"><span class="no">{i}</span>{html.escape(d_["title"])}{" — главное решение" if i == 1 else ""}</div>'
            f'<div class="dec"><div><div class="k">Что меняется</div><div class="v">{html.escape(d_["mechanism"])}.<br><br><span class="k">Группа мер</span><br>{html.escape(d_["kind"])}</div></div>'
            f'<div><div class="k">Обоснование</div><div class="v">{html.escape(d_["basis"])}</div></div>'
            f'<div><div class="k">Ожидаемый эффект</div><div class="v"><span class="big">−{fm(d_["effect_day"])} в день</span>'
            f'к концу 4-й недели; −{fm(d_["effect"])} за 4 недели · {fr(d_["effect_day"] / p["risk_day"] if p["risk_day"] else 0)} дневной неустойки ЖК</div></div>'
            f'<div><div class="k">Контрольный показатель</div><div class="v">{html.escape(d_["metric"])}<br><br><span class="k">Ответственные роли</span><br>{roles_}</div></div></div>',
            unsafe_allow_html=True)
    st.markdown('<div class="dec-h" style="font-size:17px">Ключевые проблемы ЖК</div>', unsafe_allow_html=True)
    for i, pr in enumerate(p["problems"], 1):
        roles = "".join(f'<span class="pf-role">{html.escape(r)}</span>' for r in pr["roles"])
        st.markdown(
            f'<div class="dec-h"><span class="no">{i}</span>{html.escape(pr["title"])}</div>'
            f'<div class="dec"><div><div class="k">Масштаб</div><div class="v"><span class="big">{f(pr["n"])} {pl(pr["n"])}</span>'
            f'≈{fm(pr["risk"])} в день · {fr(pr["share_risk"])} дневной неустойки ЖК<br>Корпуса: {html.escape(pr["korpusa"])}</div></div>'
            f'<div><div class="k">Причина</div><div class="v">{html.escape(pr["cause"])}</div></div>'
            f'<div><div class="k">Предлагаемая мера</div><div class="v">{html.escape(pr["action"])}<br><br>'
            f'<span class="k">Ответственные роли</span><br>{roles}</div></div>'
            f'<div><div class="k">Контрольный показатель</div><div class="v">{html.escape(pr["metric"])}<br>'
            f'<b>Текущее значение: {f(pr["baseline"])}</b></div></div></div>', unsafe_allow_html=True)
    if len(p["by_korpus"]):
        bk = p["by_korpus"].head(8).iloc[::-1]
        fig = go.Figure(go.Bar(y=bk["k"], x=bk["n"], orientation="h", marker_color=U.NAVY,
                               text=[f"{f(n)} {pl(n)} · {fm(r)}/день" for n, r in zip(bk["n"], bk["risk"])], textposition="outside", cliponaxis=False,
                               hovertemplate="корпус %{y}: %{x} квартир<extra></extra>"))
        fig.update_layout(title="Корпуса: квартиры в просрочке и неустойка за день", margin=dict(l=8, r=150, t=34, b=8), bargap=.4)
        fig.update_xaxes(showticklabels=False)
        U.chart(fig, key=f"pf_korp_{p['key']}", height=max(200, 36 * len(bk) + 64))
    st.markdown('<div class="dec-h" style="font-size:17px">Корпуса</div>', unsafe_allow_html=True)
    kt = DT.korpus_table(A_, P["price"]).rename(columns={"Дневная экспозиция, ₽": DAILY_PENALTY})
    st.dataframe(kt, hide_index=True, width="stretch", height=min(44 + 35 * len(kt), 420), key=f"pf_kt_{p['key']}",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in kt.columns if c not in ("Корпус", "Передано, %")}
                 | {"Передано, %": st.column_config.NumberColumn(format="%.1f")})

with tabs[1]:
    ks = DT.korpus_list(A_)
    kt2 = DT.korpus_table(A_, P["price"]).set_index("Корпус")
    dflt = int(kt2["Дневная экспозиция, ₽"].reset_index(drop=True).idxmax())
    kk = st.selectbox("Корпус", ks, index=dflt, key=f"pf_chess_{p['key']}", format_func=lambda k: f"Корпус {k}")
    row = kt2.loc[kk]
    st.markdown(f'<div class="note">Корпус {html.escape(kk)}: помещений {f(row["Помещений"])}, передано {fr(row["Передано, %"] / 100)}, просрочено по ДДУ {f(row["Просрочка по ДДУ"])}, '
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
        fg.add_bar(y=g["Группа"][::-1], x=g["Замечаний"][::-1] - g["Просрочено более 45 дней"][::-1], orientation="h", name="В срок", marker_color=U.SILVER)
        fg.add_bar(y=g["Группа"][::-1], x=g["Просрочено более 45 дней"][::-1], orientation="h", name="Просрочено более 45 дней", marker_color=U.RISK)
        fg.update_layout(barmode="stack", title="Замечания по категориям", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.2))
        U.chart(fg, key=f"pf_rg_{p['key']}", height=300)
    with r2:
        ag = DT.remark_ages(REM)
        fa = go.Figure(go.Bar(x=ag["Возраст замечания"], y=ag["Замечаний"], marker_color=U.NAVY, text=[f(v) for v in ag["Замечаний"]], textposition="outside"))
        fa.update_layout(title="Возраст открытых замечаний", margin=dict(l=8, r=8, t=34, b=8))
        fa.update_yaxes(showticklabels=False)
        U.chart(fa, key=f"pf_ra_{p['key']}", height=300)
    U.fin_table(["Категория", "Замечаний", "Доля", "Критических", "Просрочено более 45 дней", "% просрочено", "Блокируют передачу"],
                [[r["Группа"], f(r["Замечаний"]), f"{r['Доля, %']:.1f}%".replace(".", ","), f(r["Критических"]), f(r["Просрочено более 45 дней"]),
                  f"{r['% просрочено']:.1f}%".replace(".", ","), f(r["Блокируют передачу"])] for _, r in g.iterrows()]
                + [["Итого", f(g["Замечаний"].sum()), "100,0%", f(g["Критических"].sum()), f(g["Просрочено более 45 дней"].sum()),
                    C.fmt_pct(g["Просрочено более 45 дней"].sum() / max(g["Замечаний"].sum(), 1), 1), f(g["Блокируют передачу"].sum())]],
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
    fc.update_layout(title="Балл риска подрядчиков (10 наибольших значений)", margin=dict(l=8, r=40, t=34, b=8), bargap=.4)
    fc.update_xaxes(showticklabels=False, range=[0, 110])
    U.chart(fc, key=f"pf_ctr_{p['key']}", height=340)
    view = pd.DataFrame({
        "Подрядчик": ct["Подрядчик"], "Группа": ct["Группа"], "Замечаний": ct["Замечаний"], "Квартир": ct["Квартир"], "Просрочено": ct["Просрочено"],
        "% просрочено": (100 * ct["% просрочено"]).round(1), "Критических": ct["Критических"], "Блокирует квартир": ct["Блок. квартир"].astype(int),
        "Балл риска": ct["Балл риска"], "Класс риска": ct["Класс риска"], "Стоимость устранения, ₽": ct["Оценка стоимости открытых, ₽"].round().astype(int)})
    st.dataframe(view, hide_index=True, width="stretch", height=min(44 + 35 * len(view), 460), key=f"pf_ctt_{p['key']}",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in ("Замечаний", "Квартир", "Просрочено", "Критических", "Блокирует квартир", "Стоимость устранения, ₽")}
                 | {"% просрочено": st.column_config.NumberColumn(format="%.1f"), "Балл риска": st.column_config.NumberColumn(format="%.1f")})
    st.markdown('<div class="note">Балл риска (0–100) рассчитан по доле просроченных и критических замечаний, средней просрочке, числу блокируемых квартир и объёму замечаний. '
                'Названия подрядчиков даны без реквизитов.</div>', unsafe_allow_html=True)

with tabs[4]:
    pen = p["penalty"]
    U.kpi_cards([
        dict(label=DAILY_PENALTY, value=fm(p["risk_day"]), delta=("", "flat"), foot=f"по готовым квартирам: {fm(p['ready_risk'])}/день"),
        dict(label="Накопленная неустойка, верхняя оценка", value=fm(p["accrued_up"]), delta=("", "flat"), foot=f"нижняя оценка {fm(p['accrued_lo'])}"),
        dict(label="Стоимость устранения замечаний", value=fm(p["remarks_cost"]), delta=("", "flat"), foot=f"{f(p['remarks'])} замечаний"),
        dict(label="Потенциал претензий к подрядчикам", value=fm(p["claim_potential"]), delta=("", "flat"), foot="по просроченным замечаниям, оценка"),
    ])
    bk_ = pen["by_korpus"].head(10)
    U.fin_table(["Корпус", "Квартир с неустойкой", "из них не переданы", "Накопленная неустойка, верхняя оценка", "Накопленная неустойка, нижняя оценка"],
                [[r["Корпус"], f(r["kv"]), f(r["nt"]), fm(r["up"]), fm(r["lo"])] for _, r in bk_.iterrows()], right=range(1, 5))
    st.markdown('<div class="note">Показаны 10 корпусов с наибольшей накопленной неустойкой.</div>',
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
        fo = go.Figure(go.Scatter(x=w["Неделя"], y=w["Просрочка на конец недели, квартир"], mode="lines+markers", line=dict(color=U.NAVY, width=2.5)))
        fo.update_layout(title="Просрочка по ДДУ на конец недели, квартир", margin=dict(l=8, r=8, t=34, b=8))
        fo.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
        fo.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        U.chart(fo, key=f"pf_wo_{p['key']}", height=300)
    U.fin_table(["Неделя", "Передано, квартир", "Передано, всего", "Просрочка на конец недели, квартир"],
                [[r["Неделя"] + (" (неполная)" if r["partial"] else ""), f(r["Передано, квартир"]), f(r["Передано, всего"]), f(r["Просрочка на конец недели, квартир"])]
                 for _, r in w.iterrows()], right=range(1, 4))

# ---------------------------------------------------------------- 8. Деньги по портфелю
U.section("Финансы: неустойка и стоимость устранения", "", anchor="money", num="12.")
U.kpi_cards([
    dict(label="Накопленная неустойка (верхняя оценка)", value=fm(tot["accrued_up"]), delta=("", "flat"),
         foot=f"расчёт с {dd(pf_demo.ACCRUAL_START)} по {slice_text} · нижняя оценка {fm(tot['accrued_lo'])}"),
    dict(label="Расчёт стоимости устранения замечаний", value=fm(tot["remarks_cost"]), delta=("", "flat"), foot=f"{f(tot['remarks'])} замечаний"),
])
U.fin_table(["ЖК", DAILY_PENALTY, "Накопленная неустойка, верхняя оценка", "Накопленная неустойка, нижняя оценка", "Стоимость устранения замечаний", "Потенциал претензий"],
            [[x["name"], f(round(x["risk_day"])), fm(x["accrued_up"]), fm(x["accrued_lo"]), fm(x["remarks_cost"]), fm(x["claim_potential"])]
             for x in projects] + [["Итого", f(round(tot["risk_day"])), fm(tot["accrued_up"]), fm(tot["accrued_lo"]), fm(tot["remarks_cost"]), fm(tot["claim_potential"])]], right=range(1, 6), total_last=True)
with st.expander("Сценарий будущих выплат по ЖК"):
    st.caption(f"Допущения сценария. Возможные требования составляют {C.fmt_pct(K['claim'])} верхней оценки неустойки. "
               f"Ожидаемые выплаты рассчитаны с учётом снижения требований на {C.fmt_pct(K['cut'])}.")
    payout_rows = [[p_["name"], fm(p_["ladder"]["claimed"]), fm(p_["ladder"]["expected"])] for p_ in projects]
    payout_rows.append(["Итого по портфелю", fm(LD["claimed"]), fm(LD["expected"])])
    U.fin_table(["ЖК", "Возможные требования по сценарию", "Ожидаемые выплаты по сценарию"], payout_rows, right=(1, 2), total_last=True)
st.markdown(f"**Сценарий накопленной неустойки к {dd(package_date)}**")
baseline_accrual = tot["accrued_up"] + tot["risk_day"] * DC.MONTH_W * 7
U.fin_table(["Условия сценария", "Накоплено к дате, расчёт"], [
    ["При ставке и объёме просрочки на дату среза", fm(baseline_accrual)],
    ["При выполнении пакета мер", fm(baseline_accrual - pack_effect)],
    ["Разница до затрат", fm(pack_effect)],
], right=(1,))
st.caption("Обе суммы — сценарий. База = накоплено на дату среза + дневная сумма × 28 дней. Во втором варианте из базы вычитается эффект пакета. Выплаты и новый приток в этом сценарии не учитываются.")

# ---------------------------------------------------------------- 9. Поручения
U.section("Поручения к согласованию", f"Единая контрольная дата — {priority_due}. Плановые показатели за новый цикл начинаются с нуля.", anchor="orders", num="13.")
order_head = ["Действие", "Поручение и ЖК", "Ответственный", "Проверка", "Было → цель", "Расчёт за 4 недели", "Затраты"]
def order_row(measure, requires_approval):
    instruction = priority_request if requires_approval else measure["title"]
    scope = f'<span>{html.escape(instruction)}<br>{measure_links(measure)}</span>'
    return ["Утвердить" if requires_approval else "Принять к сведению", scope, measure["owner"], priority_due,
            result_text(measure), f"−{fm(measure['effect'])}", fm(measure["cost"])]

st.markdown("**Нужно решение ГД**")
approval_rows = [order_row(priority_package, True)] if priority_package else []
if not priority_package and priority_measure:
    approval_rows.append(["Утвердить", f'{html.escape(priority_request)}<br>{project_link(focus["key"], focus["name"])}',
                          priority_owner, priority_due, "Проверка применимости 0 → 1", "Вне пакета", "Без отдельного бюджета"])
approval_rows.append(["Утвердить", plan_title + " и бюджет пакета", plan_owner, priority_due,
                      f"Передано 0 → {f(plan_total)}; просрочка {f(tot['overdue_kv'])} → {f(plan_closing)}",
                      f"−{fm(pack_effect)}", fm(pack_cost)])
U.fin_table(order_head, approval_rows, right=(5, 6))
st.markdown("**В рабочем порядке**")
U.fin_table(order_head, [order_row(measure, False) for measure in package if measure is not priority_package], right=(5, 6))
st.caption("«Утвердить» — требуется решение генерального директора. «Принять к сведению» — за выполнение отвечает руководитель подразделения.")
st.markdown(f"**Недельный план передач из текущей просрочки по ЖК · контроль {priority_due}**")
plan_rows = [[project_link(row["project"]["key"], row["project"]["name"]), f(row["baseline"]),
              *[f(row["groups"][key]) for key in PF.PROBLEMS], f(row["total"]), f(row["new"]), f(row["closing"]), priority_due]
             for row in plan]
plan_rows.append(["Итого", f(tot["overdue_kv"]), *[f(sum(row["groups"][key] for row in plan)) for key in PF.PROBLEMS],
                  f(plan_total), f(plan_new), f(plan_closing), priority_due])
U.fin_table(["ЖК", "Было в просрочке", "Готовы", "Ключи в ОЗ", "Отказ", "Готовность не открыта", "Есть замечания",
             "План передач", "Новые просрочки", "Целевой остаток", "Дата"], plan_rows, right=range(1, 10), total_last=True)
st.caption(f"Целевой остаток: {f(tot['overdue_kv'])} − {f(plan_total)} + {f(plan_new)} = {f(plan_closing)} квартир. "
           "Квартиры из мер уже входят в план. Новые просрочки рассчитаны по наступающим датам ДДУ в реестре, если эти квартиры останутся непереданными.")

# ---------------------------------------------------------------- 10. Допущения
U.section("Допущения и методология расчёта", "", anchor="notes", num="14.")
U.sources(
    "<b>Расчётная неустойка за день.</b> Отчёт суммирует оценки по непереданным квартирам с просрочкой по ДДУ. "
    "Дневная сумма = расчётная ставка в процентах / 100 / 150 × расчётная цена квартиры. "
    "Цены квартир по ДДУ приняты допущением: "
    + ", ".join(f"{DA[key]['name']} — {pr_in[key]:.1f} млн ₽".replace(".", ",") for key in project_keys)
    + "; значения меняются в боковой панели, неустойка пересчитывается пропорционально. Коммерческие помещения не включены; машиноместа и кладовые учитываются отдельно по расчётным ценам. "
    f"<br><b>Накопленная неустойка.</b> За дни просрочки с {dd(pf_demo.ACCRUAL_START)} по {slice_text}; для переданных квартир расчёт заканчивается датой передачи. "
    "Верхняя оценка — дневная сумма × дни, нижняя — 75% верхней. Выплаты приняты равными нулю. "
    f"<br><b>Сценарий выплат.</b> Возможные требования — {C.fmt_pct(K['claim'])} верхней границы. Предполагаемое снижение требований — {C.fmt_pct(K['cut'])}. "
    "Ожидаемые будущие выплаты по сценарию — возможные требования за вычетом предполагаемого снижения. "
    "<br><b>Готовы к передаче</b> — квартира просрочена по ДДУ, не передана, готовность подтверждена (есть дата готовности, нет отмены готовности и мотивированного отказа), открытых замечаний нет; "
    "неустойка по этим квартирам входит в итог по ЖК. Причины непередачи определены по статусу и дате записи собственника и по реестру официальных вызовов; границы в 7 и 30 дней приняты допущением. "
    "<br><b>Темп и целевой темп.</b> Чистый темп — среднее за 4 последние недели по датам актов приёма-передачи (передано из просрочки за вычетом притока новых просрочек). "
    "Целевой темп снижения — тот же показатель за предыдущие четыре недели с запасом 10%; план передачи за неделю — средний факт четырёх предыдущих полных недель с запасом 10%. "
    "Прогноз линейный: темп, приток и расчётная ставка не меняются. "
    "<br><b>Ожидаемый эффект решений</b> — снижение расчётной неустойки за день к концу 4-й недели и накопленное за 4 недели относительно текущего темпа; рассчитывается от доли причины в дневной неустойке ЖК "
    "по допущениям, приведённым в разделе «Управленческие решения». Дневная неустойка по квартирам с открытыми замечаниями распределяется между подрядчиками пропорционально числу квартир с их замечаниями. "
    "Стоимость устранения — оценка по средней стоимости замечания; потенциал претензий — трёхкратная стоимость просроченных замечаний. "
    "<br><b>Реестр замечаний.</b> Остаток, доля просроченных замечаний и число квартир с неустранёнными замечаниями определены по реестру замечаний. Поступившие за период, устранённые, отменённые и приостановленные замечания, "
    "поквартальный ход и доля квартир, где устранены все замечания, рассчитаны по накопленной статистике ЖК. Соблюдаются тождества: всего = устранено + отменено + приостановлено + остаток; "
    "остаток на конец квартала = перенос + поступило нарастающим итогом − закрыто. Неустойка по квартирам с замечаниями включает сумму за день по просроченным квартирам с открытыми замечаниями. "
    "<br>Персональных данных в отчёте нет: объекты обозначены номерами, подрядчики — наименованиями организаций. Стоимость второй смены определяется допущением о цене одной дополнительной приёмки.")
st.markdown("**Допущения для решений и плана**")
U.fin_table(["Что задано", "Значение или правило"], [
    ["Даты", f"Срез {slice_text}; сравнение с {dd(period_start)}; контроль {priority_due}; горизонт мер до {dd(package_date)}."],
    ["Бунинские кварталы", f"{pf_demo.BK_EXPIRED_POOL} квартир с истёкшим сроком вызова в реестре; дополнение к первоначальной группе — из готовых без записи и вызова. Возраст уведомлений в добавленной группе — {pf_demo.BK_NOTICE_AGE} дней. Цель = группа × {C.fmt_pct(DC.UNILATERAL_SHARE)}, с округлением."],
    ["Охват остальных мер", f"Ранние слоты {C.fmt_pct(DC.SLOT_SHARE)}, повторная приёмка {C.fmt_pct(DC.REFUSAL_RESOLVED)}, устранение замечаний {C.fmt_pct(DC.REMARKS_HANDOVER_SHARE)}, обзвон {C.fmt_pct(DC.CALL_RESPONSE)}. Целое число округляется по ЖК."],
    ["Цели", "На неделю — четверть планового результата меры с округлением вверх по мере. Остаток просрочки = текущий остаток − план передач + новый приток."],
    ["План передач", "Среднее число передач за 4 последних полных недели × 1,10. Сначала резервируются квартиры по мерам, остальной план делится пропорционально оставшимся группам."],
    ["Затраты на одну квартиру", ", ".join(f'{measure["title"].lower()} — {fm(DC.PACKAGE_RATES[measure["key"]])}' for measure in package)],
    ["Эффект мер", "В день к концу периода = план квартир × средняя дневная неустойка в группе ЖК. За 4 недели = эффект в день × 28 / 2. Затраты = план квартир × тариф."],
])
with st.expander("Сверка расчётов портфеля и мер"):
    U.fin_table(["Показатель", "Расчёт в рублях или квартирах"], [
        ["Остаток просрочки", f"{f(tot['overdue_prev'])} − {f(tot['left_n'])} + {f(tot['entered_n'])} = {f(tot['overdue_kv'])}"],
        ["Готовы к передаче", f"{f(sum(reason['n'] for reason in RSN.values()))} = {f(tot['ready'])}"],
        ["Расчётная неустойка за день", f"{f(tot['risk_prev'])} − {f(tot['left_risk'])} + {f(tot['entered_risk'])} = {f(tot['risk_day'])} ₽/день"],
        ["Доли неустойки", f"{fr(sum(project['risk_day'] / tr_ for project in projects))} по исходным суммам; на экране доли округляются."],
        ["Накоплено", f"{f(sum(project['accrued_up'] for project in projects))} ₽, с {dd(pf_demo.ACCRUAL_START)} по {slice_text}"],
        ["Пакет", f"{f(pack_daily)} × 28 / 2 ≈ {f(pack_effect)} ₽; {f(pack_effect)} − {f(pack_cost)} ≈ {f(pack_effect-pack_cost)} ₽ после затрат."],
    ])
    U.fin_table(["Мера", "ЖК", "Группа, квартир", "Цель за 4 недели", "Среднее, ₽/день", "Снижение на 4-й неделе, ₽/день"],
                [[measure["title"], project_link(item["project"]["key"], item["project"]["name"]),
                  f(item["eligible"]), f(item["units"]), f(item["average"]), f(item["effect_day"])]
                 for measure in package for item in measure["items"]], right=(2, 3, 4, 5))

st.html(U.navigation_script(st.session_state.pop("_pf_sync_route", None), st.session_state.pop("_pf_scroll", None),
                            st.session_state.pop("_pf_initial_route", False)),
        unsafe_allow_javascript=True)
