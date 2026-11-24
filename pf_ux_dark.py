"""Версия 3 «Отчёта по заселению»: тёмная тема поверх того же отчёта (маршрут ?view=portfolio3, далее — ver=3).

Основа — UX-пакет к приложению (палитра, карточки KPI с цветной левой границей, тёмные таблицы, палитра графиков).
В отличие от пакета, тема не подключается глобально: CSS выводится только в версии 3, а графики перекрашиваются
в момент вывода (U.chart) по флагу текущего прогона — версии 1 и 2 не меняются. Данные и расчёты — те же, что в версии 1.
"""
from __future__ import annotations

import re
import threading

import plotly.graph_objects as go

VIEW = "portfolio3"
UX_SCHEMA = "x1"
BG, CARD, BORDER, TEXT, MUTED = '#0f1419', '#1a2332', '#2a3648', '#e8eef7', '#8b9bb4'
BLUE, GREEN, RED, ORANGE, PURPLE = '#3b82f6', '#22c55e', '#ef4444', '#f59e0b', '#a78bfa'

_state = threading.local()      # прогон Streamlit — свой поток: флаг не влияет на другие сессии


def set_active(on: bool) -> None:
    _state.on = bool(on)


def active() -> bool:
    return getattr(_state, "on", False)


def recolor(markup):
    # Only declarations in existing CSS; no data or HTML attribute rewriting.
    surfaces = {'#fff', '#ffffff', '#f3f5f8', '#f3f5f9', '#f2f5f9', '#f7f9fc', '#eef2f8', '#eef2f7', '#e8edf5', '#f5f8fc', '#e9edf2', '#e6eaf0', '#e1eaf4', '#fffaf0'}
    ink = {'#0b1f3a', '#14213d', '#14243b'}
    muted = {'#3a4658', '#4a5568', '#596577', '#5b6778', '#5b6b82', '#7a8597'}
    borders = {'#d5dbe3', '#c9d2df', '#c9d2de', '#e1e6ee', '#e6eaf0', '#d5dbe5', '#0b1f3a', '#14243b', '#14213d'}
    def declaration(m):
        prop, value = m.group(1), m.group(2)
        def color(h):
            raw = h.group(0); c = raw.lower()
            if prop == 'color':
                if c in ink: return TEXT
                if c in muted: return MUTED
                if c in {'#b3261e', '#a52c28'}: return '#f87171'
                if c in {'#2e7d32', '#2f6b3a', '#246829'}: return '#4ade80'
                if c in {'#a67c00', '#80550e'}: return '#fbbf24'
                if c in {'#23406e', '#234f7a'}: return '#93c5fd'
            if prop.startswith('background'):
                if c in surfaces: return CARD if c in {'#fff', '#ffffff'} else '#151c28'
                if c == '#0b1f3a': return '#121820'
            if prop.startswith('border') and c in borders: return BORDER
            return raw
        value = re.sub(r'#[0-9a-fA-F]{3,8}\b', color, value)
        if prop.startswith(('background', 'border')):
            value = value.replace('var(--navy)', 'var(--accent)')
        return prop + ':' + value
    return re.sub(r'(?<![-\w])((?:background(?:-color)?|border(?:-[a-z]+)*|color))\s*:\s*([^;}]+)', declaration, markup)



CSS = '''<style>
:root {--bg:#0f1419;--paper:#1a2332;--card:#1a2332;--card-hover:#1f2a3c;--line:#2a3648;--row:#2a3648;--hov:#1f2a3c;--ink:#e8eef7;--navy:#e8eef7;--ink2:#8b9bb4;--ink3:#8b9bb4;--accent:#3b82f6;--risk:#f87171;--good:#4ade80;--gold:#f59e0b;--r8:16px;--sh1:0 8px 32px rgba(0,0,0,.35);color-scheme:dark}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"] {background:var(--bg)!important;color:var(--ink)!important}
[data-testid="stSidebar"] {background:#121820!important;border-right:1px solid var(--line)}
.pfnav,.pfnav .more-links {background:#121820!important;border-bottom:1px solid var(--line)}
.pfnav .pf-ver a[aria-current="page"],.pfnav a[aria-current="page"],.pfnav a:hover {background:rgba(59,130,246,.18)!important;color:#93c5fd!important}
.rh,.p2-head,.exec-header {background:#121820!important;border:1px solid var(--line)!important;border-bottom:3px solid var(--accent)!important;border-radius:16px!important;padding:24px 28px!important;box-shadow:none!important}
.rh .kick,.p2-head .kick {color:var(--ink2)!important}
.rh .ttl,.p2-head .ttl {color:var(--ink)!important;font-size:clamp(24px,2.5vw,34px)!important}
.sec,.p2-sec,.main-port .mt-l2 {border:0!important;border-left:5px solid var(--accent)!important;padding:0 0 0 12px!important;color:var(--ink)!important;margin-top:24px}
.sec .nm {color:#93c5fd}
.kcard,.exec-metric,.exec-project,.p2-kpi,.p2-card,.p2-focus,.card,.prio,.concl,.dec,.dev,.pen-head,.pen-note,.pen-basis,.cell-panel,.dec-block,.gantt-l1,.contrib-bars,details.mx-l2,.mt-total,.ladder .st,.weekly,.weekly .item {background:var(--paper)!important;border:1px solid var(--line)!important;border-radius:16px!important;box-shadow:none}
.kcard,.exec-metric,.p2-kpi {border-left:4px solid var(--accent)!important;padding:20px 16px!important;transition:background .18s,transform .18s,box-shadow .18s;min-width:0}
.kcard.risk,.p2-focus,.concl {border-left:4px solid #ef4444!important}
.kcard:not(.risk):has(.dl.good) {border-left-color:#22c55e!important}
.kcard:hover,.exec-metric:hover,.exec-project:hover,.p2-kpi:hover {background:var(--card-hover)!important;transform:translateY(-2px);box-shadow:var(--sh1)}
.kcard .lab,.exec-label,.p2-kpi span,.mt-total .tl {font-size:11px!important;letter-spacing:.04em;text-transform:uppercase;color:var(--ink2)!important}
.kcard .val,.exec-metric strong,.p2-kpi b,.mt-total b {color:var(--ink)!important;font-variant-numeric:tabular-nums;letter-spacing:-.035em}
.kcard.risk .val,.p2-focus strong,.fin td.risk {color:#f87171!important}
.dl.good,.ok,.p2-ok,.lg-good,.exec-delta.good {color:#4ade80!important}
.dl.bad,.bad,.p2-bad,.lg-bad,.exec-delta.bad {color:#f87171!important}
.mt-total {gap:14px!important;padding:0!important;border:0!important;background:transparent!important}
.mt-total > * {background:var(--paper)!important;border:1px solid var(--line)!important;border-left:4px solid var(--accent)!important;border-radius:16px!important;padding:16px!important;min-width:0}
.mt-total > .key {border-left-color:#ef4444!important}
.mt-total > .tg {border-left-color:#a78bfa!important}
.mt-total > [data-k="decide"],.mt-total > [data-k="resp"] {border-left-color:#f59e0b!important}
.mt-total a.cell,.mt-total .ti b a {color:var(--ink)!important}
.main-table td.hl-bad a.cell,.mt-total .hl-bad a.cell {color:#f87171!important}
.main-table td.hl-good a.cell,.mt-total .hl-good a.cell {color:#4ade80!important}
.exec-metrics,.p2-kpis {gap:14px!important}
.exec-projects {gap:18px!important}
.fin,.exec-annual,.main-table,.p2-main {background:var(--paper)!important;color:var(--ink)!important}
.fin th,.exec-annual thead th,.main-table th,.tw table.fin th:first-child {background:#151c28!important;color:var(--ink2)!important;border-bottom:1px solid var(--line)!important}
.fin td,.exec-annual td,.main-table td {border-bottom-color:var(--line)!important}
.fin tr.tot td,.tw table.fin tr.tot td:first-child {background:#151c28!important}
.fin tbody tr:not(.mt-toggle):hover td,.exec-annual tbody tr:hover td {background:var(--card-hover)!important}
.tw,.main-port .tw,.pt3-wrap {border-radius:16px!important}
a[data-pf-route],.pf-path a,.pf-links a {color:#93c5fd!important}
.pfnav a[data-pf-route] {color:#c5ceda!important}
.pfnav a[data-pf-route][aria-current="page"] {color:#93c5fd!important}
.pf-links a,.pf-role {background:#1a2332!important;border-color:var(--line)!important;color:#93c5fd!important;border-radius:8px!important}
.pf-links a[aria-current="page"] {background:#243b59!important}
.cmp .trk,.contrib-track,.pen-bar,.ready-reasons .reason-track {background:#2a3648!important}
.cmp .now,.contrib-track i,.pen-bar i,.ready-reasons .reason-fill {background:#3b82f6!important}
.contrib-row.focus .contrib-track i {background:#ef4444!important}
.dr-h,.dr-tot,.dr-l4 {background:#151c28!important;color:var(--ink)!important}
.dr-house[open] > summary,.dr-house > summary:hover,.dr-apt > summary:hover {background:#1f2a3c!important}
.weekly .fields .approval {background:#243b59!important}
[data-testid="stPlotlyChart"],[data-testid="stDataFrame"],[data-testid="stExpander"] details {background:var(--paper)!important;border:1px solid var(--line)!important;border-radius:16px!important}
[data-testid="stPlotlyChart"] {padding:12px!important}
[data-testid="stExpander"] summary {color:var(--ink)!important}
[data-testid="stButton"] button,[data-testid="stButtonGroup"] button {border-radius:8px!important}
[data-testid="stButton"] button:hover {border-color:var(--accent)!important;color:#93c5fd!important}
:focus-visible {outline-color:#93c5fd!important}
@media(max-width:1100px) {.exec-metrics,.p2-kpis {grid-template-columns:repeat(2,minmax(0,1fr))!important}.exec-projects {grid-template-columns:1fr!important}}
@media(prefers-reduced-motion:reduce) {.kcard,.exec-metric,.exec-project,.p2-kpi {transition:none!important;transform:none!important}}
/* Версия 3: дополнения к теме пакета — виджеты, сводка, мини-графики, шахматка */
html,body {background:var(--bg)!important}
h1,h2,h3,h4,p,li,label,.note,.src,.cell-note,.cell-ttl,.exec-date,[data-testid="stMarkdownContainer"] {color:var(--ink)}
.note,.src,.cell-note,.exec-date,.mt-legend,[data-testid="stCaptionContainer"],.main-port .mt-l2 span {color:var(--ink2)!important}
.main-port .mt-l2 b,.cell-ttl b,.db-main,.card-resp-ttl {color:var(--ink)!important}
.main-port .mt-l2 {border-bottom:0!important}
.mt-total > .tg,.mt-total > [data-k="decide"],.mt-total > [data-k="resp"] {border-top:1px solid var(--line)!important}
.mt-total .u,.main-table td .u,.mt-total .tgi i,.mt-dy .sub,.mt-dy .dy-t {color:var(--ink2)!important}
.mt-dy .sub.wr,.mt-dy .dy-t.hl-bad,.dy-t.hl-bad {color:#f87171!important}
.mt-dy .sub.improved,.mt-dy .dy-t.hl-good,.dy-t.hl-good {color:#4ade80!important}
.main-table a.cell,.fin a.cell {color:var(--ink)!important;border-bottom-color:#3b4a61!important}
.main-table a.cell:hover {background:rgba(59,130,246,.15)!important;color:#93c5fd!important}
.main-table td,.fin td {color:var(--ink)} .main-table td .sub,.fin td .sub,.main-table td.resp .sub {color:var(--ink2)!important}
.main-table th .unit,.fin th .unit {color:var(--ink2)!important}
svg.sp line[stroke="#D5DBE3"] {stroke:#2a3648} svg.sp line[stroke="#4A5568"] {stroke:#8b9bb4}
svg.sp polyline[stroke="#5B7BA6"] {stroke:#60a5fa} svg.sp circle[fill="#5B7BA6"] {fill:#60a5fa}
svg.sp polyline[stroke="#B3261E"] {stroke:#f87171} svg.sp circle[fill="#B3261E"] {fill:#f87171}
.cb {color:#14213D} .cb * {color:inherit}      /* шахматка — светлая вставка: статусы квартир читаются в исходных цветах */
.priority-label,.db-gd {background:rgba(245,158,11,.15)!important;color:#fbbf24!important;border-color:#594a29!important}
/* виджеты Streamlit (тема приложения — светлая, поэтому только для версии 3) */
[data-testid="stSidebar"] * {color:var(--ink)}
[data-baseweb="select"] > div,[data-baseweb="input"],[data-baseweb="input"] input,[data-testid="stNumberInput"] input,[data-baseweb="base-input"] {background:var(--paper)!important;color:var(--ink)!important;border-color:var(--line)!important}
[data-baseweb="popover"] ul,[data-baseweb="menu"] {background:var(--paper)!important} [data-baseweb="menu"] li {color:var(--ink)!important}
[data-baseweb="menu"] li:hover,[data-baseweb="menu"] [aria-selected="true"] {background:var(--card-hover)!important}
[data-testid="stNumberInput"] button {background:#151c28!important;color:var(--ink)!important;border-color:var(--line)!important}
[data-testid="stWidgetLabel"] p,[data-testid="stRadio"] label p,[data-testid="stSlider"] p {color:var(--ink)!important}
[data-testid="stExpander"] summary:hover {color:#93c5fd!important} [data-testid="stExpander"] summary svg {fill:var(--ink2)}
[data-testid="stDataFrame"] {background:#ffffff!important}
[data-testid="stExpander"] details > summary,[data-testid="stExpander"] details[open] > summary,[data-testid="stExpander"] details > summary:hover {background:var(--paper)!important;color:var(--ink)!important}
[data-testid="stExpander"] details[open] > summary {border-bottom:1px solid var(--line)}
[data-testid="stExpanderDetails"] {background:var(--paper)!important}
.mt-total .tdy .mt-dy {flex-wrap:wrap} .mt-total .tdy .sub,.mt-total .tdy .dy-t {white-space:normal!important}
[style*="color:#0B1F3A"],[style*="color: rgb(11, 31, 58)"] {color:var(--ink)!important}
[style*="color:#B3261E"],[style*="color: rgb(179, 38, 30)"] {color:#f87171!important}
[style*="color:#2E7D32"],[style*="color: rgb(46, 125, 50)"] {color:#4ade80!important}
[data-testid="stSelectbox"] [data-baseweb="select"] div {background-color:var(--paper)!important;color:var(--ink)!important;border-color:var(--line)!important}
[data-testid="stSelectbox"] svg {fill:var(--ink2)!important}
</style>'''


# ---------------------------------------------------------------- графики Plotly
_MAP = {"#0b1f3a": BLUE, "#14213d": BLUE, "#14243b": BLUE, "#23406e": "#60a5fa", "#5b7ba6": "#60a5fa", "#3f4a5a": "#93c5fd",
        "#b3261e": RED, "#a52c28": RED, "#a67c00": ORANGE, "#80550e": ORANGE, "#2e7d32": GREEN, "#2f6b3a": GREEN,
        "#b7c0cc": "#64748b", "#9aa5b4": "#64748b", "#e3e7ed": "#2a3648", "#d5dbe3": BORDER, "#c9d2df": BORDER}
_BG_KEYS = {"paper_bgcolor", "plot_bgcolor", "bgcolor"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")


def _lum(h: str) -> float:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return .2126 * r + .7152 * g + .0722 * b


def _dark(c: str, key: str, font: bool) -> str:
    low = c.lower()
    if key in _BG_KEYS:
        return CARD if _lum(low) > .6 else low
    if font:                                    # подписи: тёмные → светлые, серые → приглушённые
        if low in ("#b3261e", "#a52c28"):
            return "#f87171"
        if low in ("#2e7d32", "#2f6b3a"):
            return "#4ade80"
        if low in ("#a67c00",):
            return "#fbbf24"
        lum = _lum(low)
        return TEXT if lum < .2 else MUTED if lum < .6 else low
    if low in _MAP:
        return _MAP[low]
    lum = _lum(low)
    return BORDER if lum > .85 else BLUE if lum < .15 else low


def _walk(obj, key="", font=False):
    if isinstance(obj, dict):
        return {k: _walk(v, k, font or k in ("font", "tickfont", "textfont", "insidetextfont", "outsidetextfont", "title")) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_walk(v, key, font) for v in obj]
    if isinstance(obj, str):
        if "color" in key and _HEX.fullmatch(obj.strip()):
            return _dark(obj.strip(), key, font)
        if "color:" in obj:                    # HTML-подписи Plotly: <span style="color:#B3261E">
            return re.sub(r"color:\s*(#[0-9a-fA-F]{3,6})", lambda m: "color:" + _dark(m.group(1), "color", True), obj)
    return obj


def dark_fig(fig):
    """Тот же график в тёмной палитре: фон карточки, светлые подписи, сетка цвета границ, акценты — из палитры темы."""
    d = _walk(fig.to_plotly_json())
    out = go.Figure(d)
    out.update_layout(paper_bgcolor=CARD, plot_bgcolor=CARD, font_color=TEXT, colorway=[BLUE, GREEN, RED, ORANGE, PURPLE],
                      hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font=dict(color=TEXT)), legend_font_color=TEXT,
                      title_font_color=TEXT)
    out.update_xaxes(gridcolor=BORDER, linecolor=BORDER, zerolinecolor=BORDER, tickfont_color=MUTED)
    out.update_yaxes(gridcolor=BORDER, linecolor=BORDER, zerolinecolor=BORDER, tickfont_color=TEXT)
    return out
