"""Версия 2 (?view=portfolio2, далее ver=2): тот же отчёт и те же расчёты, что версия 1, в светлом минималистичном оформлении.
Версии 1 и 3 не меняются; тёмная палитра pf_ux_dark больше не включается."""
from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pf_ux_dark as UXD  # noqa: E402
import pf_ux_v2 as V2  # noqa: E402

BANNED = re.compile("(" + "|".join(["[AА]1" + "01", "power\\s*" + "bi", "app" + "le", "де" + "мо", "Нет " + "данных", "ориен" + "тир", "РН" + "В"]) + ")", re.I)
V2_MARK = "--bg:#F5F5F7"


def _app(**route):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    at.query_params.update(route)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _md(at):
    return "\n".join(m.value for m in at.markdown)


def _body(raw):
    return re.sub(r"<style>.*?</style>", " ", raw, flags=re.S)


def _table(raw):
    t = re.search(r'<table class="fin main-table">.*?</table>', raw, re.S).group(0)
    return re.sub(r'href="[^"]*"', "", t)


def _fig_bg(at):
    return [json.loads(c.proto.spec)["layout"].get("paper_bgcolor") for c in at.get("plotly_chart")]


def _num(s):
    return int(re.sub(r"\D", "", s))


def test_v2_route_light_overview_same_numbers():
    v1_at, v2_at = _app(), _app(view=UXD.VIEW)
    v1, v2 = _md(v1_at), _md(v2_at)
    assert V2_MARK in v2 and V2_MARK not in v1 and "--bg:#0f1419" not in v2               # светлая тема — только в версии 2
    assert _table(v1) == _table(v2)                                                       # полная сводка: те же цифры, что в версии 1
    body = _body(v2)
    for s in ('class="v2-hero v2-prob"', 'class="v2-hero v2-action"', "Главная проблема портфеля", "Управленческое решение", "Ответственный",
              "Финансовый эффект за 4 недели", "ЖК по финансовому риску", "Отчёт по заселению", 'id="portfolio-total"'):
        assert s in body, s
    nav = re.search(r'<span class="pf-ver".*?</a></span>', v2).group(0)
    assert 'aria-label="Версия 2" aria-current="page"' in nav and nav.index("Версия 1") < nav.index("Версия 2") < nav.index("Версия 3")
    assert 'href="/?ver=1"' in nav and re.search(r'href="/\?(ver=1&amp;view=portfolio3|view=portfolio3&amp;ver=1)"', nav)
    links = re.findall(r'href="(/\?[^"]*)" data-pf-route', body)
    assert links and all("ver=2" in h or "ver=1" in h for h in links)                     # переходы сохраняют версию 2
    assert not BANNED.search(body) and "gd-strip" not in body
    assert all(c.value.find("Демо") < 0 for c in v2_at.caption)
    # KPI версии 2 = итоги версии 1 (просрочка, дневная неустойка)
    kpi = re.findall(r'<div class="v2-kpi[^"]*"><span class="v2-label">([^<]+)</span><strong>(.*?)</strong>', body)
    vals = {k: _num(re.sub(r"<[^>]+>", "", v)) for k, v in kpi}
    assert set(vals) == {"Нарушен срок передачи, кв.", "Неустойка в день, ₽", "Передано в 2026, кв.", "Остаток 2026, кв."}
    tot = re.search(r'Неустойка в день <strong>([^<]+) ₽</strong>', _body(v1)).group(1)
    assert vals["Неустойка в день, ₽"] == _num(tot)


def test_v2_ranking_by_daily_risk_and_drill_down():
    body = _body(_md(_app(view=UXD.VIEW)))
    amounts = [_num(a) for a in re.findall(r'<div class="v2-amount">([^<]+) ₽', body)]
    assert len(amounts) == 10 and amounts == sorted(amounts, reverse=True)
    lead = re.search(r'class="v2-row v2-top".*?href="/\?([^"]+)"', body).group(1)
    key = re.search(r"card=([a-z0-9_]+)", lead).group(1)
    card = _app(ver="2", card=key)                                                        # портфель → ЖК (карточка)
    assert f'id="card-{key}"' in _md(card) and _fig_bg(card) and all(bg != UXD.CARD for bg in _fig_bg(card))
    cell = _app(ver="2", card=key, cell="decide")
    assert f'id="card-{key}"' in _md(cell) and "Что решить" in _body(_md(cell))       # «Открыть решение» → блок решения ЖК
    chess = _app(ver="2", jk=key, tab="chess")                                            # ЖК → корпус
    raw = _md(chess)
    assert V2_MARK in raw and "Шахматка" in raw and 'class="pf-path v2-crumbs"' in raw
    crumb = re.search(r'<nav class="pf-path v2-crumbs".*?</nav>', raw).group(0)
    assert crumb.index("Портфель") < crumb.index("Корпус") and "уровень 3 из 5" in crumb
    unit = re.search(r'href="/\?([^"]*unit=[^"]+)"', raw).group(1).replace("&amp;", "&").split("#")[0]
    params = dict(p.split("=", 1) for p in unit.split("&"))
    assert params.get("ver") == "2"
    from urllib.parse import unquote
    u = _app(**{k: unquote(v) for k, v in params.items()})                               # корпус → квартира → замечания
    uraw = _md(u)
    assert "Замечания по помещению" in "\n".join(x.value for x in u.subheader) and uraw.count('class="pf-path v2-crumbs"') == 1
    crumb = re.search(r'<nav class="pf-path v2-crumbs".*?</nav>', uraw).group(0)
    for lvl in ("Портфель", "Корпус", "Квартира", "Замечания · "):
        assert lvl in crumb, lvl
    assert "уровень 5 из 5" in crumb and 'class="pf-path"' not in uraw
    assert not BANNED.search(_body(uraw))


def test_v1_and_v3_unchanged():
    v1 = _app(card="bunino")
    assert _fig_bg(v1) and all(bg != UXD.CARD for bg in _fig_bg(v1)) and V2_MARK not in _md(v1)
    nav = re.search(r'<span class="pf-ver".*?</a></span>', _md(v1)).group(0)
    assert 'href="/?view=portfolio2"' in nav and 'aria-label="Версия 1" aria-current="page"' in nav
    p3 = _md(_app(view="portfolio3"))
    assert V2_MARK not in p3 and 'aria-label="Версия 3" aria-current="page"' in p3 and 'class="p2-head"' in p3


def test_dark_fig_recolors_light_palette():
    import plotly.graph_objects as go
    f = go.Figure(go.Bar(x=[1], y=[1], marker_color="#0B1F3A", text=['<span style="color:#B3261E">+5 дн.</span>']))
    f.update_layout(paper_bgcolor="#FFFFFF", font_color="#14213D")
    d = UXD.dark_fig(f)
    assert d.layout.paper_bgcolor == UXD.CARD and d.layout.font.color == UXD.TEXT and d.data[0].marker.color == UXD.BLUE


# --- изолированные тесты модуля (адаптированы из пакета version2_ux_patch/test_v2.py) ---
def _link(label, *, content=None, css="", **route):
    q = "&".join(f"{k}={v}" for k, v in route.items())
    return f'<a href="?{escape(q)}">{content if content is not None else escape(label)}</a>'


def _render(projects, totals, rows):
    return V2.render(projects, totals, rows, "20.11.2026", _link, str, lambda n: str(n / 1e6))


def test_module_ranking_and_values():
    projects = [dict(key="b", name="ЖК Б", risk_day=100, overdue_kv=3), dict(key="a", name="ЖК А", risk_day=300, overdue_kv=5)]
    rows = [dict(key="a", dec=dict(short="Мера", role="Роль", effect=1000, effect_day=40), overdue=5, t2026=10, left2026=7, remarks=2),
            dict(key="b", dec=None, overdue=3, t2026=20, left2026=8, remarks=1)]
    s = _render(projects, dict(risk_day=400, overdue_kv=8), rows)
    assert "75,0%" in s and "25,0%" in s and "300 ₽" in s and ">30<" in s and ">15<" in s
    assert s.index("ЖК А") < s.index("ЖК Б") and "Открыть решение" in s and "Роль" in s and "−0.001 млн ₽" in s
    assert "jk=a&amp;tab=chess" in s and not BANNED.search(s)


def test_module_empty_and_escape():
    assert "Срок передачи по ДДУ нигде не нарушен" in _render([], dict(risk_day=0, overdue_kv=0), [])
    s = _render([dict(key="a", name="<script>", risk_day=1, overdue_kv=1)], dict(risk_day=1, overdue_kv=1),
                [dict(key="a", dec=None, overdue=1, t2026=0, left2026=1)])
    assert "<script>" not in s and "Оценённое решение отсутствует" in s


# --- правила UX-аудита для версии 2 ---
def _lum(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _cr(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_contrast_palette_and_css_pairs():
    for fg in (V2.INK, V2.INK2, V2.MUTED, V2.RISK, V2.GOOD, V2.LINK, V2.ZERO):
        for bg in (V2.BG, V2.PAPER):
            assert _cr(fg, bg) >= 4.5, (fg, bg, round(_cr(fg, bg), 2))
    assert _cr("#FFFFFF", "#0060C0") >= 4.5 and _cr("#FFFFFF", "#7A5A00") >= 4.5      # белый текст на кнопке и метке
    css = re.sub(r"/\*.*?\*/", "", V2.CSS, flags=re.S)
    checked = 0
    dark_bg = {"aria-current": "#1D1D1F", "db-gd": "#7A5A00", "BaseButton-primary": "#0060C0", 'kind="primary"': "#0060C0"}
    for sel, block in re.findall(r"([^{}]*)\{([^{}]*)\}", css):
        fg = re.search(r"(?:^|;)color:(#[0-9A-Fa-f]{3,6})", block)
        bg = re.search(r"background(?:-color)?:(#[0-9A-Fa-f]{3,6})", block)
        if fg:
            light_text = _lum(fg.group(1)) > 0.5
            back = bg.group(1) if bg else (next(v for k, v in dark_bg.items() if k in sel) if light_text else None)
            pairs = [back] if back else [V2.PAPER, V2.BG] + (["#E8E8ED"] if ".pfnav" in sel else [])   # #E8E8ED — активный пункт меню
            for b in pairs:
                assert _cr(fg.group(1), b) >= 4.5, (block[:80], round(_cr(fg.group(1), b), 2))
            checked += 1
    assert checked > 20


def test_min_font_12px_and_no_tiny_caps():
    css = re.sub(r"/\*.*?\*/", "", V2.CSS, flags=re.S)
    sizes = [float(x) for x in re.findall(r"font-size:\s*([\d.]+)px", css)]
    assert sizes and min(sizes) >= 12
    assert "text-transform:uppercase" not in css.replace(" ", "")
    import plotly.graph_objects as go
    f = go.Figure(go.Bar(x=[1], y=[1], textfont=dict(size=10)))
    f.update_layout(legend=dict(font=dict(size=11)))
    f.update_xaxes(tickfont=dict(size=10))
    f.add_annotation(text="a", x=1, y=1, font=dict(size=10))
    V2.min_font_fig(f)
    assert f.layout.legend.font.size == 12 and f.layout.xaxis.tickfont.size == 12 and f.layout.annotations[0].font.size == 12
    assert f.data[0].textfont.size == 12 and f.data[0].x == (1,)                         # данные не меняются


def test_zero_values_neutral_grey():
    projects = [dict(key="a", name="ЖК А", risk_day=0, overdue_kv=0), dict(key="b", name="ЖК Б", risk_day=0, overdue_kv=0)]
    rows = [dict(key="a", dec=None, overdue=0, t2026=0, left2026=0, remarks=0), dict(key="b", dec=None, overdue=0, t2026=0, left2026=0, remarks=0)]
    s = _render(projects, dict(risk_day=0, overdue_kv=0), rows)
    assert "v2-critical" not in s and "v2-top" not in s and s.count('class="v2-kpi v2-zero"') == 4
    assert s.count("v2-row v2-zero") == 2 and "Срок передачи по ДДУ нигде не нарушен" in s and 'data-field="none"' in s
    # положительный эффект — зелёный, не красный; нулевой эффект — серый
    p2 = [dict(key="a", name="ЖК А", risk_day=50, overdue_kv=1)]
    r2 = [dict(key="a", dec=dict(short="Мера", role="Роль", effect=0), overdue=1, t2026=0, left2026=0, remarks=0)]
    assert 'class="v2-effect v2-zero"' in _render(p2, dict(risk_day=50, overdue_kv=1), r2)
    css = V2.CSS.replace(" ", "")
    assert ".v2-fact.v2-effect{" in css and "color:#1F6E35" in css.split(".v2-fact.v2-effect{")[1].split("}")[0]


def test_problem_fallback_when_main_metric_zero():
    projects = [dict(key="a", name="ЖК А", risk_day=0, overdue_kv=2), dict(key="b", name="ЖК Б", risk_day=0, overdue_kv=7)]
    rows = [dict(key="a", dec=None, overdue=2, t2026=1, left2026=1, remarks=3), dict(key="b", dec=None, overdue=7, t2026=1, left2026=1, remarks=1)]
    s = _render(projects, dict(risk_day=0, overdue_kv=9), rows)
    assert 'data-field="overdue_kv"' in s and "ЖК Б: больше всего квартир с нарушенным сроком" in s and "7 из 9 кв." in s
    assert "Ранжирование по квартирам с нарушенным сроком" in s and s.index("ЖК Б") < s.index("ЖК А")
    rows3 = [dict(r, overdue=0) for r in rows]
    p3 = [dict(p, overdue_kv=0) for p in projects]
    s3 = _render(p3, dict(risk_day=0, overdue_kv=0), rows3)
    assert 'data-field="remarks"' in s3 and "ЖК А: больше всего открытых замечаний" in s3


def test_headline_consistent_with_numbers_on_screen():
    body = _body(_md(_app(view=UXD.VIEW)))
    hero = re.search(r'<div class="v2-hero v2-prob" data-field="risk_day">(.*?)</div><div class="v2-hero v2-action">', body, re.S).group(1)
    lead_name = re.search(r"<h2>([^:<]+):", hero).group(1)
    big = _num(re.search(r'<span class="v2-number">([^<]+)', hero).group(1))
    rows = re.findall(r'<div class="v2-name"><a [^>]*>([^<]+)</a>.*?<div class="v2-amount">([^<]+) ₽', body, re.S)
    assert rows[0][0] == lead_name and _num(rows[0][1]) == big                        # заголовок = первая строка рейтинга
    total = sum(_num(a) for _, a in rows)
    kpi_risk = _num(re.search(r'Неустойка в день, ₽</span><strong>([^<]+)</strong>', body).group(1))
    assert abs(total - kpi_risk) <= len(rows)                                          # сумма строк = KPI (округление)
    share = float(re.search(r"<p>([\d,]+)% дневной неустойки", hero).group(1).replace(",", "."))
    assert abs(share - 100 * big / kpi_risk) < 0.06
    x, y = map(_num, re.search(r"([\d\s\xa0]+) из ([\d\s\xa0]+) кв\.", hero).groups())
    kpi_over = _num(re.search(r'Нарушен срок передачи, кв\.</span><strong><a [^>]*>([^<]+)</a>', body).group(1))
    assert 0 < x <= y == kpi_over
    widths = [float(w) for w in re.findall(r'class="v2-fill[^"]*" style="width:([\d.]+)%"', body)]
    assert widths and max(widths) <= 100 and abs(sum(widths) - 100) < 0.5
    assert body.count("v2-extra") == len(rows) - 5 and 'for="v2-more"' in body          # на телефоне ЖК после 5-го — по «Ещё»


def test_empty_chart_note_and_crumbs_module():
    import plotly.graph_objects as go
    assert V2.fig_empty(go.Figure()) and V2.fig_empty(go.Figure(go.Bar(x=[], y=[])))
    assert not V2.fig_empty(go.Figure(go.Bar(x=[1], y=[2])))
    f = go.Figure(); f.add_shape(type="rect", x0=0, x1=1, y0=0, y1=1)
    assert not V2.fig_empty(f)
    note = V2.empty_html()
    assert "За период нет записей" in note and not BANNED.search(note)
    c = V2.crumbs(_link, "ЖК А", "a", "3", "Квартира 5", remarks=2)
    assert [m for m in ("Портфель", "ЖК А", "Корпус 3", "Квартира 5", "Замечания · 2") if m in c] == ["Портфель", "ЖК А", "Корпус 3", "Квартира 5", "Замечания · 2"]
    assert "jk=a&amp;tab=chess&amp;corpus=3" in c and "уровень 5 из 5" in c
    assert "уровень 2 из 5" in V2.crumbs(_link, "ЖК А", "a")


def test_print_and_touch_css_present():
    css = V2.CSS.replace(" ", "")
    assert "@mediaprint{" in css and "min-height:44px" in css
