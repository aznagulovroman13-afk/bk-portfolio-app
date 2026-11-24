"""Отчёт по заселению — отчёт для генерального директора (открывается без пароля)."""
import html
from importlib import reload
from math import ceil

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="Отчёт по заселению", page_icon="🏢", layout="wide", initial_sidebar_state="collapsed")

import pf_ui as U  # noqa: E402


import pf_core as C  # noqa: E402
import pf_data  # noqa: E402
import pf_decide as DC  # noqa: E402
import pf_detail as DT  # noqa: E402
import pf_demo  # noqa: E402
import pf_nav as N  # noqa: E402
import pf_model as PF  # noqa: E402
import pf_penalty as PN  # noqa: E402
import pf_gantt as GT  # noqa: E402
import pf_drill as DR  # noqa: E402
import pf_roles as R  # noqa: E402
import pf_portfolio2 as P2  # noqa: E402

# Streamlit может выполнить новый app.py в процессе, где ещё загружены старые модули.
REPORT_SCHEMA = "v31"
if getattr(PF, "REPORT_SCHEMA", None) != REPORT_SCHEMA or getattr(PN, "PENALTY_SCHEMA", None) != "p4" \
        or getattr(GT, "GANTT_SCHEMA", None) != "g3" or getattr(DR, "DRILL_SCHEMA", None) != "d4" \
        or getattr(R, "ROLES_SCHEMA", None) != "r1" or not hasattr(U, "gloss") or "cell" not in N.ROUTE_FIELDS \
        or getattr(P2, "P2_SCHEMA", None) != "q3":
    for module in (R, U, DC, DT, pf_demo, PF, PN, GT, DR, P2):
        reload(module)
    if "cell" not in N.ROUTE_FIELDS:
        try:
            reload(N)
        except Exception:  # компонент маршрутов уже зарегистрирован — достаточно новых полей
            N.ROUTE_FIELDS = tuple(dict.fromkeys((*N.ROUTE_FIELDS, "card", "cell")))

st.markdown(U.CSS, unsafe_allow_html=True)
st.markdown(
    '<style>header[data-testid="stHeader"], header[data-testid="stHeader"] * {pointer-events: none !important;} '
    'header[data-testid="stHeader"] [data-testid="stExpandSidebarButton"] {pointer-events: auto !important;}'
    '.fin.ready-reasons td:first-child {width: 48%;} '
    '.ready-reasons .reason-track {display: block; height: 5px; margin-top: 6px; background: #E9EDF2; border-radius: 3px;} '
    '.ready-reasons .reason-fill {display: block; height: 100%; background: #5B7BA6; border-radius: inherit;}'
    """
    .exec-header {padding: 16px 24px; margin: 2px 0 0;}
    .exec-header .ttl {margin: 2px 0 0; line-height: 1.2;}
    #summary {margin-top: 14px;}
    .exec-summary {display: grid; gap: 12px; color: var(--ink);}
    .exec-date {font-size: 13px; color: var(--ink2); margin: 0;}
    .exec-metrics, .exec-projects {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px;}
    .exec-metrics {grid-template-columns: repeat(3, minmax(0, 1fr));}
    .exec-metric, .exec-project {border: 1px solid var(--line); background: var(--paper); border-radius: 7px;}
    .exec-metric {min-width: 0; padding: 11px 16px 12px; text-decoration: none !important;}
    .exec-metric:hover {border-color: #6799CE; background: #F5F8FC;}
    .exec-label {display: block; font-size: 12px; line-height: 1.35; color: var(--ink2); font-weight: 600;}
    .exec-metric strong {display: block; font-size: clamp(25px, 3vw, 41px); line-height: 1.1; font-weight: 700;
      font-variant-numeric: tabular-nums; letter-spacing: -.035em; margin: 4px 0; color: var(--navy);}
    .exec-metric em {font-style: normal; font-size: .48em; font-weight: 600; white-space: nowrap;}
    .exec-delta {display: block; font-size: 12px; color: var(--ink2);}
    .exec-delta.good {color: #246829;}
    .exec-delta.bad {color: var(--risk);}
    .exec-project {min-width: 0; padding: 15px 18px; border-top: 3px solid var(--gold);}
    .exec-project h3 {font-size: clamp(17px, 1.55vw, 22px); line-height: 1.25; margin: 0; padding: 0; font-weight: 650;}
    .exec-project h3 a {color: var(--navy) !important;}
    .exec-project-metrics {display: grid; grid-template-columns: 1fr 1.3fr 1fr; gap: 8px; margin: 11px 0 14px;}
    .exec-project-metrics dt {color: var(--ink2); font-size: 12px; line-height: 1.25;}
    .exec-project-metrics dd {margin: 4px 0 0; color: var(--navy); font-size: 15px; font-weight: 650; font-variant-numeric: tabular-nums;}
    .exec-summary h2.exec-projects-heading {margin: 4px 0 0 !important; padding: 0 !important;
      font-size: 19px !important; line-height: 1.3; color: var(--navy);}
    .exec-annual {width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums;}
    .exec-annual th, .exec-annual td {padding: 6px; text-align: right; border-bottom: 1px solid var(--line);}
    .exec-annual th:first-child {text-align: left;}
    .exec-annual thead th {background: #F3F5F8; color: var(--ink2); font-size: 11px;}
    .exec-annual td {color: var(--navy);}
    .exec-annual td.is-missing, .exec-annual td.coverage {color: var(--ink2); font-size: 11px;}
    .exec-annual td.coverage {text-align: left;}
    .exec-control {display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 4px 16px; color: var(--ink2);}
    .exec-plan-readiness {margin-top: 9px; font-size: 13px; color: var(--ink2);}
    .exec-plan-readiness strong {color: var(--navy);}
    .exec-plan-readiness .pending {color: #80550E; font-weight: 600;}
    .exec-control {margin-top: 9px; font-size: 13px;}
    .exec-control strong {color: var(--navy);}
    .pfnav a[data-pf-route] {color: #C5CEDA !important;}
    .pfnav a[data-pf-route]:hover, .pfnav a[aria-current="page"][data-pf-route] {color: #fff !important;}
    .exec-summary :focus-visible {outline: 2px solid #6799CE; outline-offset: 3px;}
    @media (max-width: 760px) {
      .stMainBlockContainer:has(.exec-summary) {padding-right: var(--bk-pad) !important;}
      .exec-projects {grid-template-columns: 1fr;}
      .exec-metrics {grid-template-columns: 1fr 1fr;} .exec-metrics > :last-child {grid-column: 1 / -1;}
      .exec-metric .exec-label {font-size: 11px;}
      .exec-metric strong {font-size: clamp(15px, 4vw, 25px); letter-spacing: -.04em;}
      .exec-metric em {font-size: .75em;}
      .exec-delta {font-size: 11px;}
      .exec-header, .exec-project, .exec-metric {padding: 12px;}
      .exec-project-metrics dd {font-size: 13px;}
      .exec-annual th, .exec-annual td {padding: 5px 3px;}
    }
    """
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
    '.weekly .fields > div + div {border-left: 0; border-top: 1px solid #38506A;}}</style>',
    unsafe_allow_html=True)


@st.cache_data(show_spinner="Загрузка данных…")
def _load_demo_projects(projects: tuple, schema: str = REPORT_SCHEMA):
    return pf_demo.build(projects)


DA = _load_demo_projects(pf_data.PROJECTS, REPORT_SCHEMA)
with st.sidebar:
    if st.button("Выйти", key="pf_exit"):
        st.session_state.clear()
        st.rerun()
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


def annual_transfers(units, through, project_name, history=None):
    """Передача по годам с результатом приёмки. 2024–2025 — ранее переданные очереди ЖК (history), 2026 — квартиры среза."""
    date = "Дата принятия собственником"
    result = "Результат передачи"
    accepted = units.loc[units["Тип объекта"].eq("Квартира") & C.transferred_mask(units)
                         & units[date].le(through)].reindex(columns=[date, result])
    cur = accepted.loc[accepted[date].dt.year.eq(2026)]
    cw, cwo = int(cur[result].eq("С замечаниями").sum()), int(cur[result].eq("Без замечаний").sum())
    share_with = cw / (cw + cwo) if cw + cwo else 0.35
    rows = []
    for year in (2024, 2025, 2026):
        records = accepted.loc[accepted[date].dt.year.eq(year)]
        total = len(records)
        with_remarks = int(records[result].eq("С замечаниями").sum())
        without_remarks = int(records[result].eq("Без замечаний").sum())
        classified = with_remarks + without_remarks
        if not total and history and year in history:
            total = history[year]
            with_remarks = int(round(total * share_with))
            without_remarks = total - with_remarks
            classified = total
        values = (total, with_remarks if classified or not total else None, without_remarks if classified or not total else None)
        cells = "".join(f"<td>{f(value)}</td>" if value is not None else '<td class="is-missing">—</td>' for value in values)
        rows.append(f'<tr><th scope="row">{year}</th>{cells}</tr>')
        if 0 < classified < total:
            rows.append(f'<tr><td colspan="4" class="coverage">{year} · Результат указан по {f(classified)} из {f(total)}</td></tr>')
        elif total and not classified:
            rows.append(f'<tr><td colspan="4" class="coverage">{year} · Результат приёмки в актах не указан</td></tr>')
    return (f'<table class="exec-annual" aria-label="Передача квартир по годам, {html.escape(project_name)}">'
            '<thead><tr><th scope="col">Год</th><th scope="col">Передано</th>'
            '<th scope="col">С замечаниями</th><th scope="col">Без замечаний</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def _mln(v, nd=1):
    return f"{v / 1e6:,.{nd}f}".replace(",", "\u00a0").replace(".", ",")


PEN_LAW = {"ddu": "Просрочка передачи", "remarks": "Недостатки"}
PEN_TIP = {"ddu": "Неустойка за просрочку передачи объекта, ч. 2 ст. 6 214-ФЗ",
           "remarks": "Неустойка за нарушение сроков устранения недостатков, ч. 8 ст. 7 214-ФЗ"}


def penalty_years(r, compact=False, name=""):
    """Уровень 2: неустойка ЖК по видам и годам, начислено и мораторий (ПП № 326), млн ₽."""
    Y = PN.YEARS
    nd = 2 if compact else 1
    def cells(vals, accrued):
        out = []
        for y in Y:
            v = vals[y]
            out.append('<td>—</td>' if accrued and PN.year_in_moratorium(y) and abs(v) < 1 else f"<td>{_mln(v, nd)}</td>")
        return "".join(out) + f"<td><b>{_mln(sum(vals.values()), nd)}</b></td>"
    head = "".join(f'<th scope="col"{" title=\"Мораторий ПП № 326\"" if PN.year_in_moratorium(y) else ""}>{y}'
                   f'{"<span class=sub>мораторий</span>" if PN.year_in_moratorium(y) else ""}</th>' for y in Y)
    body = ""
    for m in ("ddu", "remarks"):
        body += (f'<tr class="pen-m"><th scope="row" title="{PEN_TIP[m]}">{PEN_LAW[m]}</th>{cells(r[m], True)}</tr>'
                 f'<tr class="pen-eff"><th scope="row" title="Не начислено по ПП № 326">мораторий</th>{cells(r["effect"][m], False)}</tr>')
    acc = {y: r["ddu"][y] + r["remarks"][y] for y in Y}
    body += f'<tr class="pen-tot"><th scope="row">Итого</th>{cells(acc, True)}</tr>'
    cls = "exec-annual pen-years" + (" compact" if compact else "")
    return (f'<table class="{cls}" aria-label="Неустойка по годам, {html.escape(name or r["name"])}"><thead><tr>'
            f'<th scope="col">млн ₽</th>{head}<th scope="col">Всего</th></tr></thead><tbody>{body}</tbody></table>')


def pen_cell(r):
    """Ячейка таблицы ЖК: уровень 1 — итог, уровень 2 (раскрытие) — по видам."""
    return (f'<details class="mx mx-cell"><summary><b>{_mln(r["total"])}</b></summary>'
            f'<span class="sub" title="{PEN_TIP["ddu"]}">передача {_mln(sum(r["ddu"].values()))}</span>'
            f'<span class="sub" title="{PEN_TIP["remarks"]}">недостатки {_mln(sum(r["remarks"].values()), 2)}</span></details>')


PEN_BASIS = (
    "<b>Просрочка передачи.</b> Ч. 2 ст. 6 214-ФЗ: 1/300 ставки Банка России на день исполнения обязательства от цены договора "
    "за каждый день просрочки; для гражданина — в двойном размере (1/150).",
    "<b>Недостатки.</b> Ч. 8 ст. 7 214-ФЗ в ред. 266-ФЗ (с 01.09.2024): 1/150 ставки от стоимости устранения недостатков "
    "за каждый день просрочки, не более этой стоимости; до 01.09.2024 — 1% в день (п. 1 ст. 23 Закона о защите прав потребителей). "
    "Ч. 4 ст. 10 в ред. 482-ФЗ (с 01.01.2025): суммы по требованиям о качестве — не более 3% цены договора.",
    "<b>Мораторий.</b> ПП РФ № 326 (ред. ПП № 1916, № 925): с 22.03.2024 по 31.12.2025 обе неустойки не начисляются; "
    "с 01.07.2023 до начала моратория ставка не выше 7,5% (ключевая на 01.07.2023). ПП № 2227: отсрочка уплаты "
    "по требованиям, предъявленным до начала моратория, — до 31.12.2026. С 01.01.2026 начисление в общем порядке.",
    "<b>Методика.</b> 2026 год — по квартирам среза, как в разделе «Финансы»; 2024–2025 годы — ранее переданные очереди ЖК. "
    "Мораторий — сумма, которая начислялась бы без ПП № 326. Подробнее — раздел «Методология».",
)


def basis_details():
    """Уровень 3: правовое основание и методика."""
    return ('<details class="mx mx-l3"><summary>Основания</summary><div class="pen-basis">'
            + "".join(f"<p>{x}</p>" for x in PEN_BASIS) + '</div></details>')


def penalty_details(r, compact=False, name="", open_=False, label=None):
    """Уровни 1–3: итог неустойки → по видам и годам → основания."""
    summary = (f'<span class="mx-t">{label}</span>' if label else
               f'<span class="mx-t">Неустойка</span><b>{_mln(r["total"], 1)} млн ₽</b><span class="mx-s">мораторий {_mln(r["effect_total"], 1)}</span>')
    return (f'<details class="mx mx-l2"{" open" if open_ else ""}><summary>{summary}</summary>'
            + penalty_years(r, compact, name) + basis_details() + '</details>')


def penalty_section(r):
    st.markdown(penalty_details(r, open_=False),
                unsafe_allow_html=True)


def gantt_causes_portfolio(scheds):
    """Уровень 3 портфельного Ганта: причины по ЖК."""
    rows = "".join(
        f'<tr><td>{project_link(g["key"], g["name"])}</td><td>{html.escape(g["critical_name"])}</td><td class="r">+{g["delay"]}</td>'
        f'<td>{html.escape(g["cause"])}</td><td class="r">{_mln(g["penalty_ddu"])}</td><td class="r">{_mln(g["penalty_rem"], 2)}</td>'
        f'<td>{html.escape(g["risk"])}</td></tr>' for g in scheds)
    return ('<details class="mx mx-l3"><summary>Причины</summary><div class="tw"><table class="fin gantt-causes"><thead><tr>'
            '<th>ЖК</th><th>Этап</th><th class="r" title="Медианная задержка массовой передачи, дней">Дни</th><th>Причина</th>'
            '<th class="r" title="Неустойка 2026 года за просрочку передачи, ч. 2 ст. 6 214-ФЗ, млн ₽">Ч. 2 ст. 6</th>'
            '<th class="r" title="Неустойка 2026 года за нарушение сроков устранения недостатков, ч. 8 ст. 7 214-ФЗ, млн ₽">Ч. 8 ст. 7</th>'
            f'<th>Риск</th></tr></thead><tbody>{rows}</tbody></table></div></details>')


def gantt_causes_project(g):
    """Уровень 3 Ганта ЖК: критический путь — этапы с задержкой и порождённая неустойка."""
    rows = []
    for r in g["rows"]:
        if not r["slip"]:
            continue
        law = " · ".join(x for x in (f'{_mln(r["penalty_ddu"])} млн ₽ по ч. 2 ст. 6' if r["penalty_ddu"] else "",
                                      f'{_mln(r["penalty_rem"], 2)} млн ₽ по ч. 8 ст. 7' if r["penalty_rem"] else "") if x)
        role = "критический" if r["critical"] else "сопутствующий"
        rows.append(f'<tr><td><b class="tip" title="{html.escape(r["full"])}">{html.escape(r["stage"])}</b><span class="sub">{role}</span></td>'
                    f'<td class="r">{r["plan_end"]:%d.%m.%y}</td><td class="r">{r["fact_end"]:%d.%m.%y}</td>'
                    f'<td class="r">+{r["slip"]}</td><td>{law}</td></tr>')
    return ('<details class="mx mx-l3"><summary>Причины</summary>'
            f'<div class="gantt-cause"><b>{html.escape(g["cause"])}.</b> Главный риск — {html.escape(g["risk"].lower())}. '
            f'Мера — {html.escape(g["decision"])}.</div>'
            '<div class="tw"><table class="fin"><thead><tr><th>Этап</th><th class="r">План</th><th class="r">Факт</th>'
            '<th class="r">Дни</th><th>Неустойка 2026</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
            '<div class="pen-basis"><p>Задержка этапа сдвигает последующие этапы; итоговая задержка равна медианной просрочке по ДДУ '
            'просроченных квартир ЖК. Неустойка по ч. 2 ст. 6 214-ФЗ распределена между этапами пропорционально их задержке, '
            'по ч. 8 ст. 7 — отнесена к устранению замечаний. Период моратория (ПП № 326) неустойку не порождает.</p></div></details>')


def gantt_project_section(g):
    st.markdown(f'<div class="gantt-l1"><span class="mx-t">Сроки</span><b>+{g["delay"]} дн.</b>'
                f'<span class="mx-s">критический этап — {html.escape(g["critical_name"])}</span></div>', unsafe_allow_html=True)
    with st.expander("Гант"):
        U.chart(GT.project_figure(g), key=f"gantt_{g['key']}", height=540)
        st.markdown(gantt_causes_project(g), unsafe_allow_html=True)


def main_row(project, data, through):
    """Строка главной таблицы: передача по годам, остаток 2026, просрочка, неустойка (мораторий учтён)."""
    key = project["key"]
    units = data["units"]
    kv = units.loc[units["Тип объекта"].eq("Квартира")]
    done = C.transferred_mask(kv)
    date = kv["Дата принятия собственником"]
    hist = PN.history_transfers(key, len(kv))
    due = pd.to_datetime(kv["Срок по ДДУ"])
    pen = PEN[key]
    return dict(key=key, name=project["name"], t2024=hist[2024], t2025=hist[2025],
                t2026=int((done & date.dt.year.eq(2026) & date.le(through)).sum()),
                left2026=int((due.dt.year.eq(2026) & ~done).sum()), overdue=int(project["overdue_kv"]), remarks=int(project["rem"]["left_cum"]),
                pen_delay=sum(pen["ddu"].values()), pen_remarks=sum(pen["remarks"].values()), effect=pen["effect_total"],
                resp=GANTT[key]["responsible"], resp_stage=GANTT[key]["critical_name"], dec=decision_info(project))


def pen_shown(r):
    """Неустойка ЖК 2024–2026 так, как она складывается из ячеек сводки (за задержку + за замечания, по 1 знаку)."""
    return _mln(round(r["pen_delay"] / 1e5) * 1e5 + round(r["pen_remarks"] / 1e5) * 1e5)


def decision_info(p):
    """Главное решение ЖК: что решить, роль, эффект за 4 недели (млн ₽) и в днях медианной задержки, контроль «было → цель»."""
    if not p.get("decisions"):
        return None
    d = p["decisions"][0]
    g = GANTT[p["key"]]
    share = min(1.0, d["effect_day"] / p["risk_day"]) if p["risk_day"] else 0.0
    days = max(1, round(g["delay"] * share))
    target = max(0, p["overdue_kv"] - max(1, round(p["overdue_kv"] * share)))
    crit = next(r for r in g["rows"] if r["critical"])
    better = sorted([c for c in p["cands"] if c["effect_day"] > d["effect_day"] and c["key"] != d["key"] and c["key"] in MAIN_OWNER],
                    key=lambda c: -c["effect_day"])
    why = (f'Критический этап — «{g["critical_name"]}» (+{crit["slip"]} дн., {_mln(crit["penalty_ddu"] + crit["penalty_rem"])} млн ₽ неустойки 2026): '
           f'решение снимает задержку этого этапа. Наибольший эффект среди мер ЖК')
    if better:
        b = better[0]
        why += (f', кроме «{b["short3"]}» (−{fm(b["effect_day"])}/день): эта мера — главная в ЖК {MAIN_OWNER[b["key"]]}, '
                'главные решения ЖК не повторяются')
    why += "."
    return dict(key=d["key"], short=d["short3"], title=d["title"], role=g["responsible"]["short"],
                company=g["responsible"]["company"], works=g["responsible"]["works"],
                effect=d["effect"], effect_day=d["effect_day"], days=days, why=why, metric=d["metric"], basis=d["basis"],
                was=p["overdue_kv"], target=target, needs_gd=d.get("needs_gd", False))


def _mln_s(v):
    """Млн ₽ для эффекта: до 1 млн — два знака."""
    return _mln(v, 2 if abs(v) < 1e6 else 1)


MAIN_COLS = (("t2024", "2024"), ("t2025", "2025"), ("t2026", "2026"))


MAIN_TOP = ("bunino", "scandc", "zen")     # три ЖК главного экрана по эскизу (БК, СК, ДЗ); остальные — по «Развернуть»


# Выборочная подсветка сводки: красный — нарушен срок и неустойка выше порога, зелёный — ноль нарушений и высокий темп передачи.
HL_OVERDUE_BAD = 40        # кв. с нарушенным сроком в ЖК
HL_PEN_BAD = 100e6         # неустойка 2024–2026 за задержку в ЖК, ₽
HL_T2026_GOOD = 150        # передано в 2026, кв.
HL_REM_BAD = 600           # открытых замечаний в ЖК, шт.
HL_REM_GOOD = 250          # мало открытых замечаний, шт.


def _tone(k, v, total=False):
    if k == "overdue":
        return "good" if v == 0 else "bad" if v >= HL_OVERDUE_BAD else ""
    if k == "remarks" and not total:
        return "good" if v < HL_REM_GOOD else "bad" if v >= HL_REM_BAD else ""
    if k == "pen_delay":
        return "bad" if v >= HL_PEN_BAD else ""
    if k == "t2026" and not total:
        return "good" if v >= HL_T2026_GOOD else ""
    return ""


def _u(unit):
    return f'<span class="u">\u00a0{unit}</span>'


MT_LABELS = {"t2026": "Передано 2026", "left2026": "Остаток 2026", "overdue": "Нарушен срок", "remarks": "Замечания",
             "pen_delay": "Неустойка за задержку", "pen_remarks": "Неустойка за замечания"}
_ARROW = lambda d_: "▲" if d_ > 0 else "▼" if d_ < 0 else "•"


def dyn_rows():
    """Динамика нарушенного срока по ЖК за 12 недель: мини-график, изменение за неделю, оценка к целевому темпу."""
    srows = PF.screen_rows(projects)
    scale = max(v for row in srows for v in row["trend"]) or 1
    dates = projects[0]["weekly"]["Неделя"].tolist()
    out = {}
    for r_ in srows:
        pr = projects_by_key[r_["key"]]
        out[r_["key"]] = dict(trend=r_["trend"], bad=r_["worse"], d=r_["d_over"], target=max(0, pr["overdue_prev"] - pr["target_burn"]), scale=scale)
    out["total"] = dict(trend=[sum(p_["trend"][i] for p_ in projects) for i in range(len(dates))], bad=portfolio_lag, d=d_over,
                        target=max(0, tot["overdue_prev"] - tot["target_burn"]), scale=None)
    return out, dates


def dyn_html(dy, dates, cls="mt-dy"):
    """Мини-график + «▼ −N кв. за неделю» + «в рамках / ниже целевого темпа» (красный — ниже темпа, зелёный — снижение)."""
    tone = "bad" if dy["bad"] else "good" if dy["d"] < 0 else ""
    chg = " wr" if dy["d"] > 0 else " improved" if dy["d"] < 0 else ""
    return (f'<div class="{cls}"><span class="dy-s">{U.spark(dy["trend"], dy["bad"], scale=dy["scale"], dates=dates, target=dy["target"])}</span>'
            f'<span class="dy-w"><span class="sub{chg}">{_ARROW(dy["d"])} {sg(dy["d"])}\u00a0кв. за неделю</span>'
            f'<span class="dy-t{" hl-" + tone if tone else ""}">{"ниже целевого темпа" if dy["bad"] else "в рамках целевого темпа"}</span></span></div>')


def main_table(rows, slice_label, open_more=False):
    """Уровень 1: главная таблица портфеля по эскизу — ЖК × передача по годам × остаток × просрочка × неустойка.
    Видны три ЖК (MAIN_TOP), остальные раскрываются строкой «Развернуть»; «Итого» — плашка над таблицей, всегда по всем ЖК."""
    tot = {k: sum(r[k] for r in rows) for k in ("t2026", "left2026", "overdue", "remarks", "pen_delay", "pen_remarks", "effect")}
    dyn, dyn_dates = dyn_rows()
    def cells(r):
        key = r.get("key", "total")
        def a(v, cell, unit, sep=False):
            tone = _tone(cell, r[cell])
            cls = "r" + (" sep" if sep else "") + (f" hl-{tone}" if tone else "") + (" key" if cell == "overdue" else "")
            return f'<td class="{cls}" data-l="{MT_LABELS[cell]}">{N.link(v, css="cell", card=key, cell=cell)}{_u(unit)}</td>'
        return (a(f(r["t2026"]), "t2026", "кв.")
                + a(f(r["left2026"]), "left2026", "кв.", True) + a(f(r["overdue"]), "overdue", "кв.") + a(f(r["remarks"]), "remarks", "шт.")
                + a(_mln(r["pen_delay"]), "pen_delay", "млн ₽", True) + a(_mln(r["pen_remarks"]), "pen_remarks", "млн ₽"))
    def decide(r):
        d = r["dec"]
        if not d:
            return '<td class="sep decide" data-l="Что решить">—</td>'
        content = (f'<b>{html.escape(d["short"])}</b><span class="sub">−{_mln_s(d["effect"])} млн ₽ за 4 нед. · −{d["days"]} дн.</span>')
        return f'<td class="sep decide" data-l="Что решить">{N.link(d["short"], content=content, css="cell", card=r["key"], cell="decide")}</td>'
    def resp(r):
        o = r["resp"]
        sub = f'<span class="sub">{html.escape(o["works"] + " " + o["company"]).strip()}</span>' if o["company"] else ""
        return (f'<td class="sep resp" data-l="Ответственный" title="Критический этап: {html.escape(r["resp_stage"])}">'
                f'{N.link(o["short"], css="cell", card=r["key"], cell="resp")}{sub}</td>')
    top = [r for r in rows if r["key"] in MAIN_TOP]
    more = [r for r in rows if r["key"] not in MAIN_TOP]
    jk = lambda r: f'<td class="jk">{N.link(r["name"], card=r["key"])}{dyn_html(dyn[r["key"]], dyn_dates)}</td>'
    body = "".join(f'<tr>{jk(r)}{cells(r)}{decide(r)}{resp(r)}</tr>' for r in top)
    body += "".join(f'<tr class="mt-hidden">{jk(r)}{cells(r)}{decide(r)}{resp(r)}</tr>' for r in more)
    if more:
        body += (f'<tr class="mt-toggle"><td colspan="9"><label for="mt-more">'
                 f'<span class="mt-open">▾ Развернуть · ещё {len(more)} ЖК</span><span class="mt-close">▴ Свернуть</span></label></td></tr>')
    gd_lbl = f"Нужно решение ГД: {len(GD_ITEMS)}"
    tl = lambda v, cell: N.link(v, css="cell", card="total", cell=cell)
    def item(label, value, k, tip="", unit=""):
        tone = _tone(k, tot[k], True) if k in tot else ""
        return (f'<div class="ti{" hl-" + tone if tone else ""}{" key" if k == "overdue" else ""}" data-k="{k}"'
                + (f' title="{html.escape(tip)}"' if tip else "") + f'><span class="tl">{label}</span><b>{value}{_u(unit) if unit else ""}</b></div>')
    def sub(k, lbl, value, unit):
        tone = _tone(k, tot[k], True)
        return f'<span data-k="{k}"{" class=" + chr(34) + "hl-" + tone + chr(34) if tone else ""}><i>{lbl}</i>{tl(value, k)}{_u(unit)}</span>'
    total_bar = ('<div class="mt-total" id="portfolio-total" aria-label="Итого">'
                 f'<div class="ti tn"><span class="tl">{len(rows)} ЖК</span><b>{N.link("Итого", card="total")}</b></div>'
                 + item("Передано 2026", tl(f(tot["t2026"]), "t2026"), "t2026", "Передано квартир по передаточным актам в 2026 году", "кв.")
                 + item("Остаток 2026", tl(f(tot["left2026"]), "left2026"), "left2026", "Квартиры со сроком по ДДУ в 2026 году, ещё не переданные", "кв.")
                 + item("Нарушен срок передачи", tl(f(tot["overdue"]), "overdue"), "overdue",
                        "Не переданы по передаточному акту, срок передачи по ДДУ нарушен, на дату среза", "кв.")
                 + f'<div class="ti tdy" data-k="dyn"><span class="tl">Динамика за неделю</span>{dyn_html(dyn["total"], dyn_dates, "mt-dy tot-dy")}</div>'
                 + item("Замечания", tl(f(tot["remarks"]), "remarks"), "remarks", "Открытые замечания по квартирам, на дату среза", "шт.")
                 + '<div class="tg" title="Начислено с учётом моратория ПП № 326"><span class="tl">Неустойка начислена</span><div class="tgi">'
                 + sub("pen_delay", "за задержку", _mln(tot["pen_delay"]), "млн ₽")
                 + sub("pen_remarks", "за замечания", _mln(tot["pen_remarks"]), "млн ₽") + '</div></div>'
                 + item("Что решить", tl(gd_lbl, "decide"), "decide")
                 + item("Ответственные", tl("По ЖК", "resp"), "resp")
                 + '</div>')
    return ('<section class="main-port" id="main-portfolio">'
            f'<input type="checkbox" id="mt-more" class="mt-more"{" checked" if open_more else ""}>'
            f'<p class="exec-date">Срез <b>{slice_label}</b> · {len(rows)} ЖК · неустойка в млн ₽ с учётом моратория</p>'
            + total_bar +
            f'<div class="mt-l2"><b>Раскрытие по ЖК</b><span>{len(rows)} ЖК · динамика нарушенного срока за 12 недель, пунктир — целевой остаток; '
            'нажмите на цифру — разбивка по домам и квартирам</span></div>'
            '<div class="tw"><table class="fin main-table"><thead>'
            '<tr><th rowspan="2">ЖК</th><th class="r tip" rowspan="2" title="Передано квартир по передаточным актам в 2026 году">Передано 2026<span class="unit">кв.</span></th>'
            '<th class="r sep tip" rowspan="2" title="Квартиры со сроком по ДДУ в 2026 году, ещё не переданные">Остаток 2026</th>'
            '<th class="r tip" rowspan="2" title="Квартиры, не переданные по передаточному акту, у которых наступил и нарушен срок передачи по ДДУ, на дату среза">Нарушен срок передачи<span class="unit">кв.</span></th>'
            '<th class="r tip" rowspan="2" title="Открытые замечания по квартирам ЖК, на дату среза">Замечания<span class="unit">шт.</span></th>'
            '<th class="grp sep" colspan="2" title="Начислено с учётом моратория ПП № 326">Неустойка, млн ₽<span class="unit">начислено</span></th>'
            '<th class="sep tip" rowspan="2" title="Главное решение ЖК: эффект за 4 недели до затрат и сокращение медианной задержки передачи">Что решить</th>'
            '<th class="sep tip" rowspan="2" title="Роль, получающая поручение по главному решению; отвечает за критический этап задержки (диаграмма Ганта)">Ответственный</th></tr>'
            '<tr>'
            '<th class="r sep tip" title="За просрочку передачи, ч. 2 ст. 6 214-ФЗ">За задержку</th>'
            '<th class="r tip" title="За нарушение сроков устранения недостатков, ч. 8 ст. 7 214-ФЗ">За замечания</th></tr>'
            f'</thead><tbody>{body}</tbody></table></div>'
            f'<p class="exec-date mt-legend"><span class="lg-bad">■</span> нарушен срок от {HL_OVERDUE_BAD} кв., замечаний от {HL_REM_BAD} шт., ниже целевого темпа, неустойка за задержку от {_mln(HL_PEN_BAD, 0)} млн ₽ · '
            f'<span class="lg-good">■</span> нет нарушений, замечаний меньше {HL_REM_GOOD} шт., передано в 2026 от {HL_T2026_GOOD} кв., снижение за неделю · '
            'нажмите на ЖК — карточка с диаграммой Ганта откроется ниже.</p></section>')


def responsibility_table(g):
    """Ответственные за задержку: участник → этап → дней задержки → неустойка этапа (как в диаграмме Ганта)."""
    rows = [r for r in g["rows"] if r["slip"] > 0 or r["penalty_rem"] > 0]   # замечания: неустойка ч. 8 ст. 7 — на устранении
    body = "".join(
        f'<tr{" class=\"crit\"" if r["critical"] else ""}><td><b>{html.escape(r["owner"]["short"])}</b>'
        + (f'<span class="sub">{html.escape(r["owner"]["company"])}</span>' if r["owner"]["company"] else "")
        + f'</td><td>{html.escape(r["stage"])}{" · критический" if r["critical"] else ""}</td>'
        f'<td class="r">{"+" + str(r["slip"]) if r["slip"] else "—"}</td><td class="r">{_mln(r["penalty_ddu"] + r["penalty_rem"])}</td>'
        f'<td>{html.escape(r["owner"]["co"]) or "—"}</td></tr>' for r in rows)
    tot = sum(r["penalty_ddu"] + r["penalty_rem"] for r in rows)
    body += f'<tr class="tot"><td>Итого</td><td></td><td class="r">+{g["delay"]}</td><td class="r">{_mln(tot)}</td><td></td></tr>'
    return ('<div class="tw"><table class="fin resp-table" aria-label="Ответственные за задержку">'
            '<thead><tr><th>Ответственный</th><th>Этап</th><th class="r tip" title="Задержка этапа, дней">Дней</th>'
            '<th class="r tip" title="Неустойка 2026 за просрочку передачи (ч. 2 ст. 6) и за замечания (ч. 8 ст. 7), приходящаяся на этап; 2024–2025 — в разделе «Неустойка по годам»">Неустойка 2026, млн ₽</th>'
            '<th class="tip" title="Подразделение, контролирующее исполнение">Контроль</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


CELL_TITLES = {"t2024": "Передача 2024", "t2025": "Передача 2025", "t2026": "Передача 2026", "left2026": "Остаток 2026",
               "overdue": "Нарушен срок передачи, кв.", "remarks": "Замечания, шт.", "pen_delay": "Неустойка за задержку", "pen_remarks": "Неустойка за замечания",
               "resp": "Ответственный", "decide": "Что решить"}


@st.cache_data(show_spinner=False, max_entries=64)
def _drill_data(key: str, price: float, schema: str):
    """Квартиры и дома ЖК (pf_drill) — считаются один раз на ЖК и цену ДДУ."""
    p = projects_by_key[key]
    cause = p["decisions"][0]["key"] if p.get("decisions") else ""
    return DR.build(DA[key], GANTT[key], p["price"], PEN[key], cause)


def drill_data(key, schema=REPORT_SCHEMA):
    return _drill_data(key, float(projects_by_key[key]["price"]), schema)


def _months_table(counts, label):
    head = "".join(f'<th class="r">{m}</th>' for m in DR.MONTHS)
    cells = "".join(f'<td class="r">{f(c) if c else "—"}</td>' for c in counts)
    return (f'<div class="tw"><table class="fin cell-months" aria-label="{html.escape(label)}"><thead><tr><th>Месяц</th>{head}<th class="r">Год</th></tr></thead>'
            f'<tbody><tr><td>Передано</td>{cells}<td class="r"><b>{f(sum(counts))}</b></td></tr></tbody></table></div>')


def _year_pen_table(pen, kind):
    """Неустойка вида kind по годам: начислено, мораторий; сумма лет = ячейка сводки."""
    rows = "".join(f'<tr><td>{y}</td><td class="r">{_mln(pen[kind][y], 2 if kind == "remarks" else 1)}</td>'
                   f'<td class="r">{_mln(pen["effect"][kind][y], 2 if kind == "remarks" else 1) if pen["effect"][kind][y] else "—"}</td>'
                   f'<td>{"мораторий ПП № 326" if PN.year_in_moratorium(y) else ("частично мораторий" if y == 2024 else "по квартирам среза — ниже")}</td></tr>'
                   for y in PN.YEARS)
    tot = sum(pen[kind].values())
    return ('<div class="tw"><table class="fin cell-years"><thead><tr><th>Год</th><th class="r">Начислено, млн ₽</th>'
            '<th class="r tip" title="Не начислено в период моратория ПП № 326">Мораторий, млн ₽</th><th>Расчёт</th></tr></thead>'
            f'<tbody>{rows}<tr class="tot"><td>Итого</td><td class="r">{_mln(tot, 2 if kind == "remarks" else 1)}</td><td></td><td></td></tr></tbody></table></div>')


def orders_by_role(p):
    data = DA[p["key"]]
    items = []
    for d_ in p.get("decisions", []):
        stage = GT.CAUSES.get(d_["key"], GT.DEFAULT_CAUSE)[0]
        o = GT.owner(stage, d_["key"], data)
        items.append(f'<li><b>{html.escape(o["short"])}</b> — {html.escape(d_["title"])}</li>')
    return f'<ul class="card-decisions">{"".join(items)}</ul>'


def cell_panel(p, row, cell):
    """Панель ячейки сводки: каждая цифра раскрывается до домов и квартир (суммы совпадают с ячейкой)."""
    key = p["key"]
    dr = drill_data(key, REPORT_SCHEMA)
    pen = PEN[key]
    g = GANTT[key]
    title = CELL_TITLES[cell]
    if cell in ("t2024", "t2025"):
        y = int(cell[1:])
        eff = pen["effect"]["ddu"][y] + pen["effect"]["remarks"][y]
        pen_txt = (f'Неустойка {y} года не начислялась — мораторий ПП № 326 (не начислено {_mln(eff)} млн ₽)'
                   if PN.year_in_moratorium(y) else
                   f'Неустойка {y} года: за задержку {_mln(pen["ddu"][y])} млн ₽, за замечания {_mln(pen["remarks"][y], 2)} млн ₽; '
                   f'с 22.03.2024 — мораторий ПП № 326 (не начислено {_mln(eff)} млн ₽)')
        body = (f'<p class="cell-note">Ранее переданные очереди ЖК: передано {f(row[cell])} квартир. {pen_txt}.</p>'
                + _months_table(DR.split_months(row[cell]), title))
    elif cell == "t2026":
        acc = [a for a in dr["apts"] if DR.MODES["t2026"][0](a)]
        months = [sum(pd.Timestamp(a["accepted"]).month == m for a in acc) for m in range(1, 13)]
        body = _months_table(months, title) + DR.houses_html(dr, "t2026", uid="c-")
    elif cell == "left2026":
        stages = {}
        for a in dr["apts"]:
            if a["left26"]:
                stages[a["stage_name"]] = stages.get(a["stage_name"], 0) + 1
        st_line = " · ".join(f"{html.escape(k)} {f(v)}" for k, v in sorted(stages.items(), key=lambda x: -x[1]))
        body = f'<p class="cell-note">По этапам: {st_line}.</p>' + DR.houses_html(dr, "left2026", uid="c-")
    elif cell == "overdue":
        body = (f'<p class="cell-note">Не переданы, срок по ДДУ нарушен. Причина ЖК: {html.escape(g["cause"])}.</p>'
                + DR.houses_html(dr, "over", uid="c-"))
    elif cell == "remarks":
        body = (f'<p class="cell-note">Открыто замечаний: {f(row["remarks"])} шт.; из них с нарушенным сроком устранения — {f(p["rem"]["overdue"])} шт. '
                'По домам и квартирам — открытые замечания.</p>' + DR.houses_html(dr, "open", uid="c-"))
    elif cell == "pen_delay":
        body = (_year_pen_table(pen, "ddu") + f'<p class="cell-note">2026 по квартирам: цена ДДУ × ставка / 150 × дни; ч. 2 ст. 6 214-ФЗ, '
                f'отсрочка уплаты по ПП № 2227 до 31.12.2026.</p>' + DR.houses_html(dr, "ddu", uid="c-"))
    elif cell == "pen_remarks":
        body = (_year_pen_table(pen, "remarks") + '<p class="cell-note">2026 по квартирам с просроченными замечаниями; ч. 8 ст. 7 214-ФЗ '
                'в ред. 266-ФЗ: 1/150 ставки от стоимости устранения, не более 3% цены договора.</p>' + DR.houses_html(dr, "rem", uid="c-"))
    else:
        body = (responsibility_table(g) + '<div class="card-resp-ttl">Поручения по ролям</div>' + orders_by_role(p))
    return (f'<section class="cell-panel" id="cell-{key}-{cell}"><div class="cell-ttl">{html.escape(title)} · '
            f'<b>{html.escape(p["name"])}</b></div>{body}</section>')


def total_cell_panel(rows, cell):
    """Ячейка строки «Итого»: разбивка по ЖК, каждая строка ведёт к ячейке ЖК."""
    title = CELL_TITLES[cell]
    if cell == "decide":
        gd = "".join(f'<li>{N.link(it["title"], card=it["card"], cell=it["cell"])} · {html.escape(it["role"])} · '
                     f'−{_mln_s(it["effect"])} млн ₽ за 4 нед.{" · затраты " + _mln_s(it["cost"]) + " млн ₽" if it["cost"] else ""}</li>' for it in GD_ITEMS)
        body = "".join(f'<tr><td>{N.link(r["name"], card=r["key"], cell="decide")}</td><td>{html.escape(r["dec"]["short"])}</td>'
                       f'<td>{html.escape(r["dec"]["role"])}</td><td class="r">−{_mln_s(r["dec"]["effect"])}</td><td class="r">−{r["dec"]["days"]}</td></tr>'
                       for r in rows if r["dec"])
        tv = sum(r["dec"]["effect"] for r in rows if r["dec"])
        body += f'<tr class="tot"><td>Итого</td><td></td><td></td><td class="r">−{_mln_s(tv)}</td><td></td></tr>'
        return (f'<section class="cell-panel" id="cell-total-decide"><div class="cell-ttl">Что решить · <b>Итого</b></div>'
                f'<div class="card-resp-ttl">Нужно решение ГД · {len(GD_ITEMS)}</div><ol class="gd-list">{gd}</ol>'
                '<div class="tw"><table class="fin cell-total"><thead><tr><th>ЖК</th><th>Главное решение</th><th>Поручение</th>'
                '<th class="r" title="Эффект за 4 недели до затрат">Эффект, млн ₽</th><th class="r" title="Сокращение медианной задержки передачи">Дней</th></tr></thead>'
                f'<tbody>{body}</tbody></table></div><p class="cell-note">Сумма главных решений ЖК не равна бюджету пакета: пакет на странице «Решения» '
                'считается по группам квартир и с учётом пересечения мер.</p></section>')
    if cell == "resp":
        body = "".join(f'<tr><td>{N.link(r["name"], card=r["key"], cell="resp")}</td><td>{html.escape(r["resp"]["label"])}</td>'
                       f'<td>{html.escape(r["resp_stage"])}</td><td class="r">+{GANTT[r["key"]]["delay"]}</td></tr>' for r in rows)
        head = '<th>ЖК</th><th>Ответственный</th><th>Критический этап</th><th class="r">Дней</th>'
    else:
        val = (lambda r: _mln(r[cell], 1)) if cell.startswith("pen") else (lambda r: f(r[cell]))
        body = "".join(f'<tr><td>{N.link(r["name"], card=r["key"], cell=cell)}</td><td class="r">{val(r)}</td></tr>' for r in rows)
        tv = sum(r[cell] for r in rows)
        body += f'<tr class="tot"><td>Итого</td><td class="r">{_mln(tv) if cell.startswith("pen") else f(tv)}</td></tr>'
        head = f'<th>ЖК</th><th class="r">{html.escape(title)}{", млн ₽" if cell.startswith("pen") else ("" if cell in ("overdue", "remarks") else ", кв.")}</th>'
    return (f'<section class="cell-panel" id="cell-total-{cell}"><div class="cell-ttl">{html.escape(title)} · <b>Итого</b></div>'
            f'<div class="tw"><table class="fin cell-total"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></section>')


def decision_block(p, row):
    """Первый блок карточки ЖК: решение → роль → эффект ₽ и дни → контроль «было → цель» → почему это решение."""
    d = row["dec"]
    if not d:
        return ""
    who = html.escape(d["role"]) + (f'<span class="sub">{html.escape((d["works"] + " " + d["company"]).strip())}</span>' if d["company"] else "")
    pkg = ""
    if priority_package and d["key"] == "unilateral" and any(it["project"]["key"] == p["key"] for it in priority_package["items"]):
        pkg = f'; к утверждению ГД — первая очередь {f(priority_package["eligible"])} кв., −{_mln_s(priority_package["scenario_effect"])} млн ₽'
    gd = '<span class="db-gd">нужно решение ГД</span>' if d["needs_gd"] or any(it["card"] == p["key"] for it in GD_ITEMS) else ""
    return (f'<section class="dec-block" id="decide-{p["key"]}"><div class="db-ttl">Что решить{gd}</div>'
            f'<div class="db-main">{html.escape(d["short"])}</div><div class="db-desc">{html.escape(d["title"])}</div>'
            '<div class="db-grid">'
            f'<div><span class="db-l">Поручение</span><b>{who}</b></div>'
            f'<div><span class="db-l">Эффект за 4 недели</span><b>−{_mln_s(d["effect"])} млн ₽</b><span class="sub">−{fm(d["effect_day"])} в день к 4-й неделе, до затрат{pkg}</span></div>'
            f'<div><span class="db-l">Задержка передачи</span><b>−{d["days"]} дн.</b><span class="sub">медиана {GANTT[p["key"]]["delay"]} → {GANTT[p["key"]]["delay"] - d["days"]} дн.</span></div>'
            f'<div><span class="db-l">Контроль · следующий срез</span><b>{f(d["was"])} → {f(d["target"])} кв.</b><span class="sub">квартиры с нарушенным сроком; показатель меры — {html.escape(d["metric"].lower())}</span></div>'
            '</div>'
            f'<details class="mx mx-l3"><summary>Почему это решение</summary><div class="db-why">{html.escape(d["why"])} {html.escape(d["basis"])}.</div></details>'
            '</section>')


def project_card_l2(p, row, cell=None):
    """Уровень 2: карточка ЖК с ключевыми показателями и диаграммой Ганта; уровень 3 — причины, неустойка, основания, решения."""
    g = GANTT[p["key"]]
    st.markdown(U.gloss(decision_block(p, row)), unsafe_allow_html=True)
    if cell in CELL_TITLES and cell != "decide":
        st.markdown(U.gloss(cell_panel(p, row, cell)), unsafe_allow_html=True)
    st.markdown(
        '<dl class="exec-project-metrics card-metrics">'
        f'<div><dt>Нарушен срок передачи, кв.</dt><dd>{f(row["overdue"])}</dd></div>'
        f'<div><dt>Неустойка в день</dt><dd>{f(round(p["risk_day"]))} ₽</dd></div>'
        f'<div><dt>Замечания</dt><dd>{f(p["remarks"])}</dd></div>'
        f'<div><dt>Задержка передачи, медиана</dt><dd>+{g["delay"]} дн.</dd></div>'
        f'<div><dt>Критический этап</dt><dd>{html.escape(g["critical_name"])}</dd></div></dl>', unsafe_allow_html=True)
    U.chart(GT.project_figure(g), key=f"gantt_main_{p['key']}", height=540)
    st.markdown('<div class="card-resp"><div class="card-resp-ttl">Ответственные за задержку</div>' + responsibility_table(g) + '</div>'
                + f'<details class="mx mx-l2 dr-sec"><summary>Дома · {len(drill_data(p["key"], REPORT_SCHEMA)["houses"])}</summary>'
                + DR.houses_html(drill_data(p["key"], REPORT_SCHEMA), "all") + '</details>', unsafe_allow_html=True)
    decisions = "".join(
        f'<li><b>{html.escape(d_["title"])}</b>{" — главное решение, см. «Что решить»" if i == 0 else ""}'
        f'<span class="sub">−{fm(d_["effect_day"])} в день к концу 4-й недели</span></li>' for i, d_ in enumerate(p["decisions"]))
    units = DA[p["key"]]["units"]
    hist = {2024: row["t2024"], 2025: row["t2025"]}
    st.markdown(gantt_causes_project(g)
                + f'<details class="mx mx-l3"><summary>Передачи по годам</summary><div class="card-annual" id="exec-project-{p["key"]}">'
                + annual_transfers(units, act_d, p["name"], hist) + '</div></details>'
                + '<details class="mx mx-l3"><summary>Неустойка по годам</summary>' + penalty_years(PEN[p["key"]]) + '</details>'
                + basis_details()
                + f'<details class="mx mx-l3"><summary>Другие меры</summary><ul class="card-decisions">{decisions}</ul></details>'
                + f'<p class="card-open">{project_link(p["key"], "Страница ЖК")}</p>', unsafe_allow_html=True)


def project_link(key, label, tab=None):
    return N.link(label, jk=key, **({"tab": tab} if tab else {}))


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
PEN_T = PN.table(DA, projects)
PEN = {r["key"]: r for r in PEN_T["rows"]}
GANTT_LIST = GT.portfolio(DA, projects, PEN)
GANTT = {g["key"]: g for g in GANTT_LIST}
MAIN_OWNER = {p["decisions"][0]["key"]: p["name"] for p in projects if p.get("decisions")}   # мера → ЖК, где она главная


route = N.read_route()
project_key = route.get("jk")
view = route.get("view", "summary")
if view not in N.REPORT_VIEWS and view != P2.VIEW:
    view = "summary"
st.markdown(P2.menu(None if project_key in projects_by_key else view), unsafe_allow_html=True)

sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
tr_, to_ = max(tot["risk_day"], 1), max(tot["overdue_kv"], 1)

dd = lambda t: t.strftime("%d.%m.%Y")


if project_key in projects_by_key:
    p = projects_by_key[project_key]
    d = DA[project_key]
    A_, REM, CT = d["units"], d["remarks"], d["contractors"]
    tab = route.get("tab", "overview")
    if tab not in N.PROJECT_VIEWS:
        tab = "overview"

    corpus = unit = None
    if tab == "chess":
        corpora = DT.korpus_table(A_, p["price"]).set_index("Корпус")
        corpus = route.get("corpus")
        if corpus not in corpora.index:
            corpus = corpora["Дневная экспозиция, ₽"].idxmax()
        matches = A_.loc[A_["Объект"].eq(route.get("unit")) & A_["Корпус"].astype(str).eq(corpus)]
        if not matches.empty:
            unit = matches.iloc[0]

    st.markdown(N.project_path(p["name"], project_key, tab, corpus,
                               DT.unit_title(unit) if unit is not None else None), unsafe_allow_html=True)
    st.header(p["name"], anchor="drill")
    st.caption(f"Демо-данные · Срез {dd(d['calc_date'])}")
    st.markdown(N.project_menu(project_key, tab), unsafe_allow_html=True)

    if tab == "overview":
        U.kpi_cards([
            dict(label="Просрочка", value=f(p["overdue_kv"]), delta=C.fmt_delta(p["overdue_delta"]),
                 foot=f"квартир по ДДУ · {fr(p['overdue_kv'] / to_)} от итога просрочки"),
            dict(label="Готовы", value=f(p["ready"]), delta=("", "flat"),
                 foot=f"к передаче без замечаний · {fr(p['ready'] / p['overdue_kv']) if p['overdue_kv'] else '—'} просрочки ЖК · неустойка {fm(p['ready_risk'])}/день"),
            dict(label=DAILY_PENALTY, value=fm(p["risk_day"]), delta=("", "flat"), foot=f"{fr(p['risk_day'] / tr_)} от итога неустойки в день"),
            dict(label="Передано за неделю", value=f(p["week_fact"]),
                 delta=C.fmt_delta(p["week_fact"] - p["week_prev"], good_when_down=False) if p["week_prev"] is not None else ("", "flat"),
                 foot="Изменение к предыдущей неделе"),
            dict(label="Замечания", value=f(p["remarks"]), delta=("", "flat"), foot=f"открытых, критических {f(p['critical'])}"),
        ])
        penalty_section(PEN[project_key])
        gantt_project_section(GANTT[project_key])
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
            fig.update_layout(title="Корпуса: нарушен срок передачи, кв., и неустойка за день", margin=dict(l=8, r=150, t=34, b=8), bargap=.4)
            fig.update_xaxes(showticklabels=False)
            U.chart(fig, key=f"pf_korp_{p['key']}", height=max(200, 36 * len(bk) + 64))
        U.section("Корпуса", "Откройте корпус, чтобы посмотреть шахматку.")
        kt = DT.korpus_table(A_, p["price"]).rename(columns={"Дневная экспозиция, ₽": DAILY_PENALTY})
        rows = [[N.link(f"Корпус {key}", jk=project_key, tab="chess", corpus=key),
                 f(units), f"{percent:.1f}".replace(".", ","), *map(f, counts)]
                for key, units, percent, *counts in kt.itertuples(index=False, name=None)]
        U.fin_table(list(kt.columns), rows, right=range(1, len(kt.columns)))

    elif tab == "chess":
        if unit is not None:
            DT.show_unit(unit, d["remark_items"])
        else:
            def change_corpus():
                N.set_route(jk=project_key, tab="chess", corpus=st.session_state[corpus_widget])

            corpus_widget = f"pf_chess_{project_key}_{corpus}"
            st.selectbox("Корпус", corpora.index.tolist(), index=corpora.index.get_loc(corpus),
                         key=corpus_widget, format_func=lambda value: f"Корпус {value}", on_change=change_corpus)
            row = corpora.loc[corpus]
            st.caption(f'Помещений {f(row["Помещений"])} · Передано {fr(row["Передано, %"] / 100)} · '
                       f'Просрочено по ДДУ {f(row["Просрочка по ДДУ"])} · Замечаний {f(row["Замечаний"])}. '
                       'Выберите помещение на шахматке, чтобы открыть его карточку.')
            ch, _ = DT.chess_html(A_, corpus, project_key=project_key)
            st.markdown(ch, unsafe_allow_html=True)

    elif tab == "remarks":
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

    elif tab == "contractors":
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

    elif tab == "money":
        pen = p["penalty"]
        U.kpi_cards([
            dict(label=DAILY_PENALTY, value=fm(p["risk_day"]), delta=("", "flat"), foot=f"по готовым квартирам: {fm(p['ready_risk'])}/день"),
            dict(label="Накопленная неустойка, верхняя оценка", value=fm(p["accrued_up"]), delta=("", "flat"), foot=f"нижняя оценка {fm(p['accrued_lo'])}"),
            dict(label="Стоимость устранения замечаний", value=fm(p["remarks_cost"]), delta=("", "flat"), foot=f"{f(p['remarks'])} замечаний"),
            dict(label="Потенциал претензий к подрядчикам", value=fm(p["claim_potential"]), delta=("", "flat"), foot="по просроченным замечаниям, оценка"),
        ])
        penalty_section(PEN[project_key])
        bk_ = pen["by_korpus"].head(10)
        U.fin_table(["Корпус", "Квартир с неустойкой", "из них не переданы", "Накопленная неустойка, верхняя оценка", "Накопленная неустойка, нижняя оценка"],
                    [[r["Корпус"], f(r["kv"]), f(r["nt"]), fm(r["up"]), fm(r["lo"])] for _, r in bk_.iterrows()], right=range(1, 5))
        st.markdown('<div class="note">Показаны 10 корпусов с наибольшей накопленной неустойкой.</div>',
                    unsafe_allow_html=True)

    elif tab == "dynamics":
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

    st.stop()


# ---------------------------------------------------------------- 1. Верхняя сводка
slice_dates = [DA[key]["calc_date"] for key in project_keys]
act_d = projects[0]["act_date"]
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
priority_request = "Утвердить оформление односторонних актов только по квартирам, по которым юридический департамент подтвердит основания" if priority_package else f"Утвердить проверку применимости меры «{priority_measure['short']}»" if priority_measure else "Принять к сведению статус по всем ЖК"
priority_due = dd(review_date)
package_path = DC.incremental_package_forecast(projects, package)
package_end = {row["key"]: row for row in package_path if row["week"] == DC.MONTH_W}
for measure in package:
    effects = [(item, package_end[item["project"]["key"]]) for item in measure["items"]]
    measure["scenario_effect"] = sum(item["effect_day"] / row["potential"] * row["effect"]
                                     for item, row in effects if row["potential"])
    measure["scenario_day"] = sum(item["effect_day"] / row["potential"] * row["day"]
                                  for item, row in effects if row["potential"])
pack_effect = sum(row["effect"] for row in package_end.values())
pack_future_base = sum(row["base"] for row in package_end.values())
pack_units = sum(measure["units"] for measure in package)
pack_cost = sum(measure["cost"] for measure in package)
plan = DC.handover_plan(projects, package, PF.PROBLEMS)
plan_total, plan_new, plan_closing = (sum(row[key] for row in plan) for key in ("total", "new", "closing"))
plan_ready, plan_pending, plan_base, plan_risk_base, plan_risk = (
    sum(row[key] for row in plan) for key in ("booked", "reserve", "closing_base", "risk_base", "risk_total"))
plan_history = f'база {f(plan_ready)} + резерв после проверки {f(plan_pending)}'
plan_title = "Выполнить недельный план передач по ЖК"
budget_title = f"Утвердить бюджет {f(pack_cost)} ₽ на меры по {f(pack_units)} квартирам"
plan_owner = "Директор по заселению"
risk_leader = projects[0]
slice_text = dd(slice_dates[0]) if min(slice_dates) == max(slice_dates) else f"{dd(min(slice_dates))}–{dd(max(slice_dates))}"
priority_amount = f'−{fm(priority_measure["effect_day"])}' if priority_measure else ""
priority_effect = f"{priority_amount}/день к концу 4-й недели" if priority_measure else "без отдельного эффекта"
risk_leader_name = html.escape(risk_leader["name"])
risk_leader_context = f'{risk_leader_name} — {f(round(risk_leader["risk_day"]))} ₽/день'
priority_check = (f"{f(priority_package['week_units'])} {C.plural(priority_package['week_units'], 'односторонний акт', 'односторонних акта', 'односторонних актов')}"
                  if priority_package else "проверить применимость меры")
priority_check_detail = (
    f'За неделю по {act_d:%d.%m} оформлено {f(focus["week_pa_unilateral"])}. В работу по пилоту — {f(priority_package["eligible"])} из {f(RSN["expired"]["n"])} '
    'квартир с истёкшим сроком вызова. Юридический департамент проверяет основания и риск оспаривания.'
    if priority_package else "")
plan_readiness = (
    f'<div class="exec-plan-readiness"><strong>{f(plan_ready)} в базовом плане</strong>'
    f' · {f(plan_pending)} в резерве после подтверждения условий · {f(plan_new)} ожидаемых новых просрочек.</div>'
)
if not priority_package and priority_measure:
    priority_effect += ", потенциал вне пакета"
overdue_tone = "good" if d_over < 0 else "bad" if d_over > 0 else "flat"


def gd_items():
    """«Нужно решение ГД»: те же пункты, что на страницах «Решения» и «Поручения», плюс главные решения ЖК, требующие решения ГД."""
    items = []
    if priority_package:
        keys = [it["project"]["key"] for it in priority_package["items"]]
        items.append(dict(title=f"Утвердить односторонние акты по {f(priority_package['eligible'])} кв. после проверки", role=priority_package["owner"],
                          effect=priority_package["scenario_effect"], cost=priority_package["cost"],
                          scope=", ".join(projects_by_key[k]["name"] for k in keys), card=keys[0] if keys else "total", cell="decide"))
    elif priority_measure:
        items.append(dict(title=f"Утвердить меру «{priority_measure['short3']}»", role=priority_owner, effect=priority_measure["effect"],
                          cost=0.0, scope=focus["name"], card=focus["key"], cell="decide"))
    items.append(dict(title=f"Утвердить бюджет мер по {f(pack_units)} квартирам", role=plan_owner, effect=pack_effect, cost=pack_cost,
                      scope="все ЖК", card="total", cell="decide"))
    done = {it["card"] for it in items}
    for p_ in sorted(projects, key=lambda x: -(x["decisions"][0]["effect"] if x.get("decisions") else 0)):
        d_ = p_["decisions"][0] if p_.get("decisions") else None
        if len(items) >= 3:
            break
        if d_ and d_.get("needs_gd") and p_["key"] not in done:
            items.append(dict(title=f"Утвердить: {d_['short3'].lower()}", role=R.DECISION_ROLE.get(d_["key"], d_["roles"][0]),
                              effect=d_["effect"], cost=0.0, scope=p_["name"], card=p_["key"], cell="decide"))
    return items


GD_ITEMS = gd_items()


def gd_strip():
    def title(it):
        return N.link(it["title"], content="<b>" + html.escape(it["title"]) + "</b>", card=it["card"], cell=it["cell"])
    rows = "".join(
        f'<li>{title(it)}'
        f'<span class="gd-role">{html.escape(it["role"])} · {html.escape(it["scope"])}</span>'
        f'<span class="gd-num">−{_mln_s(it["effect"])} млн ₽ за 4 нед.</span>'
        f'<span class="gd-cost">{("затраты " + _mln_s(it["cost"]) + " млн ₽") if it["cost"] else "без отдельного бюджета"}</span></li>'
        for it in GD_ITEMS)
    return (f'<section class="gd-strip" id="gd-strip"><div class="gd-ttl">Нужно решение ГД · {len(GD_ITEMS)}</div>'
            f'<ol>{rows}</ol><div class="gd-note">Эффект — снижение неустойки за 4 недели до затрат; контроль — на следующем срезе.</div></section>')
if view == P2.VIEW:            # «Портфель 2» — альтернативная версия на тех же данных и расчётах
    P2.render(dict(projects=projects, totals=tot, DA=DA, PEN=PEN, GANTT=GANTT, slice_text=slice_text, route=route,
                   main_row=lambda p_: main_row(p_, DA[p_["key"]], act_d), drill=drill_data))
    st.stop()

if view == "summary":
    st.markdown('<div class="rh exec-header"><div class="kick">Отчёт для генерального директора · Демо-данные</div>'
                '<div class="ttl">Отчёт по заселению</div></div>', unsafe_allow_html=True)
    U.section("Сводка по ЖК", anchor="summary")
    first_projects = ("bunino", "scandc", "scands")
    display_order = [projects_by_key[key] for key in first_projects if key in projects_by_key]
    display_order.extend(project for project in projects if project["key"] not in first_projects)
    main_order = ([projects_by_key[k] for k in MAIN_TOP if k in projects_by_key]
                  + [p_ for p_ in display_order if p_["key"] not in MAIN_TOP])
    main_rows = [main_row(p_, DA[p_["key"]], act_d) for p_ in main_order]
    open_card = route.get("card")
    st.markdown(U.gloss(main_table(main_rows, slice_text, open_more=bool(open_card) and open_card not in MAIN_TOP and open_card != "total")),
                unsafe_allow_html=True)
    for row_, p_ in zip(main_rows, main_order):
        if p_["key"] not in MAIN_TOP and open_card != p_["key"]:
            continue      # карточки свёрнутых ЖК появляются по клику на строку после «Развернуть»
        st.markdown(f'<div id="card-{p_["key"]}" class="card-anchor"></div>', unsafe_allow_html=True)
        with st.expander(f'{p_["name"]} · нарушен срок передачи {f(row_["overdue"])} кв. · неустойка {pen_shown(row_)} млн ₽',
                         expanded=open_card == p_["key"]):
            project_card_l2(p_, row_, route.get("cell") if open_card == p_["key"] else None)
    st.markdown('<div id="card-total" class="card-anchor"></div>', unsafe_allow_html=True)
    with st.expander(f'Итого · сроки и неустойка по видам', expanded=open_card == "total"):
        if open_card == "total" and route.get("cell") in CELL_TITLES:
            st.markdown(U.gloss(total_cell_panel(main_rows, route["cell"])), unsafe_allow_html=True)
        U.chart(GT.portfolio_figure(GANTT_LIST), key="gantt_portfolio", height=520)
        st.markdown(gantt_causes_portfolio(GANTT_LIST)
                    + '<details class="mx mx-l3"><summary>Неустойка по годам</summary>'
                    + penalty_years(PEN_T["total"], name="итого") + '</details>' + basis_details(), unsafe_allow_html=True)
    st.markdown(
        '<div class="exec-control">'
        f'<span>Неустойка в день <strong>{f(round(tot["risk_day"]))} ₽</strong> · за неделю {sgm(rk_d)}/день · '
        f'начислено <strong>{_mln(PEN_T["total"]["total"])} млн ₽</strong>, в т. ч. 2026 — '
        f'<strong>{_mln(PEN_T["total"]["ddu"][2026] + PEN_T["total"]["remarks"][2026])} млн ₽</strong> · '
        f'сценарий выплат <strong>{fm(LD["expected"])}</strong></span>{N.report_link("money", "Финансы")}</div>',
        unsafe_allow_html=True)
    st.markdown('<nav class="pf-links" aria-label="Открыть раздел из сводки">' + "".join(
        N.report_link(key) for key in ("segments", "dynamics", "decisions", "remarks", "orders", "forecast")
    ) + '</nav>', unsafe_allow_html=True)
    with st.expander("Показатели по всем ЖК и динамика за неделю"):
        st.markdown(f'<div class="slice">Срез на <b>{slice_text}</b> · сравнение с <b>{dd(period_start)}</b> '
                    f'за полные 7 дней по <b>{dd(act_d)}</b></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="note">Просрочка по ДДУ — {fr(tot["overdue_kv"] / max(tot["units_kv"], 1))} всех квартир. '
                    f'Недельная цель по дневной неустойке — {sgm(rk_t)}/день.</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="dev">Из просрочки за неделю вышло <b>{f(tot["left_n"])}</b>, новых просрочек — <b>{f(tot["entered_n"])}</b>. '
                    f'Отстают от цели <b>{lagging} из {len(projects)} ЖК</b>. {N.report_link("dynamics", "Динамика по ЖК")}.</div>', unsafe_allow_html=True)

if view == "decisions":
    week_cards = []
    for measure in package:
        status = "Утвердить" if measure is priority_package else "Принять к сведению"
        measure_control = priority_check_detail if measure is priority_package else ""
        cost_label = "В составе бюджета пакета" if measure is priority_package else "Затраты"
        week_cards.append(
            f'<article class="item"><h3>{html.escape(measure["title"])}</h3><div class="fields">'
            f'<div><span class="label">Группа квартир</span>{html.escape(scope_label(measure))} · {f(measure["eligible"])} квартир'
            f'<span class="subline">{measure_links(measure)}</span></div>'
            f'<div><span class="label">Расчёт, до затрат</span><strong class="amount">−{fm(measure["effect_day"])}/день</strong>'
            f'<span class="subline">к концу 4-й недели · −{fm(measure["scenario_effect"])} за 4 недели к текущему темпу</span></div>'
            f'<div><span class="label">{cost_label}</span>{fm(measure["cost"])}. План за 4 недели — {f(measure["units"])} квартир.</div>'
            f'<div class="approval"><span class="label">{status}</span><strong>{html.escape(measure["owner"])}</strong>'
            f'<span class="subline">Контроль на следующем срезе · {result_text(measure)}. {measure_control}</span></div></div></article>')
    n_direct = 1 if priority_package else 0
    priority_card = "".join(week_cards[:n_direct])
    if not priority_package and priority_measure:
        priority_card = (f'<article class="item"><h3>{html.escape(priority_request)}</h3><div class="fields">'
                         f'<div>{project_link(focus["key"], focus["name"])}</div><div>{priority_effect}</div>'
                         f'<div>{html.escape(priority_owner)}</div><div class="approval">Контроль на следующем срезе · '
                         f'{priority_check}</div></div></article>')
    portal_budget = (f'<article class="item"><h3>{html.escape(budget_title)}</h3><div class="fields">'
                     f'<div>Эффект до затрат {fm(pack_effect)}</div><div>{plan_owner}</div>'
                     f'<div class="approval">Цикл 4 недели, контроль на каждом срезе · {N.report_link("orders", "Было → цель")}</div></div></article>')
    portal_plan = (f'<article class="item"><h3>{plan_title}</h3><div class="fields">'
                   f'<div>{plan_history}</div><div>{plan_owner}</div><div class="approval">Контроль на следующем срезе '
                   f'· {N.report_link("orders", "План по ЖК")}</div></div></article>')
    gd_extra = ""
    for it in GD_ITEMS[2:]:
        d_ = decision_info(projects_by_key[it["card"]]) if it["card"] in projects_by_key else None
        gd_extra += (f'<article class="item"><h3>{html.escape(it["title"])}</h3><div class="fields">'
                     f'<div>{project_link(it["card"], it["scope"])}</div><div>Эффект до затрат −{_mln_s(it["effect"])} млн ₽ за 4 недели</div>'
                     f'<div>{html.escape(it["role"])}</div><div class="approval">Контроль на следующем срезе'
                     + (f' · нарушен срок, кв.: {f(d_["was"])} → {f(d_["target"])}' if d_ else "") + '</div></div></article>')
    st.markdown('<section class="weekly" id="weekly-decisions"><h2>Решения недели по всем ЖК · расчёт до учёта затрат</h2>'
                '<h3>Нужно решение ГД</h3>' + priority_card + portal_budget + gd_extra
                + '<h3>В рабочем порядке</h3>' + portal_plan + "".join(week_cards[n_direct:])
                + f'<div class="intro"><strong>Итого за 4 недели</strong> · снижение {fm(pack_effect)}, затраты {fm(pack_cost)}, '
                f'разница {fm(pack_effect - pack_cost)} расчётного эффекта за вычетом затрат.</div>'
                f'<div class="links">{N.report_link("orders", "Поручения и план по ЖК")}<a href="#decisions">Все меры по ЖК</a></div></section>',
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
    U.section("Приоритет", "Критерий выбора — наибольшее расчётное снижение неустойки за день к концу 4-й недели среди главных мер по ЖК.", anchor="priority")
    if risk_leader["key"] != focus["key"]:
        leader_effect = risk_leader["decisions"][0]["effect_day"] if risk_leader["decisions"] else 0
        st.markdown(f'<div class="note">Наибольшая дневная неустойка — {risk_leader_context}. '
                    f'Расчётное снижение по главной мере этого ЖК — {fm(leader_effect)}/день. '
                    f'У приоритета недели — {fm(priority_measure["effect_day"])}/день.</div>', unsafe_allow_html=True)
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
            f'<div>Весь ЖК: {fm(pri["risk_day"])}/день · {fr(pri["share"])} от итога</div></div></div>'
            f'<div class="pc"><div class="pl">Основная причина</div><div class="pt">{html.escape(pri["cause"])}</div><ul>{drv}</ul></div>'
            f'<div class="pc"><div class="pl">Предлагаемые решения и ожидаемый эффект</div>{decs}</div></div>', unsafe_allow_html=True)

    attention = sorted((p for p in projects if p["risk_delta"] > 0 or p["risk_vs_target"] > 0),
                       key=lambda p: (p["risk_delta"] > 0, p["risk_vs_target"]), reverse=True)
    if attention:
        st.markdown("**ЖК, требующие внимания по недельной динамике**")
        U.fin_table(["ЖК", "Сигнал", "Изменение дневной неустойки", "Отклонение от целевого темпа"],
                    [[p["name"], "Дневная неустойка выросла" if p["risk_delta"] > 0 else "Отставание от целевой динамики",
                      f"{sgm(p['risk_delta'])} в день", f"{sgm(p['risk_vs_target'])} в день"] for p in attention], right=(2, 3))

if view == "segments":
    # ---------------------------------------------------------------- 3. Таблица по ЖК
    U.section("Перечень ЖК", "По убыванию расчётной неустойки за день. Нажмите на ЖК, чтобы открыть его карточку.", anchor="segments")
    srows = PF.screen_rows(projects)
    arrow = lambda d_: "▲" if d_ > 0 else "▼" if d_ < 0 else "•"
    trend_scale = max(v for row in srows for v in row["trend"]) or 1
    trend_dates = projects[0]["weekly"]["Неделя"].tolist()
    seg_dyn, seg_dates = dyn_rows()
    tb = []
    for r_ in srows:
        bad_ = r_["worse"]
        wk_cls = ' class="wr"' if bad_ else ""
        change_cls = " wr" if r_["d_over"] > 0 else " improved" if r_["d_over"] < 0 else ""
        project = projects_by_key[r_["key"]]
        target = max(0, project["overdue_prev"] - project["target_burn"])
        focus_label = '<span class="priority-label">Приоритет недели</span>' if r_["key"] == focus["key"] else ""
        tb.append([
            f'<b>{project_link(r_["key"], r_["name"])}</b>{focus_label}{dyn_html(seg_dyn[r_["key"]], seg_dates)}',
            f'{f(r_["over"])}<span class="sub{change_cls}">{arrow(r_["d_over"])} {sg(r_["d_over"])} за неделю</span>',
            f(r_["ready"]), f(round(r_["risk"])), fr(r_["share"]),
            f(r_["left"]),
            pen_cell(PEN[r_["key"]]), _mln(PEN[r_["key"]]["effect_total"]),
            f'{html.escape(r_["decision"])}<span class="sub">−{fm(r_["dec_day"])} в день · −{fm(r_["dec_4w"])} за 4 недели</span>' if r_["dec_day"] else html.escape(r_["decision"])])
    portfolio_target = max(0, tot["overdue_prev"] - tot["target_burn"])
    tb.append([f'<b>Итого</b>{dyn_html(dyn_rows()[0]["total"], seg_dates)}', f'{f(tot["overdue_kv"])}<span class="sub">{arrow(d_over)} {sg(d_over)} за неделю</span>', f(tot["ready"]), f(round(tot["risk_day"])), "100%",
               f(tot["rem"]["left_cum"]), pen_cell(PEN_T["total"]), _mln(PEN_T["total"]["effect_total"]), ""])
    U.fin_table(["ЖК", "Нарушен срок, кв.", "Готовы", "Неустойка в день", "Доля", "Замечания",
                 "Неустойка", "Мораторий", "Решение"],
                tb, right=(1, 2, 3, 4, 5, 6, 7), total_last=True, cls="pt3", hide=(2, 4, 5, 7, 8),
                tips={1: "Не переданы, срок передачи по ДДУ нарушен, квартир", 2: "Готовы к передаче, квартир", 3: "Расчётная неустойка за просрочку передачи, ₽ в день",
                      4: "Доля от итога неустойки в день", 5: "Остаток замечаний",
                      6: "Неустойка начислена, млн ₽ (ч. 2 ст. 6 и ч. 8 ст. 7 214-ФЗ); нажмите на сумму — по видам",
                      7: "Не начислено по ПП № 326 за 22.03.2024–31.12.2025, млн ₽", 8: "Главное решение и ожидаемый эффект"})
    st.markdown(f'<div class="note">Динамика — мини-график в строке ЖК: общая шкала ЖК 0–{f(trend_scale)} квартир, для итога — собственный масштаб; '
                'красный — отставание от недельной цели или рост просрочки, зелёный — снижение просрочки. '
                'Эффекты мер — расчёт до затрат.</div>', unsafe_allow_html=True)

    with st.expander("Расширенные показатели по ЖК: неустойка, темп и сроки"):
        fall = []
        for p_ in PF.by_risk(projects):
            fc_ = p_["forecast"]
            fall.append([p_["name"], f(p_["overdue_kv"]), f(p_["ready"]), f(round(p_["risk_day"])), f(round(p_["risk_day"] / max(p_["overdue_kv"], 1))), fr(p_["risk_day"] / tr_),
                         f"{sgm(p_['risk_delta'])} при целевом темпе {sgm(p_['risk_target'])}", f"{f(p_['week_fact'])} / {f(p_['week_plan'])} ({sg(p_['week_dev'])})",
                         weeks_text(fc_["base"]["weeks"]), fm(fc_["base"]["accrued"])])
        fall.append(["Итого", f(tot["overdue_kv"]), f(tot["ready"]), f(round(tot["risk_day"])), f(round(tot["risk_day"] / max(tot["overdue_kv"], 1))), "100,0%",
                     f"{sgm(rk_d)} при целевом темпе {sgm(rk_t)}", f"{f(tot['week_fact'])} / {f(tot['week_plan'])} ({sg(tot['week_fact'] - tot['week_plan'])})", "", ""])
        U.fin_table(["ЖК", "Просрочка по ДДУ", "Готовы к передаче", DAILY_PENALTY, "Неустойка на просроченную квартиру, ₽/день", "Доля от итога неустойки в день", "Изменение за неделю к целевому темпу",
                     "Передано за неделю: факт / целевой темп", "Срок закрытия, недель", "Будущая расчётная неустойка до закрытия"], fall, right=range(1, 10), total_last=True)

if view == "reasons":
    # ---------------------------------------------------------------- 4. Причины непередачи готовых квартир
    U.section("Причины непередачи",
              "В каждой строке — количество квартир, их доля среди готовых и расчётная неустойка за день.",
              anchor="reasons")
    reason_scope = st.selectbox("Причины по ЖК", ["Все ЖК"] + names, key="pf_reason_scope")
    reason_data = tot if reason_scope == "Все ЖК" else next(p_ for p_ in projects if p_["name"] == reason_scope)
    if reason_scope != "Все ЖК":
        st.markdown(project_link(reason_data["key"], f"Открыть ЖК «{reason_scope}»"), unsafe_allow_html=True)
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
        U.fin_table(["Причина (квартир · неустойка за день)"] + names + ["Итого"], rows_r, right=range(1, len(projects) + 2))
        capacity_rows = []
        for p_ in projects + [tot]:
            required = ceil(p_["ready"] / DC.MONTH_W)
            capacity_rows.append([p_.get("name", "Итого"), f(p_["week_fact"]), f(p_["capacity"]), f(required),
                                  f(max(0, required - p_["capacity"]))])
        U.fin_table(["ЖК", "Передано за последнюю неделю", "Максимум за 8 недель", "Нужно в неделю для передачи за 4 недели",
                     "Не хватает передач в неделю к максимуму"], capacity_rows, right=range(1, 5), total_last=True)
        st.caption("Каждая квартира учтена в одной группе. Запись позже семи дней показывает дату визита. "
                   "Доступность более ранних слотов проверяется отдельно.")

if view == "forecast":
    # ---------------------------------------------------------------- 5. Прогноз и целевой темп
    U.section("Прогноз", "Текущий чистый темп, целевой темп по истории и сценарий ускоренной передачи готовых квартир", anchor="forecast")
    rw = st.radio("Срок передачи всех готовых квартир, недель", [2, 4, 8], index=1, horizontal=True, key="pf_ready_w")
    rw_w = C.plural(rw, "неделю", "недели", "недель")
    PFC = DC.portfolio_forecast(projects, rw)
    frows = []
    for p_ in projects:
        fc_ = DC.forecast(p_, rw)
        frows.append([p_["name"], f(p_["overdue_kv"]), pace_text(p_["burn_pace"]), weeks_text(fc_["base"]["weeks"]), weeks_text(fc_["target"]["weeks"]),
                      (fm(fc_["base"]["accrued"]), RS), weeks_text(fc_["scn"]["weeks"]), fm(fc_["saving"])])
    frows.append(["Итого", f(tot["overdue_kv"]), pace_text(tot["burn_pace"]), weeks_text(PFC["base"]["weeks"]), weeks_text(PFC["target"]["weeks"]),
                  (fm(PFC["base"]["accrued"]), RS), weeks_text(PFC["scn"]["weeks"]), fm(PFC["saving"])])
    U.fin_table(["ЖК", "Просрочка на дату среза", "Чистый темп, квартир в неделю", "Срок закрытия, недель (текущий темп)", "При целевом темпе, недель",
                 "Будущая расчётная неустойка до закрытия", f"Срок закрытия при передаче всех готовых за {rw} {rw_w}", "Снижение расчётной неустойки за весь прогноз"], frows, right=range(1, 8), total_last=True)
    cut_ = min(max(len(PFC["base"]["path"]), len(PFC["scn"]["path"]), len(PFC["target"]["path"])), 60)
    fg = go.Figure()
    for key_, lab_, col_, dash_ in (("base", "Текущий темп", U.NAVY, "solid"), ("target", "Целевой темп", U.GRAPH, "dash"), ("scn", f"Все готовые за {rw} {rw_w}", U.GOOD, "solid")):
        pth = PFC[key_]["path"][:cut_]
        fg.add_scatter(x=[x_[0] for x_ in pth], y=[x_[2] / 1e6 for x_ in pth], mode="lines", name=lab_, line=dict(color=col_, width=2.5, dash=dash_))
    fg.add_scatter(x=list(range(DC.MONTH_W+1)),
                   y=[0] + [sum(row["base"]-row["effect"] for row in package_path if row["week"] == w)/1e6
                            for w in range(1, DC.MONTH_W+1)],
                   mode="lines+markers", name="Текущий темп с пакетом мер", line=dict(color="#825900", width=2.5))
    fg.update_layout(title="Будущая расчётная неустойка с даты среза нарастающим итогом, млн ₽", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.18), hovermode="x unified")
    fg.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
    fg.update_xaxes(title_text="недель от даты среза")
    with st.expander("График накопленной неустойки"):
        U.chart(fg, key="pf_fc_chart", height=320)
    closed_base, closed_scenario = PFC["base"]["weeks"], PFC["scn"]["weeks"]
    weeks_saved = weeks_text(closed_base - closed_scenario) if closed_base is not None and closed_scenario is not None else "—"
    st.markdown(f'<div class="note">При передаче всех готовых квартир за {rw} {rw_w} сокращение срока закрытия просрочки по всем ЖК, недель: {weeks_saved}; '
                f'будущая расчётная неустойка снижается на ≈{fm(PFC["saving"])} (за первые 4 недели — на {fm(PFC["saving_4w"])}). Чистый темп — среднее число квартир, вышедших из просрочки, за вычетом новых просрочек за последние 4 недели. '
                'Целевой темп — неотрицательный средний темп за предыдущие четыре недели с запасом 10%. В сценарии новые просрочки вычитаются из числа передач. Вариант с готовыми задаёт минимум общего темпа передач. Эффект пакета рассчитан от текущего темпа и включает отдельные меры по квартирам с препятствиями.</div>', unsafe_allow_html=True)

if view == "decisions":
    # ---------------------------------------------------------------- 6. Управленческие решения и ожидаемый эффект
    U.section("Решения по ЖК", "Рекомендации по ЖК · расчёт до учёта затрат. Итог этого раздела относится к главным мерам по ЖК. Бюджет пакета недели показан в блоке «Решения недели» и разделе «Поручения».", anchor="decisions")
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
                'Контроль исполнения пакета — на каждом срезе, см. «Поручения».</div>', unsafe_allow_html=True)

if view == "contribution":
    # ---------------------------------------------------------------- 3. Вклад сегментов в риск
    U.section("Концентрация неустойки", "Вклад каждого ЖК в расчётную неустойку за день по всем ЖК", anchor="contribution")
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
    st.markdown(f'<div class="note">Расчёт с {dd(pf_demo.ACCRUAL_START)} по {slice_text}: {fm(tot["accrued_up"])} по всем ЖК. '
                'Сумма включает начисления по просроченным квартирам до даты передачи или среза. Выплаты в сценарии приняты равными нулю. '
                'Доля первых ЖК — сумма долей строк сверху до текущего ЖК включительно.</div>', unsafe_allow_html=True)
    hhi = sum((p["risk_day"] / tr_) ** 2 for p in projects) * 10000
    big = srt[0]
    st.markdown(f'<div class="note">Наибольшая доля — у ЖК «{big["name"]}»: {fr(big["risk_day"] / tr_)} дневной неустойки. Индекс концентрации (HHI, 0–10 000): <b>{f(hhi)}</b> — '
                f'{"высокая концентрация" if hhi > 2500 else "умеренная концентрация"}.</div>', unsafe_allow_html=True)

if view == "dynamics":
    # ---------------------------------------------------------------- 4. Динамика
    U.section("Динамика за неделю", f"Изменение с {dd(period_start)} по {dd(act_d)}. Красный — рост просрочки, зелёный — снижение.", anchor="dynamics")
    v1, v2 = st.columns([1, 1.4], gap="large")
    with v1:
        wf = go.Figure(go.Waterfall(
            x=[p["name"] for p in projects] + ["Итого"], measure=["relative"] * len(projects) + ["total"],
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
            rv.append([project_link(p["key"], p["name"], "dynamics") if "key" in p else p["name"], f(p["overdue_week_current"]), f(prev_o), sg(p["overdue_delta"]),
                       f(p["week_fact"]), sg(dwk) if dwk is not None else PF.DASH, sgm(p["risk_delta"]),
                       sgm(p["risk_target"]), (sgm(p["risk_delta"] - p["risk_target"]), f"color:{tone};font-weight:600")])
        U.fin_table(["ЖК", f"Просрочка на {dd(act_d)}", f"Просрочка на {dd(period_start)}", "Изменение просрочки",
                     "Передано за 7 дней", "Δ передач к предыдущей неделе", "Изменение неустойки, ₽/день",
                     "Цель на неделю, ₽/день", "Отклонение от цели, ₽/день"], rv, right=range(1, 9), total_last=True)
    with st.expander("Передачи квартир по подписанным актам (ПА)"):
        pa_rows = []
        for project in [*projects, dict(tot, name="Итого")]:
            bilateral = project["week_pa_bilateral"]
            unilateral = project["week_pa_unilateral"]
            unclassified = project["week_fact"] - bilateral - unilateral
            pa_rows.append([project_link(project["key"], project["name"], "dynamics") if "key" in project else project["name"], f(bilateral), f(unilateral), f(unclassified),
                            f(project["week_fact"]), f(project["left_n"])])
        if all(row[3] == "0" for row in pa_rows):
            pa_rows = [row[:3] + row[4:] for row in pa_rows]
            pa_headers = ["ЖК", "Двусторонние ПА", "Односторонние ПА", "Всего квартир по ПА", "Передано из просрочки на начало недели"]
        else:
            pa_headers = ["ЖК", "Двусторонние ПА", "Односторонние ПА", "Тип ПА не указан", "Всего квартир по ПА", "Передано из просрочки на начало недели"]
        U.fin_table(pa_headers, pa_rows, right=range(1, len(pa_headers)), total_last=True)
        st.caption(f"Даты ПА с {dd(period_start + pd.Timedelta(days=1))} по {dd(act_d)} включительно. "
                   "Одна квартира учитывается один раз. В последней колонке — квартиры, у которых срок передачи уже был нарушен на начало недели.")
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

if view == "matrix":
    # ---------------------------------------------------------------- 6. Матрица рисков
    U.section("Причины и неустойка", "Сравнение причин просрочки по ЖК", anchor="matrix")
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

if view == "remarks":
    # ---------------------------------------------------------------- 10. Замечания портфеля
    RM = tot["rem"]
    U.section("Замечания", "Открытые и просроченные замечания на дату среза", anchor="remarks")
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
        sel_q = st.selectbox("Динамика замечаний по кварталам", ["Все ЖК"] + names, key="pf_qsel")
        Q = RM["quarters"] if sel_q == "Все ЖК" else next(p_ for p_ in projects if p_["name"] == sel_q)["rem"]["quarters"]
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
            t1 = [[project_link(p_["key"], p_["name"], "remarks")] + rr(p_["rem"]) for p_ in ranked_] + [["Итого"] + rr(RM)]
            U.fin_table(["ЖК", "Всего замечаний", "Устранено", "Отменено", "Приостановлено", "Остаток к устранению", "Остаток нарастающим итогом", "Доля устранённых", "Доля отменённых",
                         "Средний срок устранения, дней", "Доля просроченных"], t1, right=range(1, 11), total_last=True, hide=(2, 3, 4, 7, 8))
            kr = lambda r_: [f(r_["flats_with"]), f(r_["flats_fixed_any"]), f(r_["flats_all_fixed"]), f(r_["flats_unfixed"]), f(r_["flats_one_unfixed"]), f(r_["flats_total"])]
            t2 = [[p_["name"]] + kr(p_["rem"]) + [fm(p_["risk_blocked"]), fr(p_["risk_blocked"] / p_["risk_day"]) if p_["risk_day"] else PF.DASH] for p_ in ranked_] + \
                 [["Итого"] + kr(RM) + [fm(blocked), fr(blocked / tr_)]]
            U.fin_table(["ЖК", "Квартир с замечаниями", "С хотя бы одним устранённым", "Все замечания устранены", "С неустранёнными", "С одним неустранённым замечанием", "Всего квартир", "Неустойка по квартирам с замечаниями, ₽/день", "Доля в дневной неустойке ЖК"],
                        t2, right=range(1, 9), total_last=True, hide=(2, 3, 5, 6))

if view == "money":
    # ---------------------------------------------------------------- 8. Деньги по всем ЖК
    U.section("Финансы", anchor="money")
    st.markdown('<nav class="pf-links" aria-label="Расчёты по всем ЖК">'
                + N.report_link("contribution") + N.report_link("forecast") + '</nav>', unsafe_allow_html=True)
    U.kpi_cards([
        dict(label="Накопленная неустойка (верхняя оценка)", value=fm(tot["accrued_up"]), delta=("", "flat"),
             foot=f"расчёт с {dd(pf_demo.ACCRUAL_START)} по {slice_text} · нижняя оценка {fm(tot['accrued_lo'])}"),
        dict(label="Расчёт стоимости устранения замечаний", value=fm(tot["remarks_cost"]), delta=("", "flat"), foot=f"{f(tot['remarks'])} замечаний"),
    ])
    U.fin_table(["ЖК", DAILY_PENALTY, "Накопленная неустойка, верхняя оценка", "Накопленная неустойка, нижняя оценка", "Стоимость устранения замечаний", "Потенциал претензий"],
                [[project_link(x["key"], x["name"], "money"), f(round(x["risk_day"])), fm(x["accrued_up"]), fm(x["accrued_lo"]), fm(x["remarks_cost"]), fm(x["claim_potential"])]
                 for x in projects] + [["Итого", f(round(tot["risk_day"])), fm(tot["accrued_up"]), fm(tot["accrued_lo"]), fm(tot["remarks_cost"]), fm(tot["claim_potential"])]], right=range(1, 6), total_last=True)
    with st.expander("Сценарий будущих выплат по ЖК"):
        st.caption(f"Допущения сценария. Возможные требования составляют {C.fmt_pct(K['claim'])} верхней оценки неустойки. "
                   f"Ожидаемые выплаты рассчитаны с учётом снижения требований на {C.fmt_pct(K['cut'])}.")
        payout_rows = [[project_link(p_["key"], p_["name"], "money"), fm(p_["ladder"]["claimed"]), fm(p_["ladder"]["expected"])] for p_ in projects]
        payout_rows.append(["Итого", fm(LD["claimed"]), fm(LD["expected"])])
        U.fin_table(["ЖК", "Возможные требования по сценарию", "Ожидаемые выплаты по сценарию"], payout_rows, right=(1, 2), total_last=True)
    st.markdown(f"**Сценарий накопленной неустойки через 4 недели**")
    baseline_accrual = tot["accrued_up"] + pack_future_base
    freeze_accrual = tot["accrued_up"] + tot["risk_day"] * DC.MONTH_W * 7
    U.fin_table(["Условия сценария", "Верхняя оценка на дату, ₽"], [
        ["Текущий чистый темп", fm(baseline_accrual)],
        ["Текущий темп с пакетом мер", fm(baseline_accrual - pack_effect)],
        ["Снижение к текущему темпу, до затрат", fm(pack_effect)],
        ["Заморозка объёма на дату среза", fm(freeze_accrual)],
    ], right=(1,))
    st.caption("Сценарий выплат считается отдельно. Текущий темп включает исторический приток. Эффект пакета нарастает по неделям и ограничен остатком неустойки каждого ЖК. Заморозка сохраняет объём на дату среза.")

if view == "orders":
    # ---------------------------------------------------------------- 9. Поручения
    U.section("Поручения", "Контроль — на следующем срезе по показателю «было → цель». Плановые показатели за новый цикл начинаются с нуля.", anchor="orders")
    order_head = ["Действие", "Поручение и ЖК", "Ответственный", "Контроль", "Было → цель", "Расчёт за 4 недели", "Затраты за 4 недели"]
    def order_row(measure, requires_approval):
        instruction = priority_request if requires_approval else measure["title"]
        scope = f'<span>{html.escape(instruction)}<br>{measure_links(measure)}</span>'
        check = f'{result_text(measure)}. {priority_check_detail}' if requires_approval else result_text(measure)
        cost = f'{f(measure["cost"])} ₽ в составе пакета' if requires_approval else fm(measure["cost"])
        return ["Утвердить" if requires_approval else "Принять к сведению", scope, measure["owner"], "Следующий срез",
                check, f"−{fm(measure['scenario_effect'])}", cost]

    st.markdown("**Нужно решение ГД**")
    approval_rows = [order_row(priority_package, True)] if priority_package else []
    if not priority_package and priority_measure:
        approval_rows.append(["Утвердить", f'{html.escape(priority_request)}<br>{project_link(focus["key"], focus["name"])}',
                              priority_owner, "Следующий срез", "Проверка применимости 0 → 1", "Вне пакета", "Без отдельного бюджета"])
    approval_rows.append(["Утвердить", budget_title, plan_owner, "Каждый срез, 4 недели",
                          f"Охват 0 → {f(pack_units)} квартир. Исполнение — на каждом срезе",
                          f"−{fm(pack_effect)}", f"{f(pack_cost)} ₽"])
    for it in GD_ITEMS[2:]:          # главные решения ЖК из полосы «Нужно решение ГД» на сводке
        d_ = decision_info(projects_by_key[it["card"]]) if it["card"] in projects_by_key else None
        was_t = f'Нарушен срок, кв.: {f(d_["was"])} → {f(d_["target"])}' if d_ else "—"
        approval_rows.append(["Утвердить", f'<span>{html.escape(it["title"])}<br>{project_link(it["card"], it["scope"])}</span>', it["role"],
                              "Следующий срез", was_t, f'−{_mln_s(it["effect"])} млн ₽', "Без отдельного бюджета"])
    U.fin_table(order_head, approval_rows, right=(5, 6))
    st.markdown("**В рабочем порядке**")
    operation_rows = [["Выполнить", plan_title, plan_owner, "Следующий срез", plan_history, "Отдельно от бюджета", "—"]]
    operation_rows.extend(order_row(measure, False) for measure in package if measure is not priority_package)
    U.fin_table(order_head, operation_rows, right=(5, 6))
    st.markdown("**Недельный план передач по квартирам с нарушенным сроком · контроль на следующем срезе**")
    st.markdown(plan_readiness, unsafe_allow_html=True)
    plan_rows = [[project_link(row["project"]["key"], row["project"]["name"]), f(row["baseline"]),
                  f(row["booked"]), f(row["reserve"]), f(row["total"]), f(row["new"]),
                  f(row["closing_base"]), f(row["closing"]), fm(row["risk_base"]), fm(row["risk_total"])]
                 for row in plan]
    plan_rows.append(["Итого", f(tot["overdue_kv"]), f(plan_ready), f(plan_pending), f(plan_total), f(plan_new),
                      f(plan_base), f(plan_closing), fm(plan_risk_base), fm(plan_risk)])
    U.fin_table(["ЖК", "Было с нарушенным сроком", "База с записью", "Резерв после проверки", "С резервом", "Новые просрочки",
                 "Остаток, база", "Остаток с резервом", "База, ₽/день", "С резервом, ₽/день"],
                plan_rows, right=range(1, 10), total_last=True)
    st.caption(f"База: {f(tot['overdue_kv'])} − {f(plan_ready)} + {f(plan_new)} = {f(plan_base)} квартир. "
               f"С резервом: {f(tot['overdue_kv'])} − {f(plan_total)} + {f(plan_new)} = {f(plan_closing)} квартир. "
               "Запись на приёмку не гарантирует передачу. Резерв зависит от выполнения мер и проверки условий.")
    st.markdown("**Недельные вехи пакета**")
    U.fin_table(["Контроль", "Будущая неустойка при текущем темпе, нарастающим итогом",
                 "С пакетом, нарастающим итогом", "Эффект до затрат"],
                [[f"Срез, неделя {week}",
                  fm(sum(row["base"] for row in package_path if row["week"] == week)),
                  fm(sum(row["base"]-row["effect"] for row in package_path if row["week"] == week)),
                  fm(sum(row["effect"] for row in package_path if row["week"] == week))]
                 for week in range(1, DC.MONTH_W+1)], right=(1, 2, 3))

if view == "notes":
    # ---------------------------------------------------------------- 10. Допущения
    U.section("Методология", "", anchor="notes")
    U.sources(
        "<b>Расчётная неустойка за день.</b> Отчёт суммирует оценки по непереданным квартирам с просрочкой по ДДУ. "
        "Дневная сумма = расчётная ставка в процентах / 100 / 150 × расчётная цена квартиры. "
        "Цены квартир по ДДУ приняты допущением: "
        + ", ".join(f"{DA[key]['name']} — {pr_in[key]:.1f} млн ₽".replace(".", ",") for key in project_keys)
        + "; значения меняются в боковой панели, неустойка пересчитывается пропорционально. Коммерческие помещения не включены; машиноместа и кладовые учитываются отдельно по расчётным ценам. "
        "<br><b>Передаточные акты (ПА).</b> Модель использует структуру реестра: проект, объект недвижимости, дата ПА и признак одностороннего акта. "
        "Динамика строится по дате ПА. Считаются только квартиры, по одному акту на объект. "
        "Двусторонние и односторонние акты учитываются раздельно. Все строки реестра сформированы синтетически. "
        f"<br><b>Накопленная неустойка.</b> За дни просрочки с {dd(pf_demo.ACCRUAL_START)} по {slice_text}; для переданных квартир расчёт заканчивается датой передачи. "
        "Верхняя оценка — дневная сумма × дни, нижняя — 75% верхней. Выплаты приняты равными нулю. "
        "<br><b>Неустойка по годам (сводка «Отчёт по заселению»).</b> За просрочку передачи по ДДУ 2026 год равен накопленной неустойке "
        "по квартирам среза (верхняя оценка, начисление с 01.01.2026). 2024–2025 годы — ранее переданные очереди ЖК, уровень "
        "к 2026 году задан профилем ЖК; ставка на срок исполнения — 16%, с 01.07.2023 по 21.03.2024 — не выше 7,5% (п. 2 ПП № 326). "
        "С 22.03.2024 по 31.12.2025 неустойка не начисляется (п. 1 ПП № 326 в ред. ПП № 1916, № 925); сумма за этот период показана "
        "как «Не начислено в период моратория» — по тем же ставкам, без ограничения 7,5%. За замечания — от расчётной стоимости "
        f"устранения недостатков по квартире ({f(PN.CLAIM_BASE_PER_FLAT)} ₽) за дни сверх регламентного срока {PN.REMARK_LIMIT_DAYS} дней: "
        "до 01.09.2024 — 1% в день, далее 1/150 ключевой ставки Банка России, не более стоимости устранения (ч. 8 ст. 7 214-ФЗ "
        "в ред. 266-ФЗ) и в пределах 3% цены договора (ч. 4 ст. 10, 482-ФЗ). Доля ЖК — вклад в начисленную сумму по всем ЖК за три года. "
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
        ["ПА базового среза", f"Односторонний акт присваивается каждому {pf_demo.UNILATERAL_ACT_INTERVAL}-му номеру объекта со сдвигом по ЖК при наличии даты ПА."],
        ["ПА за 14–20 ноября", f"Синтетические акты по готовым квартирам. По Бунинским добавлены {pf_demo.BK_WEEK_UNILATERAL} односторонних акта с истёкшим сроком вызова. Остальные акты за неделю двусторонние. Часть несостоявшихся приёмок перенесена на новые даты."],
        ["Даты", f"Срез {slice_text}; сравнение с {dd(period_start)}; контроль на следующем срезе; горизонт мер 4 недели."],
        ["Бунинские кварталы", f"{pf_demo.BK_EXPIRED_POOL} квартир с истёкшим сроком вызова в базовом срезе; дополнение к первоначальной группе — из готовых без записи и вызова. Возраст уведомлений в добавленной группе — {pf_demo.BK_NOTICE_AGE} дней. Цель = группа × {C.fmt_pct(DC.UNILATERAL_SHARE)}, с округлением."],
        ["Охват остальных мер", f"Ранние слоты {C.fmt_pct(DC.SLOT_SHARE)}, повторная приёмка {C.fmt_pct(DC.REFUSAL_RESOLVED)}, устранение замечаний {C.fmt_pct(DC.REMARKS_HANDOVER_SHARE)}, обзвон {C.fmt_pct(DC.CALL_RESPONSE)}. Целое число округляется по ЖК."],
        ["Цели", "На неделю — четверть планового результата меры с округлением вверх по мере. Остаток просрочки = текущий остаток − план передач + новый приток."],
        ["План передач", "Расчётная мощность по ЖК = среднее за 4 недели число передач из просрочки × 1,10 с округлением. База — готовые с записью в ближайшие 7 дней. Остаток мощности занимает резерв по мерам. Дневная оценка = сумма на срезе + риск новых просрочек − ожидаемое снижение по средним ставкам групп."],
        ["Затраты на одну квартиру", ", ".join(f'{measure["title"].lower()} — {fm(DC.PACKAGE_RATES[measure["key"]])}' for measure in package)],
        ["Эффект мер", "Потенциал = квартиры меры × средняя дневная неустойка группы. В сценарии пакет нарастает линейно и ограничивается остатком каждого ЖК при текущем темпе. Недельный эффект = полусумма дневных снижений на границах недели × 7, максимум — расчётная неустойка ЖК за неделю. Затраты = план квартир × тариф."],
    ])
    with st.expander("Сверка расчётов и мер"):
        U.fin_table(["Показатель", "Расчёт в рублях или квартирах"], [
            ["Остаток просрочки", f"{f(tot['overdue_prev'])} − {f(tot['left_n'])} + {f(tot['entered_n'])} = {f(tot['overdue_kv'])}"],
            ["Передачи по ПА за неделю", f"{f(tot['week_pa_bilateral'])} двусторонних + {f(tot['week_pa_unilateral'])} односторонних "
             + (f"+ {f(tot['week_fact'] - tot['week_pa_bilateral'] - tot['week_pa_unilateral'])} без типа " if tot['week_fact'] != tot['week_pa_bilateral'] + tot['week_pa_unilateral'] else "")
             + f"= {f(tot['week_fact'])} квартир. Из просрочки на начало недели передано {f(tot['left_n'])}."],
            ["Готовы к передаче", f"{f(sum(reason['n'] for reason in RSN.values()))} = {f(tot['ready'])}"],
            ["Расчётная неустойка за день", f"{f(tot['risk_prev'])} − {f(tot['left_risk'])} + {f(tot['entered_risk'])} = {f(tot['risk_day'])} ₽/день"],
            ["Доли неустойки", f"{fr(sum(project['risk_day'] / tr_ for project in projects))} по исходным суммам; на экране доли округляются."],
            ["Накоплено", f"{f(sum(project['accrued_up'] for project in projects))} ₽, с {dd(pf_demo.ACCRUAL_START)} по {slice_text}"],
            ["Пакет", f"{f(pack_future_base)} − {f(pack_future_base-pack_effect)} = {f(pack_effect)} ₽; "
                        f"{f(pack_effect)} − {f(pack_cost)} = {f(pack_effect-pack_cost)} ₽ после затрат."],
            ["План 27.11", f"{f(tot['overdue_kv'])} − ({f(plan_ready)} + {f(plan_pending)}) + {f(plan_new)} = {f(plan_closing)} квартир с резервом."],
        ])
        U.fin_table(["Мера", "ЖК", "Группа, квартир", "Цель за 4 недели", "Среднее, ₽/день", "Снижение на 4-й неделе, ₽/день"],
                    [[measure["title"], project_link(item["project"]["key"], item["project"]["name"]),
                      f(item["eligible"]), f(item["units"]), f(item["average"]), f(item["effect_day"])]
                     for measure in package for item in measure["items"]], right=(2, 3, 4, 5))
