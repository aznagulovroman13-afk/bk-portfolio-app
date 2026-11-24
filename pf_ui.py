"""Оформление «Отчёта по заселению»: тёмная navy/metallic тема, большие цифры, без служебных меток."""
from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import pf_roles as _R
import re as _re

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
.pen-head .pen-eff, .fin td.pen-eff, .fin tr.pen-eff td { color: var(--ink3); } .fin tr.sub-tot td { font-weight: 700; border-top: 1px solid var(--navy); }
.pen-note { font-size: 12.5px; color: var(--ink2); background: #F3F5F8; border: 1px solid var(--line); padding: 9px 14px; margin: 0 0 10px; line-height: 1.5; }
.pen-years { margin-top: 12px; } .pen-years th .sub { display: block; font-size: 10px; font-weight: 400; color: var(--ink3); }
.pen-years tbody th { font-weight: 600; color: var(--ink); font-size: 12px; line-height: 1.3; } .pen-years tr.pen-eff th, .pen-years tr.pen-eff td { color: var(--ink3); font-weight: 400; padding-left: 14px; }
.pen-years tr.pen-tot th, .pen-years tr.pen-tot td { font-weight: 700; border-top: 2px solid var(--navy); } .pen-years.compact { font-size: 12px; } .pen-years.compact th, .pen-years.compact td { padding: 5px; }
.pen-basis { font-size: 12.5px; color: var(--ink2); background: #F3F5F8; border: 1px solid var(--line); padding: 8px 14px; margin: 10px 0 16px; line-height: 1.5; } .pen-basis p { margin: 3px 0; }
.pen-bridge { margin-bottom: 10px; }
details.mx > summary { cursor: pointer; list-style: none; color: var(--navy); }
details.mx > summary::-webkit-details-marker { display: none; }
details.mx > summary::before { content: "▸"; display: inline-block; width: 14px; color: #8A96A8; transition: transform .15s; }
details.mx[open] > summary::before { transform: rotate(90deg); }
details.mx-l2 { margin-top: 10px; border: 1px solid var(--line); border-left: 3px solid var(--navy); background: var(--paper); border-radius: 5px; padding: 7px 12px; }
details.mx-l2 > summary { display: flex; align-items: baseline; gap: 10px; font-size: 13px; }
details.mx-l2 > summary .mx-t { font-weight: 650; } details.mx-l2 > summary b { font-variant-numeric: tabular-nums; }
details.mx-l2 > summary .mx-s { color: var(--ink3); font-size: 12px; margin-left: auto; }
details.mx-sub { margin: -4px 0 10px; } details.mx-sub > summary { font-size: 12px; color: #5B6B82; }
details.mx-l3 { margin-top: 8px; border-top: 1px dashed #C9D1DC; padding-top: 6px; }
details.mx-l3 > summary { font-size: 12px; color: #5B6B82; font-weight: 600; letter-spacing: .02em; }
details.mx-cell > summary { display: inline; } details.mx-cell[open] > summary { display: block; }
details.mx-cell > summary::before { content: none; } details.mx-cell > summary::after { content: " ▾"; font-size: 10px; color: #8A96A8; }
.gantt-l1 { display: flex; align-items: baseline; gap: 10px; margin: 12px 0 4px; font-size: 13px; color: var(--navy);
  border: 1px solid var(--line); border-left: 3px solid var(--gold); background: var(--paper); border-radius: 5px; padding: 8px 12px; }
.gantt-l1 .mx-t { font-weight: 650; } .gantt-l1 b { font-variant-numeric: tabular-nums; color: var(--risk); } .gantt-l1 .mx-s { color: var(--ink3); font-size: 12px; margin-left: auto; }
.gantt-cause { font-size: 13px; color: var(--ink); margin: 6px 0 8px; } .gantt-causes td { font-size: 12.5px; }
.main-table td:first-child a { font-weight: 650; }
.main-table td.resp { font-size: 12px; white-space: nowrap; } .main-table td.resp .sub, .resp-table .sub { display: block; color: #5b6778; font-size: 11px; }
.card-resp { margin: 6px 0 10px; } .card-resp-ttl { font-size: 12px; font-weight: 650; color: #14243b; margin: 0 0 4px; text-transform: uppercase; letter-spacing: .04em; }
.resp-table tr.crit td:first-child b { color: #b3261e; }
.main-table a.cell { color: inherit; text-decoration: none; border-bottom: 1px dotted #9aa8bb; }
.main-table a.cell:hover { color: #23406e; border-bottom-color: #23406e; background: #eef2f8; }
.main-table td.resp a.cell { font-weight: 600; }
.cell-panel { border: 1px solid #c9d2df; border-left: 3px solid #23406e; background: #f7f9fc; padding: 10px 12px; margin: 4px 0 12px; }
.cell-ttl { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #5b6778; margin-bottom: 6px; }
.cell-ttl b { color: #14243b; } .cell-note { font-size: 12.5px; color: #3a4658; margin: 4px 0 8px; }
.cell-months th, .cell-months td { padding: 4px 6px; font-size: 12px; }
.dr-houses, .dr-apts { font-size: 12.5px; } .dr-houses { margin: 6px 0; }
.dr-row { display: grid; grid-template-columns: 1.3fr repeat(calc(var(--hcols) - 1), 1fr); gap: 6px; align-items: center; padding: 6px 8px; border-bottom: 1px solid #e1e6ee; }
.dr-row span.r { text-align: right; } .dr-row span.resp { padding-left: 14px; } .dr-row i { display: block; font-style: normal; color: #5b6778; font-size: 11px; }
.dr-h { background: #eef2f8; font-size: 11px; text-transform: uppercase; letter-spacing: .03em; color: #3a4658; }
.dr-h b { font-weight: 650; } .dr-tot { border-top: 2px solid #14243b; background: #f3f5f9; }
.dr-house > summary, .dr-apt > summary { list-style: none; cursor: pointer; } .dr-house > summary::-webkit-details-marker, .dr-apt > summary::-webkit-details-marker { display: none; }
.dr-house > summary .dr-row > span:first-child { font-weight: 650; color: #23406e; }
.dr-house > summary .dr-row > span:first-child::before { content: "▸ "; color: #8a97aa; } .dr-house[open] > summary .dr-row > span:first-child::before { content: "▾ "; }
.dr-house > summary:hover, .dr-apt > summary:hover { background: #eef2f8; }
.dr-house[open] > summary { background: #e8edf5; }
.dr-apts { margin: 0 0 8px 18px; border-left: 2px solid #c9d2df; }
.dr-apts .dr-row { grid-template-columns: repeat(var(--cols), 1fr); padding: 4px 8px; }
.dr-apt > summary .dr-row > span:first-child { color: #23406e; font-weight: 600; }
.dr-apt.ok { display: none; } .dr-all { display: none; } .dr-all:checked ~ .dr-list .dr-apt.ok { display: block; }
.dr-tog { display: inline-block; cursor: pointer; font-size: 12px; font-weight: 600; color: #23406e; padding: 4px 8px; }
.dr-tog .c { display: none; } .dr-all:checked + .dr-tog .o { display: none; } .dr-all:checked + .dr-tog .c { display: inline; }
.dr-l4 { margin: 2px 8px 8px 16px; padding: 8px 10px; background: #fff; border: 1px solid #e1e6ee; font-size: 12px; }
.dr-tl { display: flex; flex-wrap: wrap; gap: 4px 14px; list-style: none; padding: 0; margin: 0 0 6px; }
.dr-tl li span { color: #5b6778; margin-right: 4px; } .dr-tl li + li::before { content: "→ "; color: #8a97aa; }
.dr-l4 p { margin: 3px 0; } .dr-empty { color: #5b6778; font-size: 12px; }
.dr-row > span:first-child { white-space: nowrap; }
@media (max-width: 640px) {
  .dr-houses { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .dr-houses .dr-row { min-width: calc(var(--hcols) * 84px); font-size: 11.5px; gap: 4px; padding: 5px 6px; }
  .dr-apts .dr-row { min-width: calc(var(--cols) * 92px); }
  .dr-apts { margin-left: 4px; } .dr-l4 { position: sticky; left: 0; max-width: 320px; }
}
.main-table th .unit { display: block; font-weight: 500; text-transform: none; letter-spacing: 0; color: #5b6778; }
.dr-row i.dr-over { display: block; font-style: normal; color: #b3261e; font-size: 11px; }
.gd-strip { border: 1px solid #c9d2df; border-left: 4px solid #a67c00; background: #fffaf0; padding: 8px 12px; margin: 6px 0 10px; }
.gd-ttl { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #14243b; margin-bottom: 4px; }
.gd-strip ol, .gd-list { margin: 0; padding-left: 18px; } .gd-strip li { margin: 3px 0; font-size: 13px; }
.gd-strip li > span { margin-left: 10px; color: #3a4658; font-size: 12px; } .gd-strip .gd-num { color: #14243b; font-weight: 650; }
.gd-note { font-size: 11px; color: #5b6778; margin-top: 4px; }
.main-table td.decide { min-width: 170px; font-size: 12px; } .main-table td.decide .sub { display: block; color: #3a4658; font-size: 11px; }
.main-table td.decide a.cell { border-bottom: none; } .main-table td.decide a.cell b { border-bottom: 1px dotted #9aa8bb; }
.dec-block { border: 1px solid #c9d2df; border-left: 4px solid #23406e; background: #f7f9fc; padding: 10px 12px; margin: 2px 0 12px; }
.db-ttl { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: .04em; color: #5b6778; }
.db-gd { margin-left: 8px; padding: 1px 6px; background: #a67c00; color: #fff; border-radius: 2px; font-size: 10px; letter-spacing: .03em; }
.db-main { font-size: 16px; font-weight: 700; color: #14243b; margin: 4px 0 2px; }
.db-desc { font-size: 12px; color: #3a4658; margin: 0 0 8px; line-height: 1.4; }
.db-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 16px; }
.db-grid > div { font-size: 13px; } .db-grid .db-l { display: block; font-size: 11px; color: #5b6778; text-transform: uppercase; letter-spacing: .03em; }
.db-grid b { display: block; font-size: 15px; color: #14243b; } .db-grid .sub { display: block; font-size: 11px; color: #5b6778; }
.db-why { font-size: 12.5px; color: #3a4658; margin: 4px 0; line-height: 1.45; }
abbr[title] { text-decoration: underline dotted #8a97aa; cursor: help; }
@media (max-width: 640px) { .db-grid { grid-template-columns: 1fr 1fr; } dl.card-metrics { grid-template-columns: 1fr 1fr !important; } dl.card-metrics dt { word-break: normal; hyphens: auto; } .gd-strip li > span { display: block; margin-left: 0; } }
.mt-total { display: flex; flex-wrap: wrap; align-items: stretch; gap: 6px 22px; background: #F2F5F9; border: 1px solid #C9D2DF;
  border-left: 4px solid #0B1F3A; border-radius: 4px; padding: 8px 14px; margin: 6px 0 8px; }
.mt-total .tl { display: block; font-size: 10.5px; color: #596577; text-transform: uppercase; letter-spacing: .04em; font-weight: 600; white-space: nowrap; }
.mt-total b { display: block; font-size: 16px; color: #14213D; font-variant-numeric: tabular-nums; white-space: nowrap; }
.mt-total .tn b { font-size: 15px; } .mt-total .tgi { display: flex; gap: 14px; }
.mt-total .tgi span { display: flex; align-items: baseline; gap: 5px; font-size: 16px; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }
.mt-total .tgi i { font-style: normal; font-size: 11px; font-weight: 400; color: #596577; }
.mt-total a.cell { color: #14213D !important; }
@media (max-width: 640px) { .mt-total { gap: 6px 14px; padding: 8px 10px; } .mt-total b, .mt-total .tgi span { font-size: 14px; }
  .mt-total .tgi { gap: 10px; flex-wrap: wrap; } .mt-total .tn { flex-basis: 100%; } }
/* сводка: иерархия и выборочные акценты */
.main-table th { font-size: 12.5px; letter-spacing: .03em; color: #14213D; padding-top: 10px; padding-bottom: 10px; }
.main-table thead tr:nth-child(2) th { font-size: 12px; color: #3A4658; }
.main-table th .unit { font-size: 11.5px; }
.main-table td { font-size: 13.5px; } .main-table td.r { white-space: nowrap; }
.main-table td .u, .mt-total .u { color: #7A8597; font-size: .78em; font-weight: 400; }
.main-table td.key { font-weight: 700; font-size: 14.5px; }
.main-table td.hl-bad a.cell, .mt-total .hl-bad a.cell { color: #A52C28 !important; font-weight: 700; border-bottom-color: #E2B3B0; }
.main-table td.hl-good a.cell, .mt-total .hl-good a.cell { color: #2F6B3A !important; font-weight: 700; border-bottom-color: #B7D3BC; }
.mt-total .ti.key { border-left: 1px solid #C9D2DF; padding-left: 14px; } .mt-total .ti.key b { font-size: 22px; line-height: 1.1; }
.mt-total .tl { font-size: 11px; }
.mt-legend { font-size: 12px; } .lg-bad { color: #A52C28; } .lg-good { color: #2F6B3A; }
@media (max-width: 640px) { .main-table th { font-size: 11.5px; } .main-table td { font-size: 12.5px; } .mt-total .ti.key b { font-size: 19px; }
  .mt-total .ti.key { border-left: none; padding-left: 0; } }
/* сводка — первый уровень: крупная плашка итогов; таблица по ЖК — второй уровень */
.mt-total { gap: 14px 30px; padding: 16px 22px 18px; margin: 10px 0 18px; border-left-width: 6px; background: #EEF2F7;
  box-shadow: 0 1px 2px rgba(11,31,58,.06); }
.mt-total .tl { font-size: 12px; letter-spacing: .05em; margin-bottom: 4px; color: #4A5568; }
.mt-total b, .mt-total .tgi span { font-size: 26px; line-height: 1.15; font-weight: 700; }
.mt-total .tgi { gap: 18px; } .mt-total .tgi i { font-size: 12px; }
.mt-total .tn b { font-size: 22px; } .mt-total .tn .tl { font-size: 12px; }
.mt-total .ti.key b { font-size: 34px; }
.mt-total .ti[data-k="decide"] b, .mt-total .ti[data-k="resp"] b { font-size: 18px; padding-top: 6px; }
.mt-l2 { display: flex; align-items: baseline; gap: 12px; margin: 4px 0 6px; padding-bottom: 4px; border-bottom: 1px solid #C9D2DF; }
.mt-l2 b { font-size: 15px; color: #14213D; } .mt-l2 span { font-size: 12px; color: #596577; }
@media (max-width: 640px) { .mt-total { padding: 12px 12px 14px; gap: 10px 18px; }
  .mt-total b, .mt-total .tgi span { font-size: 19px; } .mt-total .ti.key b { font-size: 26px; } .mt-total .tn b { font-size: 18px; }
  .mt-total .ti[data-k="decide"] b, .mt-total .ti[data-k="resp"] b { font-size: 15px; } .mt-l2 { flex-direction: column; gap: 2px; } }
/* динамика: сетка мини-графиков под сводкой */
.main-table td.jk { min-width: 190px; }
.mt-dy { display: flex; align-items: center; gap: 8px; margin-top: 4px; }
.mt-dy .dy-s svg { display: block; width: 92px; height: auto; }
.mt-dy .dy-w { display: flex; flex-direction: column; line-height: 1.25; }
.mt-dy .sub { font-size: 11px; color: #596577; white-space: nowrap; } .mt-dy .sub.wr { color: #A52C28; } .mt-dy .sub.improved { color: #2F6B3A; }
.mt-dy .dy-t { font-size: 11px; color: #596577; white-space: nowrap; } .mt-dy .dy-t.hl-bad { color: #A52C28; font-weight: 650; } .mt-dy .dy-t.hl-good { color: #2F6B3A; font-weight: 600; }
.mt-total .ti.tdy .mt-dy { margin-top: 6px; } .mt-total .ti.tdy .dy-s svg { width: 120px; }
.pt3 td .mt-dy { margin-top: 3px; }
@media (max-width: 640px) { .main-table td.jk { min-width: 150px; } .mt-dy { gap: 6px; } .mt-dy .dy-s svg { width: 64px; } .mt-dy .sub, .mt-dy .dy-t { font-size: 10.5px; } }
@media (max-width: 640px) {
  .main-port .tw { overflow-x: visible; }
  .main-table, .main-table tbody { display: block; width: 100%; min-width: 0 !important; }
  .main-table thead { display: none; }
  .main-table tbody tr { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; padding: 10px 4px; border-bottom: 1px solid #C9D2DF; }
  .main-table tbody tr.mt-hidden { display: none; }
  .main-table tbody td { display: block; padding: 0; border: none !important; text-align: left; min-width: 0 !important; white-space: normal; }
  .main-table tbody td.jk, .main-table tbody td.decide, .main-table tbody td.resp { grid-column: 1 / -1; }
  .main-table tbody td[data-l]::before { content: attr(data-l); display: block; font-size: 10.5px; color: #596577; letter-spacing: .03em; text-transform: uppercase; font-weight: 500; }
  .main-table tbody tr.mt-toggle { display: block; padding: 0; } .main-table tbody tr.mt-toggle td { display: block; }
  .main-table td.resp { white-space: normal; } .main-table tbody td.r { text-align: left; }
}
@media (max-width: 640px) { .mt-more:checked ~ .tw .main-table tr.mt-hidden { display: grid; } }
.mt-more { display: none; } .main-table tr.mt-hidden { display: none; } .mt-more:checked ~ .tw .main-table tr.mt-hidden { display: table-row; }
.main-table tr.mt-toggle td { padding: 0; border-bottom: 1px solid #d5dbe5; }
.main-table tr.mt-toggle label { display: block; cursor: pointer; padding: 7px 10px; color: #23406e; font-size: 12px; font-weight: 600; letter-spacing: .02em; }
.main-table tr.mt-toggle label:hover { background: #eef2f8; }
.mt-close { display: none; } .mt-more:checked ~ .tw .mt-open { display: none; } .mt-more:checked ~ .tw .mt-close { display: inline; } .main-table th.grp { text-align: center; }
.card-metrics { grid-template-columns: repeat(5, minmax(0, 1fr)) !important; } .card-anchor { scroll-margin-top: 60px; }
.card-decisions { margin: 6px 0; padding-left: 18px; font-size: 13px; } .card-decisions .sub { display: block; color: var(--ink3); font-size: 12px; }
.card-open { margin: 8px 0 0; font-size: 13px; }
.fin th.tip { text-decoration: underline dotted #9AA6B8; text-underline-offset: 3px; cursor: help; } .fin th .sub { display: block; font-size: 10px; text-transform: none; letter-spacing: 0; color: var(--ink3); font-weight: 400; }
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
/* ===== Отчёт по заселению: дизайн на всю ширину (сетка 8 px) ===== */
:root { --bk-pad: clamp(16px, 2.2vw, 32px); --r8: 8px; --sh1: 0 1px 2px rgba(11,31,58,.06), 0 4px 16px rgba(11,31,58,.05); --row: #E6EAF0; --hov: #F5F8FC; }
.stMainBlockContainer, .block-container { max-width: 100% !important; padding: 64px var(--bk-pad) 64px var(--bk-pad) !important; }
.rh { border-radius: var(--r8); padding: 24px 32px; margin: 0 0 24px; box-shadow: var(--sh1); }
.main-port .exec-date { margin: 0 0 8px; font-size: 13px; color: var(--ink3); }
/* плашка «Итого» — первый уровень, сетка 12 колонок на всю ширину */
.mt-total { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 24px 32px; align-items: start;
  background: var(--paper); border: 1px solid var(--line); border-left: 6px solid var(--navy); border-radius: var(--r8);
  box-shadow: var(--sh1); padding: 24px 32px; margin: 8px 0 32px; }
.mt-total > * { grid-column: span 2; min-width: 0; }
.mt-total > .tg { grid-column: span 6; } .mt-total > [data-k="decide"], .mt-total > [data-k="resp"] { grid-column: span 3; }
.mt-total > .tg, .mt-total > [data-k="decide"], .mt-total > [data-k="resp"] { border-top: 1px solid var(--row); padding-top: 16px; }
.mt-total .ti.key { border-left: none; padding-left: 0; }
.mt-total .tl { font-size: 12px; letter-spacing: .06em; color: var(--ink3); margin-bottom: 8px; }
.mt-total b, .mt-total .tgi span { font-size: 32px; line-height: 1.1; letter-spacing: -.01em; }
.mt-total .ti.key b { font-size: 40px; } .mt-total .tn b { font-size: 24px; }
.mt-total .tgi { gap: 32px; } .mt-total .tgi span { font-size: 28px; }
.mt-total .ti[data-k="decide"] b, .mt-total .ti[data-k="resp"] b { font-size: 18px; padding-top: 0; }
.mt-total .tdy .mt-dy { margin-top: 0; } .mt-total .tdy .dy-s svg { width: 112px; height: 32px; }
.mt-total .tdy .sub { font-size: 13px; } .mt-total .tdy .dy-t { font-size: 12px; }
@media (max-width: 1180px) { .mt-total { grid-template-columns: repeat(6, minmax(0, 1fr)); } .mt-total > .tg { grid-column: span 6; } }
@media (min-width: 641px) { .pfnav { padding-left: 56px; } }
/* второй уровень — таблица по ЖК */
.main-port .mt-l2 { margin: 0 0 16px; padding-bottom: 8px; gap: 16px; border-bottom: 2px solid var(--navy); }
.main-port .mt-l2 b { font-size: 18px; letter-spacing: -.005em; } .main-port .mt-l2 span { font-size: 13px; }
.main-port .tw, .pt3-wrap { border-radius: var(--r8); box-shadow: var(--sh1); }
.main-table, .fin.pt3 { border: 1px solid var(--line); border-radius: var(--r8); border-collapse: separate; border-spacing: 0; overflow: hidden; }
.main-table th, .fin.pt3 th { padding: 12px 16px; font-size: 12px; letter-spacing: .05em; color: var(--ink); background: #F3F5F8; border-bottom: 1px solid var(--line); vertical-align: bottom; }
.main-table thead tr:first-child th.grp { border-bottom: 1px solid var(--row); }
.main-table td, .fin.pt3 td { padding: 16px; border-bottom: 1px solid var(--row); vertical-align: middle; font-variant-numeric: tabular-nums; }
.main-table td.r, .fin.pt3 td.r { text-align: right; } .main-table td.r .u { margin-left: 2px; }
.main-table tbody tr:last-child td, .fin.pt3 tbody tr:last-child td { border-bottom: none; }
.main-table tbody tr:not(.mt-toggle):hover td, .fin.pt3 tbody tr:hover td { background: var(--hov); }
.main-table td.sep, .main-table th.sep { border-left: 1px solid var(--row); }
.main-table td.jk { min-width: 240px; } .main-table td.jk > a { font-size: 14.5px; }
.main-table td.key { font-size: 16px; } .main-table td { font-size: 14px; }
.main-table td.decide { min-width: 220px; font-size: 13px; } .main-table td.resp { font-size: 13px; }
.mt-dy { gap: 12px; margin-top: 8px; } .mt-dy .dy-s svg { width: 96px; height: 28px; }
.fin.pt3 td .mt-dy { margin-top: 8px; }
.mt-legend { margin: 16px 0 24px; font-size: 12.5px; }
/* карточки и раскрытия — единые скругления и тени */
div[data-testid="stExpander"] details { border-radius: var(--r8); box-shadow: var(--sh1); }
.cell-panel, .dec-block, details.mx-l2, .gantt-l1, .pen-basis { border-radius: var(--r8); }
.cell-panel, .dec-block { box-shadow: var(--sh1); padding: 16px 24px; margin: 8px 0 16px; }
div[data-testid="stPlotlyChart"], div[data-testid="stDataFrame"] { border-radius: var(--r8); box-shadow: var(--sh1); }
@media (max-width: 640px) { .stMainBlockContainer, .block-container { padding: 56px 16px 48px !important; }
  .mt-total { grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; } .mt-total > * { grid-column: span 1; }
  .mt-total > .tn, .mt-total > .key, .mt-total > .tdy, .mt-total > .tg { grid-column: span 2; }
  .mt-total > [data-k="decide"], .mt-total > [data-k="resp"] { grid-column: span 1; }
  .mt-total b, .mt-total .tgi span { font-size: 22px; } .mt-total .ti.key b { font-size: 28px; }
  .main-table, .fin.pt3 { border-collapse: collapse; } .main-table td, .main-table th { padding: 0; } .main-table tbody tr { padding: 12px 8px; } }
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
                + (f'<details class="mx mx-sub"><summary>Подробнее</summary><div class="secsub">{sub}</div></details>' if sub else ""),
                unsafe_allow_html=True)


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
    import pf_ux_dark as _UXD                  # версия 3: тот же график в тёмной палитре (флаг текущего прогона)
    if _UXD.active():
        fig = _UXD.dark_fig(fig)
    import pf_ux_v2 as _V2                     # версия 2: пустой график — подпись вместо пустой рамки (флаг текущего прогона)
    if _V2.active() and _V2.fig_empty(fig):
        st.markdown(_V2.empty_html(), unsafe_allow_html=True)
        return
    if _V2.active():
        fig = _V2.min_font_fig(fig)
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False, "locale": "ru", "scrollZoom": False, "doubleClick": False, "responsive": True}, key=key)


def fin_table(head, rows, right=(), total_last=False, cls="", hide=(), tips=None):
    """HTML-таблица в банковском стиле: числа вправо, итоговая строка выделена, первая колонка закреплена при прокрутке.
    rows: списки готовых ячеек (str, (str, style) или HTML, начинающийся с «<»). hide — номера колонок, скрываемых на узком экране."""
    hm = lambda i: " hm" if i in hide else ""
    tips = tips or {}
    tip = lambda i: f' title="{html.escape(tips[i])}"' if i in tips else ""
    th = "".join(f'<th class="{"r" if i in right else ""}{hm(i)}{" tip" if i in tips else ""}"{tip(i)}>{html.escape(h)}</th>' for i, h in enumerate(head))
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
    st.markdown(gloss(f'<div class="tw"><table class="fin {cls}"><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'), unsafe_allow_html=True)


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


_GLOSS_RE = _re.compile(r"(?<![\w])(" + "|".join(_re.escape(k) for k in sorted(_R.GLOSSARY, key=len, reverse=True)) + r")(?![\w])")


def gloss(markup: str) -> str:
    """Подсказки к сокращениям (РВЭ, АПП, ОЗ, ч. 6 ст. 8 …): только в тексте, не в атрибутах и не внутри <abbr>, <style>, <script>."""
    out, skip = [], 0
    for part in _re.split(r"(<[^>]+>)", markup):
        if part.startswith("<"):
            tag = part[1:].split()[0].rstrip(">").lower() if len(part) > 1 else ""
            if tag in ("abbr", "style", "script", "summary"):
                skip += 1
            elif tag in ("/abbr", "/style", "/script", "/summary"):
                skip = max(0, skip - 1)
            out.append(part)
        elif skip or not part.strip():
            out.append(part)
        else:
            out.append(_GLOSS_RE.sub(lambda m: f'<abbr title="{html.escape(_R.GLOSSARY[m.group(1)])}">{m.group(1)}</abbr>', part))
    return "".join(out)
