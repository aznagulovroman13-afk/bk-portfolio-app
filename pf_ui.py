"""Оформление «Портфеля ЖК»: тёмная navy/metallic тема, большие цифры, без служебных меток."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

NAVY, INK, INK2, INK3 = "#0B1F3A", "#14213D", "#4A5568", "#7A8494"
LINE, GOLD, RISK, GOOD = "#D5DBE3", "#A67C00", "#B3261E", "#2E7D32"
SILVER, GRAPH = "#9AA5B4", "#3F4A5A"

CSS = """
<style>
:root { --navy: #0B1F3A; --ink: #14213D; --ink2: #4A5568; --ink3: #7A8494; --line: #D5DBE3; --gold: #A67C00; --risk: #B3261E;
  --paper: #FFFFFF; --bg: #E9EDF2; --bk-pad: clamp(16px, 3vw, 48px); color-scheme: light; }
html, body, .stApp, button, input, textarea, select, [class*="css"] {
  font-family: Inter, system-ui, "Segoe UI", "Helvetica Neue", Arial, sans-serif !important; -webkit-font-smoothing: antialiased; }
html, body { background: var(--bg) !important; }
.stApp, [data-testid="stAppViewContainer"] { background: var(--bg) !important; color: var(--ink) !important; min-height: 100vh; }
[data-testid="stMain"], [data-testid="stHeader"] { background: transparent !important; }
header[data-testid="stHeader"] { height: 0; }
[data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stMainMenu"], #MainMenu,
[data-testid="stAppDeployButton"], [data-testid="stToolbarActions"], footer { display: none !important; }
.stMainBlockContainer, .block-container { max-width: 1480px !important; margin: 0 auto; padding: 58px var(--bk-pad) 5rem var(--bk-pad) !important; }
html, body, .stApp, [data-testid="stMain"] { max-width: 100%; overflow-x: clip; }
h1, h2, h3, h4, p, li, label { color: var(--ink); }
[data-testid="stCaptionContainer"] { color: var(--ink3) !important; }
.num, .kcard .val, .fin td, .fin th.r { font-variant-numeric: tabular-nums; }
/* верхняя полоса */
.pfnav { position: fixed; top: 0; left: 0; right: 0; z-index: 999980; height: 44px; display: flex; align-items: center; gap: 22px;
  padding: 0 var(--bk-pad); background: var(--navy); font-size: 13px; overflow-x: auto; white-space: nowrap; }
.pfnav b { color: #fff; font-size: 14px; letter-spacing: .02em; margin-right: 10px; font-weight: 600; }
.pfnav a { color: #C5CEDA !important; text-decoration: none !important; } .pfnav a:hover { color: #fff !important; }
.pfnav .pfr { margin-left: auto; font-size: 11.5px; color: #97A4B6; }
/* шапка отчёта */
.rh { background: var(--navy); color: #fff; border-radius: 6px; padding: 26px 30px 20px; margin: 4px 0 18px; border-bottom: 3px solid var(--gold); }
.rh .kick { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #C5CEDA; font-weight: 600; }
.rh .ttl { font-size: clamp(24px, 2.4vw, 34px); font-weight: 700; margin: 6px 0 12px; letter-spacing: -.01em; color: #fff; }
.rh .meta { display: flex; flex-wrap: wrap; gap: 6px 30px; font-size: 12.5px; color: #C5CEDA; }
.rh .meta b { color: #fff; font-weight: 600; }
.km { margin: 10px 0 0; padding: 0; list-style: none; } .km li { font-size: 14.5px; color: var(--ink2); line-height: 1.45; padding: 3px 0 3px 14px; border-left: 3px solid var(--navy); margin: 6px 0; }
.fin td.hm { text-align: right; font-variant-numeric: tabular-nums; }
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
.dec .big { font-size: 22px; font-weight: 700; color: var(--risk); display: block; font-variant-numeric: tabular-nums; }
.note { font-size: 12px; color: var(--ink3); line-height: 1.5; margin: 6px 0 10px; }
.pf-role { display: inline-block; font-size: 12px; color: var(--navy); background: #EEF2F7; border: 1px solid #C9D2DE; border-radius: 3px; padding: 1px 8px; margin: 2px 4px 2px 0; }
/* финансовые таблицы */
.fin { width: 100%; border-collapse: collapse; background: var(--paper); border: 1px solid var(--line); font-size: 13px; }
.fin th { background: #F3F5F8; color: var(--ink2); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; font-weight: 700; text-align: left;
  padding: 8px 12px; border-bottom: 2px solid var(--navy); } .fin th.r, .fin td.r { text-align: right; }
.fin td { padding: 8px 12px; border-bottom: 1px solid #E6EAF0; color: var(--ink); } .fin tr.tot td { font-weight: 700; background: #F3F5F8; border-top: 2px solid var(--navy); }
.fin td.risk { color: var(--risk); font-weight: 600; } .fin td.nd { color: var(--ink3); font-style: italic; }
.ok { color: #2E7D32; font-weight: 700; } .bad { color: var(--risk); font-weight: 700; }
.src { font-size: 11px; color: var(--ink3); line-height: 1.55; border-top: 1px solid var(--line); margin-top: 36px; padding-top: 12px; }
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


def kpi_cards(items):
    out = []
    for it in items:
        d_txt, d_cls = it.get("delta") or ("", "flat")
        arrow = "▲ " if d_txt.startswith("+") else ("▼ " if d_txt.startswith("−") else "")
        out.append(
            f'<div class="kcard{" risk" if it.get("risk") else ""}"><div class="lab">{html.escape(it["label"])}</div>'
            f'<div class="val{" sm" if len(str(it["value"])) >= 10 else ""}">{html.escape(str(it["value"]))}</div>'
            f'<div class="dl {d_cls}">{arrow}{html.escape(d_txt)}</div>'
            f'<div class="foot">{html.escape(it.get("foot", ""))}</div></div>')
    st.markdown(f'<div class="kgrid">{"".join(out)}</div>', unsafe_allow_html=True)


def chart(fig, key=None, height=320):
    fig.update_layout(template="pf", height=height)
    fig.update_yaxes(automargin=True)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False, "locale": "ru"}, key=key)


def fin_table(head, rows, right=(), total_last=False, cls=""):
    """HTML-таблица в банковском стиле: числа вправо, итоговая строка выделена. rows: списки готовых строк (str)."""
    th = "".join(f'<th class="{"r" if i in right else ""}">{html.escape(h)}</th>' for i, h in enumerate(head))
    body = []
    for n, r in enumerate(rows):
        tr = ' class="tot"' if total_last and n == len(rows) - 1 else ""
        cells = []
        for i, c in enumerate(r):
            style = ""
            if isinstance(c, tuple):
                c, style = c
            style = f' style="{style}"' if style else ""
            txt = c if str(c).startswith("<") else html.escape(str(c))
            cells.append(f'<td class="{"r" if i in right else ""}{" nd" if c == "Нет данных" else ""}"{style}>{txt}</td>')
        tds = "".join(cells)
        body.append(f"<tr{tr}>{tds}</tr>")
    st.markdown(f'<table class="fin {cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table>', unsafe_allow_html=True)


def sources(notes_html: str):
    st.markdown(f'<div class="src">{notes_html}</div>', unsafe_allow_html=True)
