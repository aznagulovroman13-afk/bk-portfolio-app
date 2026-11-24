"""«Версия 2» отчёта по заселению: светлый минималистичный интерфейс поверх тех же данных и расчётов.

Только оформление и порядок показа: все цифры приходят из app.py (projects, totals, main_rows) без пересчёта.
Подключается только при view=portfolio2 / ver=2; версии 1 и 3 этот модуль не используют.
"""
from html import escape

import threading

UX2_SCHEMA = "l4"
_state = threading.local()      # прогон Streamlit — свой поток: флаг версии 2 не влияет на другие сессии

# Палитра версии 2 (контраст текста на белом и на #F5F5F7 ≥ 4.5:1 — проверяется в тестах).
INK, INK2, MUTED, RISK, GOOD, LINK, ZERO = "#1D1D1F", "#424245", "#6B6B70", "#B42318", "#1F6E35", "#0060C0", "#6B6B70"
BG, PAPER = "#F5F5F7", "#FFFFFF"
EMPTY_NOTE = "За период нет записей"


def set_active(on: bool) -> None:
    _state.on = bool(on)


def active() -> bool:
    return getattr(_state, "on", False)

CSS = '''<style>
:root{--navy:#1D1D1F;--ink:#1D1D1F;--ink2:#515154;--ink3:#6B6B70;--line:#E3E3E8;--paper:#fff;--bg:#F5F5F7;--gold:#1D1D1F;--risk:#B42318;
  --sh1:none;--hov:#F5F5F7;--row:#EDEDF0;color-scheme:light}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:#F5F5F7!important;color:#1D1D1F!important}
html,body,.stApp,button,input,textarea,select{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Segoe UI",Roboto,Helvetica,Arial,sans-serif!important}
.stMainBlockContainer,.block-container{max-width:1280px!important;margin:0 auto!important;padding-top:24px!important}
/* верхняя полоса — светлая, полупрозрачная */
.pfnav{background:rgba(251,251,253,.86)!important;-webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid #E3E3E8}
.pfnav b{color:#1D1D1F!important}
.pfnav a[data-pf-route]{color:#424245!important}
.pfnav a[data-pf-route]:hover,.pfnav a[aria-current="page"][data-pf-route]{color:#1D1D1F!important}
.pfnav .pf-ver a[aria-current="page"][data-pf-route]{color:#fff!important}
.pfnav a,.pfnav summary{color:#424245!important;border-radius:8px!important}
.pfnav a:hover,.pfnav summary:hover,.pfnav [aria-current="page"],.pfnav .more:has([aria-current="page"])>summary{color:#1D1D1F!important;background:#E8E8ED!important}
.pfnav :focus-visible{outline:2px solid #0060C0!important}
.pfnav .more-links{background:#fff!important;border:1px solid #E3E3E8;box-shadow:0 12px 32px rgba(0,0,0,.12)!important;border-radius:12px!important}
.pf-ver{border:1px solid #D2D2D7!important;border-radius:9px!important;background:#fff}
.pfnav .pf-ver a{color:#424245!important;border-radius:0!important}
.pfnav .pf-ver a[aria-current="page"]{background:#1D1D1F!important;color:#fff!important}
header [data-testid="stExpandSidebarButton"]{color:#424245!important}
/* шапка */
.rh.exec-header{background:transparent!important;border:0!important;box-shadow:none!important;border-radius:0!important;padding:8px 0 4px!important;margin:0 0 8px!important}
.rh.exec-header .ttl{font-size:clamp(28px,3.4vw,44px)!important;font-weight:700;color:#1D1D1F!important;letter-spacing:-.035em;margin:2px 0 0!important}
.rh.exec-header .kick{color:#6B6B70!important;text-transform:none!important;letter-spacing:0!important;font-size:14px!important;font-weight:500}
.rh:not(.exec-header){background:#fff!important;color:#1D1D1F!important;border:1px solid #E3E3E8!important;border-bottom:1px solid #E3E3E8!important;box-shadow:none!important}
.rh:not(.exec-header) .ttl,.rh:not(.exec-header) .meta b{color:#1D1D1F!important}
.rh:not(.exec-header) .kick,.rh:not(.exec-header) .meta{color:#6B6B70!important}
/* общие поверхности остальных разделов */
.kcard,.exec-project,.exec-metric,.card,.concl,.dev,.dec,.cell-panel,.gantt-l1,.tw,.prio,.mt-total{border-radius:16px!important;box-shadow:none!important}
.mt-total{border-left:1px solid #E3E3E8!important}
.fin{border-radius:12px;overflow:hidden;border-color:#E3E3E8!important}
.fin th{background:#FAFAFC!important;color:#6B6B70!important;border-bottom:1px solid #E3E3E8!important;text-transform:none!important;letter-spacing:0!important;font-size:12px!important}
.fin tr.tot td{background:#FAFAFC!important;border-top:1px solid #D2D2D7!important}
.pf-links a{border-radius:980px!important;border-color:#D2D2D7!important;background:#fff!important;color:#1D1D1F!important}
.pf-links a[aria-current="page"]{background:#1D1D1F!important;border-color:#1D1D1F!important;color:#fff!important}
.pf-role{border-radius:980px!important;background:#F5F5F7!important;border-color:#E3E3E8!important;color:#1D1D1F!important}
div[data-testid="stPlotlyChart"],div[data-testid="stDataFrame"]{border-radius:16px!important;border-color:#E3E3E8!important}
[data-testid="stExpander"] details{border-radius:16px!important;background:#fff!important;border:1px solid #E3E3E8!important}
[data-testid="stExpander"] summary{padding-top:14px;padding-bottom:14px}
[data-testid="stExpander"] summary p{font-weight:600;color:#1D1D1F}
/* обзор версии 2 */
.v2-overview{display:grid;gap:16px;margin:0 0 22px;color:#1D1D1F}
.v2-overview *{box-sizing:border-box}
.v2-label{display:block;color:#6B6B70;font-size:13px;font-weight:500;line-height:1.4}
.v2-eyebrow{display:block;color:#B42318;font-size:13px;font-weight:600;letter-spacing:.01em}
.v2-hero,.v2-kpi,.v2-risklist{background:#fff;border:1px solid #E3E3E8;border-radius:20px}
.v2-first{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:12px}
.v2-first .v2-kpis{grid-column:1 / -1}
.v2-hero{padding:28px 32px;min-width:0}
.v2-hero h2{font-size:clamp(22px,2.2vw,28px)!important;font-weight:700!important;letter-spacing:-.025em;margin:6px 0 2px!important;padding:0!important;color:#1D1D1F!important;line-height:1.2!important}
.v2-number{display:block;font-size:clamp(34px,4.6vw,56px);font-weight:700;letter-spacing:-.045em;line-height:1.05;color:#B42318;font-variant-numeric:tabular-nums;margin:10px 0 6px}
.v2-number small{font-size:.42em;font-weight:600;letter-spacing:-.01em;color:#6B6B70;margin-left:4px}
.v2-hero p{color:#515154;font-size:14px;line-height:1.5;margin:4px 0!important}
.v2-action{display:grid;gap:12px;align-content:start}
.v2-action .v2-what{display:block;font-size:19px;font-weight:650;line-height:1.3;letter-spacing:-.015em;color:#1D1D1F}
.v2-facts{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
.v2-fact b{display:block;font-size:15px;font-weight:600;color:#1D1D1F;margin-top:3px;line-height:1.35}
.v2-fact .v2-effect{font-size:24px;font-weight:700;color:#1F6E35;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.v2-fact span.v2-sub{display:block;font-size:12px;color:#6B6B70;margin-top:2px}
.v2-cta{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:12px}
.v2-overview a{color:#0060C0!important;text-decoration:none!important}
.v2-overview a:hover{text-decoration:underline!important;text-underline-offset:3px}
.v2-overview a:focus-visible{outline:2px solid #0060C0;outline-offset:3px;border-radius:4px}
.v2-cta a{font-size:15px;font-weight:500}
.v2-cta a::after,.v2-go::after{content:"\\00a0›"}
.v2-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.v2-kpi{min-width:0;padding:18px 20px}
.v2-kpi strong{display:block;font-size:clamp(26px,2.6vw,36px);font-weight:700;letter-spacing:-.035em;line-height:1.15;font-variant-numeric:tabular-nums;margin:8px 0 2px}
.v2-kpi strong small{font-size:.5em;font-weight:600;color:#6B6B70;margin-left:3px;letter-spacing:0}
.v2-kpi a{color:#1D1D1F!important}
.v2-kpi.v2-critical strong,.v2-kpi.v2-critical strong a{color:#B42318!important}
.v2-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-top:10px}
.v2-title{font-size:22px!important;font-weight:700!important;letter-spacing:-.02em;margin:0!important;padding:0!important;color:#1D1D1F!important}
.v2-path{display:flex;flex-wrap:wrap;gap:4px 6px;font-size:12px;color:#6B6B70;list-style:none;margin:0;padding:0}
.v2-path li+li::before{content:"›";margin-right:6px;color:#6B6B70}
.v2-path li:first-child{color:#1D1D1F;font-weight:600}
.v2-risklist{padding:4px 24px}
.v2-row{display:grid;grid-template-columns:28px minmax(0,1.3fr) minmax(0,1fr) minmax(120px,.6fr);align-items:center;gap:16px;padding:14px 0;border-bottom:1px solid #EDEDF0}
.v2-row:last-child{border-bottom:0}
.v2-rank{font-size:13px;font-weight:600;color:#6B6B70;font-variant-numeric:tabular-nums}
.v2-name a{font-weight:600;font-size:16px;color:#1D1D1F!important;overflow-wrap:anywhere}
.v2-detail,.v2-share{font-size:12px;color:#6B6B70;display:block;margin-top:3px}
.v2-detail a.v2-go{color:#0060C0!important;font-size:12px;font-weight:500}
.v2-track{height:6px;background:#EDEDF0;border-radius:6px;overflow:hidden}
.v2-fill{display:block;height:6px;background:#8E8E93;border-radius:6px}
.v2-row.v2-top .v2-fill{background:#B42318}
.v2-amount{font-size:17px;font-weight:650;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.v2-row.v2-top .v2-amount{color:#B42318}
.v2-foot{font-size:12px;color:#6B6B70;line-height:1.5}
@media(max-width:900px){.v2-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.v2-hero{grid-template-columns:1fr;gap:18px;padding:22px}
  .v2-first{grid-template-columns:1fr}.v2-first .v2-action{order:3}}
@media(max-width:640px){.stMainBlockContainer,.block-container{padding-left:14px!important;padding-right:14px!important}
  .v2-row{grid-template-columns:22px minmax(0,1fr) auto;gap:6px 10px;padding:12px 0}
  .v2-bar{grid-row:2;grid-column:2 / -1}.v2-row .v2-amount{grid-row:1;grid-column:3;font-size:15px}
  .v2-kpi{padding:14px}.v2-kpi strong{font-size:24px}.v2-risklist{padding:2px 14px}.v2-facts{grid-template-columns:1fr}
  .v2-hero{padding:18px;border-radius:18px}.v2-path{display:none}
  .pfnav{background:rgba(251,251,253,.94)!important}}
/* ===== правила аудита: минимум 12 px, без мелкого капса, ноль серым, контраст ≥ 4.5:1 ===== */
.dec .k,.dev .k,.prio .pl,.ladder .l,.cmph,.kcard .lab,.card-resp-ttl,.cell-ttl,.dr-h,.gd-ttl,.db-ttl,.db-grid .db-l,.mt-total .tl,
.main-table tbody td[data-l]::before,.fin th,.cb h5,.rh .kick{font-size:12px!important;text-transform:none!important;letter-spacing:0!important}
.kcard .foot,.mt-dy .sub,.mt-dy .dy-t,.sub,.unit,.u,.priority-label,.db-gd,.cb .fn{font-size:12px!important}
.u,.unit,.cb .fn,.cb h5,.dr-h,.cell-ttl,.db-ttl,.db-grid .db-l,.mt-total .tl,.dec .k,.prio .pl{color:#5E5E63!important}
.cb .c{width:52px!important;height:44px!important;font-size:12px!important}
.db-gd{background:#7A5A00!important;color:#fff!important}
.dec-block .db-grid > div:nth-child(2) > b{color:#1F6E35!important}
.card-anchor,#drill,[id^="cell-"]{scroll-margin-top:64px}
.stMarkdown svg text{font-size:12px!important}
.dr-over,.dr-over i,.label,.ladder .s,.ladder .l,.main-table th,.main-table th .unit,.stMarkdown th{font-size:12px!important}
.dr-houses .dr-row{font-size:12px!important}
.cb .c s{font-size:12px!important;opacity:1!important}
.cb .c b{font-size:13px}
.mt-dy .sub.wr,.mt-dy .dy-t.hl-bad{color:#A52C28!important}
.mt-dy .sub.improved,.mt-dy .dy-t.hl-good,.fin td .improved{color:#1F6E35!important}
.v2-zero,.v2-kpi.v2-zero strong,.v2-kpi.v2-zero strong a,.v2-zero .v2-amount{color:#6B6B70!important}
.v2-fill.v2-zero{background:#C7C7CC!important}
.v2-hero.v2-neutral .v2-number{color:#1D1D1F}
.v2-first .v2-neutral{grid-column:1 / -1}
.v2-concl{margin:0 0 8px}
.v2-concl .v2-hero{padding:20px 26px}
.v2-concl .v2-number{font-size:clamp(28px,3.2vw,40px);margin:6px 0 4px}
.v2-concl .v2-hero h2{font-size:clamp(19px,1.8vw,23px)!important}
.v2-concl .v2-action{gap:8px}
.v2-concl .v2-action .v2-what{font-size:17px}
.v2-empty{background:#fff;border:1px dashed #C7C7CC;border-radius:16px;padding:22px;color:#424245;font-size:14px;text-align:center;margin:4px 0 12px}
.v2-crumbs{font-size:13px!important;margin:0 0 6px}
.v2-crumbs a{color:#0060C0!important;text-decoration:none!important}
.v2-crumbs a:hover{text-decoration:underline!important}
.v2-crumbs [aria-current="page"]{color:#1D1D1F;font-weight:600}
.v2-crumbs .v2-lvl{color:#6B6B70;font-size:12px;margin-left:4px}
/* кнопки: белый текст только на тёмном фоне (контраст ≥ 4.5:1) */
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"],[data-testid="stBaseButton-primary"]{background:#0060C0!important;border-color:#0060C0!important;color:#fff!important}
.stButton button,.stDownloadButton button,[data-testid^="stBaseButton"]{min-height:44px;border-radius:980px!important}
/* раскрытие на телефоне: ЖК после 5-го — по кнопке «Ещё» */
.v2-more-t{display:none}
.v2-more-l{display:none}
@media(max-width:640px){
  .v2-more-t:not(:checked) ~ .v2-risklist .v2-extra{display:none}
  .v2-more-l{display:flex;align-items:center;justify-content:center;min-height:44px;margin:-8px 0 0;background:#fff;border:1px solid #E3E3E8;border-radius:14px;
    color:#0060C0;font-size:15px;font-weight:500;cursor:pointer}
  .v2-more-t:checked ~ .v2-more-l .v2-mo,.v2-more-t:not(:checked) ~ .v2-more-l .v2-mc{display:none}
  .v2-hero .v2-foot,.v2-hide-m{display:none}
  /* цели касания ≥ 44 px */
  .pfnav a,.pfnav summary,.pfnav .pf-ver a{min-height:44px;display:flex!important;align-items:center}
  .pfnav .more-links a{min-height:44px;display:flex!important;align-items:center;font-size:13px!important;padding:0 12px!important}
  [data-testid="stHeaderActionElements"]{display:none!important}
  .pfnav{height:auto!important;flex-wrap:wrap;row-gap:0;padding-top:0;padding-bottom:0;white-space:nowrap}
  .pfnav .pf-ver{order:0}.pfnav .more{order:1;margin-left:auto}.pfnav::before{content:"";order:2;flex-basis:100%;height:0}
  .pfnav > a{order:3}
  .pfnav > a,.pfnav summary,.pfnav .pf-ver a{min-width:44px;justify-content:center;font-size:13px!important;padding:0 8px!important}
  .stMainBlockContainer,.block-container{padding-top:40px!important}
  .v2-crumbs .v2-lvl{display:none}
  .v2-hero h2{font-size:21px!important}
  .exec-control a,.pf-links a{min-height:44px;display:inline-flex!important;align-items:center}
  .v2-kpi a{display:flex!important;width:100%}
  .card-anchor,#drill,[id^="cell-"]{scroll-margin-top:120px}
  .card-open a,.fin a,.cb a.c{min-height:44px;display:inline-flex!important;align-items:center}
  .cb a.c{display:flex!important;flex-direction:column;justify-content:center}
  [data-baseweb="select"] > div{min-height:44px}
  .main-table th,.main-table td{font-size:12.5px!important}
  .pf-links a,.v2-cta a,.v2-crumbs a,.pf-path a{min-height:44px;display:inline-flex!important;align-items:center}
  .v2-name a,.v2-detail a.v2-go,.v2-kpi a{display:inline-flex;align-items:center;min-height:44px}
  .v2-detail a.v2-go{font-size:13px!important}
  [data-testid="stExpander"] summary,details > summary{min-height:44px;display:flex;align-items:center}
  .main-table a.cell,.mt-total a.cell{display:inline-flex;align-items:center;min-height:44px;min-width:44px}
  .main-table td.jk a,.mt-total a,.mt-toggle label{display:inline-flex;align-items:center;min-height:44px}
  .cb .c{width:48px!important}
}
/* печать / PDF для совещания */
@media print{
  .pfnav,header,[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"],.v2-more-l,.v2-cta,
  [data-testid="stToolbar"]{display:none!important}
  html,body,.stApp,[data-testid="stAppViewContainer"]{background:#fff!important}
  .stMainBlockContainer,.block-container{padding:0 8mm!important;max-width:none!important}
  .v2-more-t ~ .v2-risklist .v2-extra{display:grid!important}
  .v2-hero,.v2-kpi,.v2-risklist,.v2-row,[data-testid="stExpander"],.fin,.dec-block{break-inside:avoid}
  .v2-hero,.v2-kpi,.v2-risklist{border-color:#999!important}
  .v2-overview a,.v2-name a{color:#000!important;text-decoration:none!important}
  .v2-kpis{grid-template-columns:repeat(4,1fr)!important}
}
</style>'''



def _pct(v):
    return f"{v:.1f}".replace(".", ",") + "%"


def fig_empty(fig) -> bool:
    """График без единой точки данных (все ряды пустые) — вместо пустой рамки показываем подпись."""
    lay = getattr(fig, "layout", None)
    if lay is not None and (len(lay.shapes or ()) or len(lay.images or ())):
        return False                      # график из фигур (например, этапы) — не пустой
    data = list(getattr(fig, "data", []) or [])
    if not data:
        return True
    for tr in data:
        for attr in ("x", "y", "values", "z", "base"):
            v = getattr(tr, attr, None)
            if v is not None and len(v):
                return False
    return True


def min_font_fig(fig, minimum: int = 12):
    """Версия 2: подписи графиков не мельче 12 px — поднимаются только явно заданные меньшие размеры, цвета и данные не меняются."""
    def bump(font):
        if font is not None and getattr(font, "size", None) is not None and font.size < minimum:
            font.size = minimum
    lay = fig.layout
    bump(lay.font)
    bump(lay.legend.font)
    for name in dir(lay):
        if name.startswith(("xaxis", "yaxis")) and not name.endswith("_"):
            ax = getattr(lay, name, None)
            if ax is not None and hasattr(ax, "tickfont"):
                bump(ax.tickfont)
                bump(ax.title.font)
    for an in lay.annotations or ():
        bump(an.font)
    for tr in fig.data:
        if hasattr(tr, "textfont"):
            bump(tr.textfont)
    return fig


def empty_html(note: str = EMPTY_NOTE) -> str:
    return f'<div class="v2-empty" role="note">{escape(note)}</div>'


def crumbs(link, name=None, key=None, corpus=None, unit=None, tab_label=None, remarks=None):
    """Путь матрёшки на каждом уровне: Портфель › ЖК › Корпус › Квартира › Замечания (последний уровень — текущий, без ссылки)."""
    steps = [("Портфель", {})]
    if name is not None:
        steps.append((name, {"jk": key}))
    if corpus is not None:
        steps.append((f"Корпус {corpus}", {"jk": key, "tab": "chess", "corpus": corpus}))
    elif tab_label:
        steps.append((tab_label, None))
    if unit is not None:
        steps.append((unit, None))
        steps.append((f"Замечания · {remarks}" if remarks is not None else "Замечания", None))
    out = []
    last = len(steps) - 1
    for i, (label, route) in enumerate(steps):
        if i == last or route is None:
            out.append(f'<span aria-current="{"page" if i == last else "false"}">{escape(label)}</span>')
        else:
            out.append(link(label, **route))
    levels = ("портфель", "ЖК", "корпус", "квартира", "замечание")
    return ('<nav class="pf-path v2-crumbs" aria-label="Путь: портфель › ЖК › корпус › квартира › замечание">' + "".join(out)
            + f'<span class="v2-lvl">уровень {min(len(steps), 5)} из 5 · {levels[min(len(steps), 5) - 1]}</span></nav>')


def card_crumbs(link, name, key):
    """Путь внутри раскрытой карточки ЖК на сводке."""
    return ('<nav class="pf-path v2-crumbs" aria-label="Путь">' + link("Портфель") + f'<span aria-current="page">{escape(name)}</span>'
            + link("Корпуса и квартиры", jk=key, tab="chess") + '</nav>')


# Порядок поиска главной проблемы — по уже посчитанным показателям, первый ненулевой.
PROBLEMS = (
    ("risk_day", "наибольшая неустойка в день", "дневной неустойки портфеля", "Ранжирование по неустойке в день."),
    ("overdue_kv", "больше всего квартир с нарушенным сроком", "квартир с нарушенным сроком", "Ранжирование по квартирам с нарушенным сроком."),
    ("remarks", "больше всего открытых замечаний", "открытых замечаний портфеля", "Ранжирование по открытым замечаниям."),
)


def _value(p, row, field):
    return (row or {}).get("remarks", 0) if field == "remarks" else p.get(field, 0)


def pick_problem(projects, main_rows):
    """Главная проблема портфеля: первый показатель из PROBLEMS, ненулевой хотя бы у одного ЖК; ЖК — с наибольшим значением.
    Возвращает (поле, ранжированные ЖК) или (None, ранжированные по неустойке) — если всё по нулям."""
    by_key = {r['key']: r for r in main_rows}
    for field, *_ in PROBLEMS:
        vals = [_value(p, by_key.get(p['key']), field) for p in projects]
        if any(v > 0 for v in vals):
            ranked = sorted(projects, key=lambda p: (-_value(p, by_key.get(p['key']), field), -p['risk_day'], -p['overdue_kv'], p['name']))
            return field, ranked
    return None, sorted(projects, key=lambda p: (-p['risk_day'], -p['overdue_kv'], p['name']))


def _fmt_value(field, v, fmt):
    return f'{fmt(round(v))} ₽' if field == "risk_day" else f'{fmt(v)} {"кв." if field == "overdue_kv" else "шт."}'


def _hero(projects, totals, main_rows, link, fmt, mln):
    """Вывод «главная проблема → решение» — общий для обзора и для сводки версии 2. Возвращает (html, field, ranked, order_note, totals_by)."""
    by_key = {r['key']: r for r in main_rows}
    field, ranked = pick_problem(projects, main_rows)
    total_risk = totals['risk_day']
    totals_by = {"risk_day": total_risk, "overdue_kv": totals['overdue_kv'], "remarks": sum(r.get("remarks", 0) for r in main_rows)}
    if field:
        _, verb, share_of, order_note = next(x for x in PROBLEMS if x[0] == field)
        lead = ranked[0]
        row = by_key[lead['key']]
        lead_v = _value(lead, row, field)
        whole = totals_by[field]
        share = max(0.0, min(100.0, 100 * lead_v / whole)) if whole > 0 else 0.0
        second = _value(ranked[1], by_key.get(ranked[1]['key']), field) if len(ranked) > 1 else -1
        verb = verb if lead_v > second else verb.replace("наибольшая", "наибольшая (наравне с другими ЖК)").replace("больше всего", "больше всего (наравне с другими ЖК)")
        decision = row['dec']
        if decision:
            eff = decision["effect"]
            eff_cls = "v2-effect" if eff > 0 else "v2-effect v2-zero"
            day = (f'<span class="v2-sub">−{fmt(round(decision["effect_day"]))} ₽ в день к концу 4-й недели</span>'
                   if decision.get("effect_day") else '')
            action = (f'<span class="v2-label">Управленческое решение</span><span class="v2-what">{escape(decision["short"])}</span>'
                      f'<div class="v2-facts"><div class="v2-fact"><span class="v2-label">Ответственный</span><b>{escape(decision["role"])}</b></div>'
                      f'<div class="v2-fact"><span class="v2-label">Финансовый эффект за 4 недели</span>'
                      f'<b class="{eff_cls}">{"−" if eff > 0 else ""}{mln(eff)} млн ₽</b>{day}</div></div>'
                      f'<div class="v2-foot">Расчёт модели, до затрат на меру.</div>'
                      f'<div class="v2-cta">' + link('Открыть решение', card=lead['key'], cell='decide') + '</div>')
        else:
            action = '<span class="v2-label">Управленческое решение</span><p>Оценённое решение отсутствует.</p>'
        context = [f'{_pct(share)} {share_of}']
        if field != "overdue_kv":
            context.append(f'{fmt(row["overdue"])} из {fmt(totals["overdue_kv"])} кв. с нарушенным сроком передачи')
        else:
            context.append(f'{fmt(row["overdue"])} из {fmt(totals["overdue_kv"])} кв. портфеля')
        unit_word = "в день" if field == "risk_day" else ""
        big = _fmt_value(field, lead_v, fmt)
        if unit_word:
            big = big + f'<small>{unit_word}</small>'
        hero = (f'<div class="v2-hero v2-prob" data-field="{field}"><span class="v2-eyebrow">Главная проблема портфеля</span>'
                f'<h2>{escape(lead["name"])}: {verb}</h2>'
                f'<span class="v2-number">{big}</span>'
                f'<p>{" · ".join(context)}</p>'
                f'<div class="v2-cta">' + link('Открыть ЖК', card=lead['key']) + '</div></div>'
                f'<div class="v2-hero v2-action">{action}</div>')
    else:
        order_note = "Ранжирование по неустойке в день."
        hero = ('<div class="v2-hero v2-prob v2-neutral" data-field="none"><span class="v2-label">Состояние портфеля</span>'
                '<h2>Срок передачи по ДДУ нигде не нарушен</h2>'
                '<p>Неустойка в день — 0 ₽, открытых замечаний нет.</p></div>')

    return hero, field, ranked, order_note, totals_by


def render(projects, totals, main_rows, slice_text, link, fmt, mln):
    """Первый экран версии 2: вывод (главная проблема) → решение → 4 KPI → ЖК по финансовому риску.
    Все тексты собираются из тех же чисел, что показаны на экране."""
    by_key = {r['key']: r for r in main_rows}
    total_risk = totals['risk_day']
    hero, field, ranked, order_note, totals_by = _hero(projects, totals, main_rows, link, fmt, mln)
    def metric(label, value, raw, cell=None, critical=False, detail=''):
        bad = critical and raw > 0
        cls = 'v2-kpi v2-critical' if bad else ('v2-kpi v2-zero' if raw == 0 else 'v2-kpi')
        value_html = link(value, card='total', cell=cell) if cell else escape(value)
        return f'<div class="{cls}"><span class="v2-label">{label}</span><strong>{value_html}</strong><span class="v2-label">{detail}</span></div>'

    t26, l26 = sum(r["t2026"] for r in main_rows), sum(r["left2026"] for r in main_rows)
    kpis = (metric('Нарушен срок передачи, кв.', fmt(totals["overdue_kv"]), totals["overdue_kv"], 'overdue', True, 'по всем ЖК')
            + metric('Неустойка в день, ₽', fmt(round(total_risk)), round(total_risk), critical=True, detail='оценка за +1 день просрочки')
            + metric('Передано в 2026, кв.', fmt(t26), t26, 't2026', detail='с начала года')
            + metric('Остаток 2026, кв.', fmt(l26), l26, 'left2026', detail='срок по ДДУ в 2026'))
    rows = []
    rank_field = field or "risk_day"
    whole = totals_by[rank_field]
    for i, p in enumerate(ranked, 1):
        r = by_key.get(p['key'], {})
        v = _value(p, r, rank_field)
        share = max(0.0, min(100.0, 100 * v / whole)) if whole > 0 else 0.0
        zero = v <= 0
        top = i == 1 and not zero
        chess = link('Корпуса и квартиры', css='v2-go', jk=p['key'], tab='chess')
        cls = "v2-row" + (" v2-top" if top else "") + (" v2-zero" if zero else "") + (" v2-extra" if i > 5 else "")
        rows.append(f'<div class="{cls}"><span class="v2-rank">{i}</span>'
                    f'<div class="v2-name">{link(p["name"], card=p["key"])}'
                    f'<span class="v2-detail">{fmt(p["overdue_kv"])} кв. с нарушенным сроком'
                    + (f' · {fmt(r["remarks"])} замечаний' if "remarks" in r else '') + f' · {chess}</span></div>'
                    f'<div class="v2-bar"><div class="v2-track"><span class="v2-fill{" v2-zero" if zero else ""}" style="width:{share:.3f}%"></span></div>'
                    f'<span class="v2-share">{_pct(share)} {"неустойки" if rank_field == "risk_day" else "показателя"} портфеля</span></div>'
                    f'<div class="v2-amount">{_fmt_value(rank_field, v, fmt)}<span class="v2-detail">{"в день" if rank_field == "risk_day" else ""}</span></div></div>')
    n_extra = max(0, len(ranked) - 5)
    toggle = ('<input type="checkbox" id="v2-more" class="v2-more-t" hidden>' if n_extra else '')
    more = (f'<label for="v2-more" class="v2-more-l"><span class="v2-mo">Ещё {n_extra} ЖК</span><span class="v2-mc">Свернуть</span></label>'
            if n_extra else '')
    path = ('<ol class="v2-path" aria-label="Уровни раскрытия"><li>Портфель</li><li>ЖК</li><li>Корпус</li>'
            '<li>Квартира</li><li>Замечание</li></ol>')
    return (f'<section class="v2-overview" id="summary"><div class="v2-foot">Срез {escape(slice_text)} · {len(ranked)} ЖК · '
            'суммы неустойки и эффект мер — расчёт модели, не фактические выплаты.</div>'
            '<div class="v2-first">' + hero + '<div class="v2-kpis">' + kpis + '</div></div>'
            '<div class="v2-head"><h2 class="v2-title">ЖК по финансовому риску</h2>' + path + '</div>'
            + toggle + '<div class="v2-risklist">' + ''.join(rows) + '</div>' + more +
            f'<div class="v2-foot">{order_note} Название ЖК раскрывает карточку ниже; '
            '«Корпуса и квартиры» ведёт к шахматке, квартире и её замечаниям.</div></section>')


def conclusion(projects, totals, main_rows, link, fmt, mln):
    """Сводка версии 2 (на основе версии 1): над плашкой «Итого» — вывод из тех же чисел: главная проблема портфеля,
    решение, ответственная роль и эффект. Ключевые показатели — в плашке «Итого» версии 1 сразу под выводом."""
    hero, field, _, _, _ = _hero(projects, totals, main_rows, link, fmt, mln)
    return f'<section class="v2-overview v2-concl" id="conclusion" aria-label="Главная проблема портфеля"><div class="v2-first">{hero}</div></section>'
