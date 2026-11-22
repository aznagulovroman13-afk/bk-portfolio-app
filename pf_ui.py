"""Оформление «Портфеля ЖК»: тёмная navy/metallic тема, большие цифры, без служебных меток."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY, INK, INK2, INK3 = "#0B1F3A", "#14213D", "#4A5568", "#596577"
LINE, GOLD, RISK, GOOD = "#D5DBE3", "#A67C00", "#B3261E", "#2E7D32"
SILVER, GRAPH = "#9AA5B4", "#3F4A5A"

CSS = """
<style>
:root { --navy: #0B1F3A; --ink: #14213D; --ink2: #4A5568; --ink3: #596577; --line: #D5DBE3; --gold: #A67C00; --risk: #B3261E;
  --paper: #FFFFFF; --bg: #E9EDF2; --bk-pad: clamp(16px, 3vw, 48px); color-scheme: light; }
html, body, .stApp, button, input, textarea, select, [class*="css"] {
  font-family: Inter, system-ui, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important; -webkit-font-smoothing: antialiased; }
html, body { background: var(--bg) !important; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg) !important; color: var(--ink) !important; min-height: 100vh; }
[data-testid="stMain"], [data-testid="stHeader"] { background: transparent !important; }
header[data-testid="stHeader"] { height: 0; }
[data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stMainMenu"], #MainMenu,
[data-testid="stAppDeployButton"], [data-testid="stToolbarActions"], footer { display: none !important; }
.stMainBlockContainer, .block-container { max-width: 1480px !important; margin: 0 auto; padding: 58px max(120px, var(--bk-pad)) 7rem var(--bk-pad) !important; }
html, body, .stApp, [data-testid="stMain"] { max-width: 100%; overflow-x: clip; }
h1, h2, h3, h4, p, li, label { color: var(--ink); }
[data-testid="stCaptionContainer"] { color: var(--ink3) !important; }
.num, .kcard .val, .fin td, .fin th.r { font-variant-numeric: tabular-nums; }
/* верхняя полоса */
.pfnav { position: fixed; top: 0; left: 0; right: 0; z-index: 999980; height: 44px; display: flex; align-items: center; gap: 8px;
  padding: 0 var(--bk-pad); background: var(--navy); font-size: 13px; white-space: nowrap; }
.pfnav b { color: #fff; font-size: 14px; letter-spacing: .02em; margin-right: 18px; font-weight: 600; }
.pfnav a, .pfnav summary { color: #C5CEDA !important; text-decoration: none !important; display: block; padding: 6px 9px; border-radius: 4px; }
.pfnav a:hover, .pfnav summary:hover, .pfnav [aria-current="page"], .pfnav .more:has([aria-current="page"]) > summary {
  color: #fff !important; background: #263F5D; }
.pfnav :focus-visible { outline: 2px solid #B8E4FF; outline-offset: 1px; }
.pfnav .more { position: relative; }
.pfnav summary { cursor: pointer; list-style: none; }
.pfnav summary::-webkit-details-marker { display: none; }
.pfnav summary::after { content: " ▾"; }
.pfnav .more-links { position: absolute; top: calc(100% + 6px); right: 0; min-width: 170px; padding: 5px; border-radius: 6px;
  background: var(--navy); box-shadow: 0 5px 20px #14213D33; max-height: calc(100dvh - 53px); overflow-y: auto; }
.pf-links, .pf-path { display: flex; align-items: center; flex-wrap: wrap; gap: 7px 10px; }
.pf-path { color: var(--ink2); font-size: 13px; }
.pf-path > :not(:first-child)::before { content: ""; display: inline-block; width: 5px; height: 5px; margin: 0 11px 2px 0; border-top: 1px solid var(--ink3); border-right: 1px solid var(--ink3); transform: rotate(45deg); }
.pf-links a { padding: 7px 11px; border: 1px solid var(--line); border-radius: 5px; background: var(--paper); text-decoration: none !important; }
.pf-links a[aria-current="page"] { background: #E1EAF4; border-color: #8EA8C4; font-weight: 700; }
.pf-links a:hover, .pf-path a:hover { border-color: #45688D; text-decoration: underline !important; }
.pf-links a:focus-visible, .pf-path a:focus-visible { outline: 2px solid #45688D; outline-offset: 2px; }
.st-key-pf_routes { display: none; }
:root:not([data-pf-route-ready]) a[data-pf-route] { pointer-events: none; }
@media (max-width: 435px) {
  .pfnav { gap: 0; }
  .pfnav a, .pfnav summary { font-size: 11px; padding-inline: 3px !important; }
}
/* шапка отчёта */
.rh { background: var(--navy); color: #fff; border-radius: 6px; padding: 26px 30px 20px; margin: 4px 0 18px; border-bottom: 3px solid var(--gold); }
.rh .kick { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #C5CEDA; font-weight: 600; }
.rh .ttl { font-size: clamp(24px, 2.4vw, 34px); font-weight: 700; margin: 6px 0 12px; letter-spacing: -.01em; color: #fff; }
.rh .meta { display: flex; flex-wrap: wrap; gap: 6px 30px; font-size: 12.5px; color: #C5CEDA; }
.rh .meta b { color: #fff; font-weight: 600; }
.km { margin: 10px 0 0; padding: 0; list-style: none; } .km li { font-size: 14.5px; color: var(--ink2); line-height: 1.45; padding: 3px 0 3px 14px; border-left: 3px solid var(--navy); margin: 6px 0; }

.concl { background: var(--paper); border: 1px solid var(--line); border-left: 4px solid var(--risk); border-radius: 4px; padding: 20px 26px; margin: 0 0 16px; }
.concl .t { font-size: clamp(20px, 2vw, 28px); font-weight: 700; color: var(--ink); line-height: 1.2; letter-spacing: -.01em; }
.concl .s { font-size: 15px; color: var(--ink2); margin-top: 8px; line-height: 1.45; }
.sec { font-size: 18px; font-weight: 700; color: var(--navy); margin: 34px 0 2px; padding-bottom: 6px; border-bottom: 1px solid var(--navy); scroll-margin-top: 60px;
  text-transform: none; letter-spacing: -.005em; }
.sec .nm { color: var(--gold); margin-right: 8px; font-variant-numeric: tabular-nums; }
.secsub { font-size: 13px; color: var(--ink2); margin: 6px 0 12px; }
.kgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 8px 0 12px; }
.kcard { background: var(--paper); border: 1px solid var(--line); border-top: 3px solid var(--navy); border-radius: 4px; padding: 14px 18px 12px; }
.kcard.risk { border-top-color: var(--risk); }
.kcard .lab { font-size: 12px; color: var(--ink2); line-height: 1.3; min-height: 32px; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; }
.kcard .val { font-size: clamp(28px, 2.4vw, 40px); font-weight: 700; color: var(--navy); line-height: 1.05; margin: 6px 0 6px; letter-spacing: -.02em; }
.kcard.risk .val { color: var(--risk); } .kcard .val.sm { font-size: clamp(20px, 1.7vw, 27px); }
.kcard .dl { font-size: 12.5px; font-weight: 600; font-variant-numeric: tabular-nums; } .dl.bad { color: var(--risk); } .dl.good { color: var(--good, #2E7D32); } .dl.flat { color: var(--ink3); font-weight: 500; }
.kcard .foot { font-size: 11.5px; color: var(--ink3); margin-top: 6px; line-height: 1.35; }
.card { background: var(--paper); border: 1px solid var(--line); border-radius: 4px; padding: 16px 20px; margin-bottom: 10px; }
.card.risk { border-left: 4px solid var(--risk); } .card .h { font-size: 15px; font-weight: 700; color: var(--navy); margin-bottom: 6px; }
.card .t { font-size: 13.5px; color: var(--ink2); line-height: 1.55; } .card .t b { color: var(--ink); }
.dec-h { font-size: 15px; font-weight: 700; color: var(--navy); margin: 18px 0 6px; }
.dec-h .no { display: inline-block; width: 24px; height: 24px; background: var(--navy); color: #fff; text-align: center; line-height: 24px; font-size: 12px; margin-right: 10px; border-radius: 3px; }
.dec { display: grid; grid-template-columns: 1.15fr 1fr 1.2fr 1fr; background: var(--paper); border: 1px solid var(--line); border-radius: 4px; overflow: hidden; margin-bottom: 10px; }
.dec > div { padding: 14px 16px; border-right: 1px solid var(--line); } .dec > div:last-child { border-right: none; }
.dec .k { font-size: 10.5px; font-weight: 700; color: var(--ink3); text-transform: uppercase; letter-spacing: .07em; margin-bottom: 6px; }
.dec .v { font-size: 13px; color: var(--ink); line-height: 1.5; }
.dec .big { font-size: 22px; font-weight: 700; color: var(--navy); display: block; font-variant-numeric: tabular-nums; }
.kgrid.big { grid-template-columns: repeat(3, 1fr); gap: 16px; }
.kgrid.big .kcard { padding: 20px 26px 16px; } .kgrid.big .kcard .val { font-size: clamp(40px, 4.2vw, 64px); margin: 10px 0 8px; } .kgrid.big .kcard .val.sm { font-size: clamp(34px, 3.4vw, 52px); }
.kgrid.big .kcard .dl { font-size: 15px; } .kgrid.big .kcard .foot { font-size: 12.5px; }
.slice { font-size: 13px; color: var(--ink2); margin: 2px 0 6px; } .slice b { color: var(--ink); }
.dev { border: 1px solid var(--line); border-left: 4px solid var(--navy); border-radius: 4px; background: var(--paper); padding: 10px 16px; margin: 8px 0 14px; font-size: 13.5px; color: var(--ink2); line-height: 1.5; }
.dev .k { display: inline-block; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; color: var(--navy); margin-right: 10px; }
.cmph { font-size: 12px; color: var(--ink3); text-transform: uppercase; letter-spacing: .04em; font-weight: 600; margin: 10px 0 6px; }
.cmp { display: grid; grid-template-columns: 190px 1fr 420px; gap: 14px; align-items: center; padding: 4px 0; font-size: 13px; color: var(--ink2); }
.cmp.tot { border-top: 1px solid var(--line); margin-top: 4px; padding-top: 8px; font-weight: 600; color: var(--ink); }
.cmp .trk { position: relative; height: 14px; background: var(--line2, rgba(128,140,160,.15)); border-radius: 2px; }
.cmp .now { position: absolute; left: 0; top: 0; bottom: 0; background: var(--navy); border-radius: 2px; opacity: .85; }
.cmp .rdy { position: absolute; left: 0; top: 3px; bottom: 3px; background: #9FB1C8; z-index: 2; border-radius: 2px; }
.cmp .prv { position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--risk); z-index: 3; }
.cmp .vl { font-variant-numeric: tabular-nums; } .cmp .vl span { color: var(--ink3); font-size: 12px; font-weight: 400; }
.prio { border: 1px solid var(--line); border-left: 5px solid var(--navy); border-radius: 4px; background: var(--paper); padding: 20px 26px; display: grid; grid-template-columns: .9fr 1.4fr 1.5fr; gap: 28px; }
.prio .pn { font-size: 24px; font-weight: 700; color: var(--ink); line-height: 1.15; } .prio .pm { font-size: 15px; color: var(--ink2); margin-top: 10px; line-height: 1.5; }
.prio .pm b { font-size: 30px; color: var(--navy); display: block; letter-spacing: -.01em; } .prio .pm span { color: var(--ink2); }
.prio .pl { font-size: 11px; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; color: var(--ink3); margin-bottom: 6px; }
.prio .pt { font-size: 14px; color: var(--ink); line-height: 1.5; } .prio ul { margin: 8px 0 0; padding-left: 18px; font-size: 13px; color: var(--ink2); line-height: 1.5; }
.ladder { display: grid; grid-template-columns: 1fr 22px 1fr 22px 1fr 22px 1fr; align-items: stretch; gap: 0; margin: 4px 0 6px; }
.ladder .st { background: var(--paper); border: 1px solid var(--line); border-top: 3px solid var(--navy); border-radius: 4px; padding: 12px 16px; }
.ladder .st.top { border-top-color: var(--risk); } .ladder .ar { display: flex; align-items: center; justify-content: center; font-size: 26px; color: var(--ink3); }
.ladder .l { font-size: 11.5px; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; color: var(--ink2); min-height: 30px; line-height: 1.3; }
.ladder .v { font-size: 26px; font-weight: 700; color: var(--navy); margin: 4px 0; letter-spacing: -.01em; } .ladder .st.top .v { color: var(--risk); }
.ladder .s { font-size: 11.5px; color: var(--ink3); line-height: 1.35; }
.prio .dc { border-top: 1px solid var(--line); padding: 8px 0; } .prio .dc:first-of-type { border-top: 0; padding-top: 0; }
.prio .dt { font-size: 13.5px; font-weight: 600; color: var(--ink); line-height: 1.4; } .prio .de { font-size: 13px; font-weight: 700; color: var(--navy); margin-top: 2px; }
.prio .dr { font-size: 12px; color: var(--ink2); margin-top: 2px; }
.prio .pr { font-size: 13px; color: var(--ink2); margin-top: 8px; }
table.pt3 td { vertical-align: top; } table.pt3 td:last-child { max-width: 280px; }
.tw { overflow-x: auto; -webkit-overflow-scrolling: touch; margin: 0 0 6px; }
.tw table.fin th:first-child, .tw table.fin td:first-child { position: sticky; left: 0; background: var(--paper); z-index: 1; box-shadow: 1px 0 0 var(--line); }
.tw table.fin th:first-child { background: #F3F5F8; } .tw table.fin tr.tot td:first-child { background: #F3F5F8; }
.fin td.r { white-space: nowrap; } .fin td .sub { display: block; white-space: nowrap; font-size: 11px; color: var(--ink3); font-weight: 400; } .fin td .wr { color: var(--risk); font-weight: 600; }
.fin td .improved { color: #2E7D32; font-weight: 600; }
.pen-summary { margin: 4px 0 18px; } .pen-summary h2 { font-size: 17px; color: var(--navy); margin: 0 0 8px; }
.pen-head { display: flex; flex-wrap: wrap; gap: 8px 28px; align-items: flex-end; background: var(--paper); border: 1px solid var(--line); border-left: 4px solid var(--navy); padding: 12px 16px; margin-bottom: 8px; }
.pen-head strong { display: block; font-size: 28px; color: var(--navy); font-variant-numeric: tabular-nums; } .pen-head strong em { font-size: 14px; font-style: normal; color: var(--ink2); }
.pen-split { display: flex; flex-wrap: wrap; gap: 4px 18px; color: var(--ink2); font-size: 13px; } .pen-split b { color: var(--ink); font-variant-numeric: tabular-nums; }
.fin th.grp { text-align: center; border-bottom: 1px solid var(--line); } .fin .sep { border-left: 1px solid var(--line); }
.pen-table td.r, .pen-table th.r { white-space: nowrap; }
.pen-bar { display: inline-block; width: 56px; height: 6px; background: #E6EAF0; margin-right: 8px; vertical-align: middle; } .pen-bar i { display: block; height: 100%; background: var(--navy); }
a[data-pf-route] { color: #234F7A !important; text-decoration: underline; text-underline-offset: 3px; }
.contrib-bars { border: 1px solid var(--line); background: var(--paper); border-radius: 4px; padding: 12px 14px; container-type: inline-size; }
.contrib-row { display: grid; grid-template-columns: minmax(110px, 1.05fr) minmax(48px, .95fr) 150px; align-items: center;
  padding: 7px 0; gap: 10px; font-size: 13px; border-bottom: 1px solid #E6EAF0; }
.contrib-row:last-child { border-bottom: 0; }
.contrib-track { display: block; height: 9px; background: #E9EDF2; border-radius: 3px; overflow: hidden; }
.contrib-track i { display: block; height: 100%; background: #31577D; border-radius: inherit; }
.contrib-value { text-align: right; font-variant-numeric: tabular-nums; }
.contrib-value span { color: var(--ink3); }
@container (max-width: 370px) {
  .contrib-row { grid-template-columns: minmax(0, 1fr) auto; gap: 4px 8px; }
  .contrib-track { order: 1; grid-column: 1 / -1; }
}
.fin td .sp { vertical-align: middle; } .fin td.nw { white-space: nowrap; }
.concl.one { border-left-color: var(--navy); padding: 16px 22px; } .concl.one .t { font-size: clamp(17px, 1.7vw, 22px); font-weight: 600; line-height: 1.35; }
@media (max-width: 640px) {
  .hm { display: none; } .fin { font-size: 12px; } .fin td, .fin th { padding: 7px 8px; }
  .kgrid.big { grid-template-columns: 1fr; } .ladder { grid-template-columns: 1fr; } .ladder .ar { display: none; } .ladder .st { margin-bottom: 8px; }
  .prio { grid-template-columns: 1fr; gap: 16px; } .cmp { grid-template-columns: 1fr; }
  .pfnav { padding: 0 43px 0 6px; gap: 1px; justify-content: space-between; font-size: 12px; }
  header [data-testid="stExpandSidebarButton"] {
    position: fixed !important; top: 5px; right: 4px; left: auto !important; width: 34px; height: 34px; color: #C5CEDA !important;
  }
  .stMainBlockContainer, .block-container { padding-right: 76px !important; }
  .pfnav b { display: none; }
  .pfnav a, .pfnav summary { padding: 6px 4px; }
}
.note { font-size: 13px; color: var(--ink3); line-height: 1.5; margin: 6px 0 10px; }
.pf-role { display: inline-block; font-size: 12px; color: var(--navy); background: #EEF2F7; border: 1px solid #C9D2DE; border-radius: 3px; padding: 1px 8px; margin: 2px 4px 2px 0; }
/* финансовые таблицы */
.fin { width: 100%; border-collapse: collapse; background: var(--paper); border: 1px solid var(--line); font-size: 13px; }
.fin th { background: #F3F5F8; color: var(--ink2); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; text-align: left;
  padding: 8px 12px; border-bottom: 2px solid var(--navy); } .fin th.r, .fin td.r { text-align: right; }
.fin td { padding: 8px 12px; border-bottom: 1px solid #E6EAF0; color: var(--ink); } .fin tr.tot td { font-weight: 700; background: #F3F5F8; border-top: 2px solid var(--navy); }
.fin td.risk { color: var(--risk); font-weight: 600; } .fin td.nd { color: var(--ink3); font-style: italic; }
.ok { color: #2E7D32; font-weight: 700; } .bad { color: var(--risk); font-weight: 700; }
.src { font-size: 13px; color: var(--ink3); line-height: 1.55; border-top: 1px solid var(--line); margin-top: 36px; padding-top: 12px; }
.src b { color: var(--ink2); }
.st-key-pf_bar { align-items: center; gap: 14px !important; justify-content: flex-start; margin: 0 0 6px; }
div[data-testid="stPlotlyChart"] { background: var(--paper); border: 1px solid var(--line); border-radius: 4px; padding: 6px 10px 2px; }
div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
div[data-testid="stExpander"] details { background: var(--paper); border: 1px solid var(--line); border-radius: 4px; }
[data-testid="stButtonGroup"] button { border-radius: 4px !important; }
@media (max-width: 900px) { .dec { grid-template-columns: 1fr; } .dec > div { border-right: none; border-bottom: 1px solid var(--line); } }
</style>
"""


def _template():
    t = go.layout.Template()
    t.layout = go.Layout(font=dict(family="Inter, system-ui, Segoe UI, Arial", size=12, color=INK2),
                         paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF", margin=dict(l=8, r=16, t=34, b=8),
                         title=dict(font=dict(size=13, color=NAVY), x=0, xanchor="left", y=.98),
                         xaxis=dict(showgrid=False, zeroline=False, linecolor=LINE, tickfont=dict(color=INK3)),
                         yaxis=dict(showgrid=False, zeroline=False, linecolor=LINE, tickfont=dict(color=INK)),
                         hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=SILVER, font=dict(color=INK)), separators=", ")
    return t


pio.templates["pf"] = _template()
pio.templates.default = "pf"


def section(title: str, sub: str = "", anchor: str | None = None, num: str = ""):
    aid = f' id="{html.escape(anchor)}"' if anchor else ""
    n = f'<span class="nm">{html.escape(num)}</span>' if num else ""
    st.markdown(f'<div class="sec"{aid}>{n}{html.escape(title)}</div>'
                + (f'<div class="secsub">{sub}</div>' if sub else ""), unsafe_allow_html=True)


def kpi_cards(items, big=False):
    out = []
    for it in items:
        d_txt, d_cls = it.get("delta") or ("", "flat")
        arrow = "▲ " if d_txt.startswith("+") else ("▼ " if d_txt.startswith("−") else "")
        out.append(
            f'<div class="kcard{" risk" if it.get("risk") else ""}"><div class="lab">{html.escape(it["label"])}</div>'
            f'<div class="val{" sm" if len(str(it["value"])) >= 10 else ""}">{html.escape(str(it["value"]))}</div>'
            f'<div class="dl {d_cls}">{arrow}{html.escape(d_txt)}</div>'
            f'<div class="foot">{html.escape(it.get("foot", ""))}</div></div>')
    st.markdown(f'<div class="kgrid{" big" if big else ""}">{"".join(out)}</div>', unsafe_allow_html=True)


def chart(fig, key=None, height=320):
    fig.update_layout(template="pf", height=height)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False, "locale": "ru"}, key=key)


def fin_table(head, rows, right=(), total_last=False, cls="", hide=()):
    """HTML-таблица в банковском стиле: числа вправо, итоговая строка выделена, первая колонка закреплена при прокрутке.
    rows: списки готовых ячеек (str, (str, style) или HTML, начинающийся с «<»). hide — номера колонок, скрываемых на узком экране."""
    hm = lambda i: " hm" if i in hide else ""
    th = "".join(f'<th class="{"r" if i in right else ""}{hm(i)}">{html.escape(h)}</th>' for i, h in enumerate(head))
    body = []
    for n, r in enumerate(rows):
        tr = ' class="tot"' if total_last and n == len(rows) - 1 else ""
        cells = []
        for i, c in enumerate(r):
            style = ""
            if isinstance(c, tuple):
                c, style = c
            style = f' style="{style}"' if style else ""
            txt = c if str(c).startswith("<") or "<span" in str(c) else html.escape(str(c))
            cells.append(f'<td class="{"r" if i in right else ""}{hm(i)}"{style}>{txt}</td>')
        body.append(f"<tr{tr}>{''.join(cells)}</tr>")
    st.markdown(f'<div class="tw"><table class="fin {cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>', unsafe_allow_html=True)


def spark(values, bad=False, w=108, h=30, *, scale=None, dates=None, target=None) -> str:
    """Мини-график ряда (SVG). Цвет — только при отставании от целевого темпа."""
    v = [float(x) for x in values]
    if len(v) < 2:
        return ""
    hi = max(max(v), scale or 0, target or 0, 1)
    pos = lambda x: h - 3 - x / hi * (h - 6)
    pts = [(2 + i * (w - 4) / (len(v) - 1), pos(x)) for i, x in enumerate(v)]
    col = "#B3261E" if bad else "#5B7BA6"
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    title = f'Квартиры, шкала 0–{hi:.0f}. ' + " · ".join(f"{day}: {value:.0f}" for day, value in zip(dates or (), v))
    goal = (f'<line x1="{pts[-2][0]:.1f}" x2="{w - 2}" y1="{pos(target):.1f}" y2="{pos(target):.1f}" '
            'stroke="#4A5568" stroke-width="1.1" stroke-dasharray="2 2"/>') if target is not None else ""
    return (f'<svg class="sp" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img"><title>{html.escape(title)}</title>'
            f'<line x1="2" x2="{w - 2}" y1="{h - 3}" y2="{h - 3}" stroke="{LINE}"/>{goal}'
            f'<polyline fill="none" stroke="{col}" stroke-width="1.6" points="{line}"/>'
            f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="2.4" fill="{col}"/></svg>')


def sources(notes_html: str):
    st.markdown(f'<div class="src">{notes_html}</div>', unsafe_allow_html=True)
