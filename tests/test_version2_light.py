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
    for s in ('class="v2-hero"', "Главная проблема портфеля", "Управленческое решение", "Ответственный",
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
    assert V2_MARK in raw and "Шахматка" in raw and 'class="pf-path"' in raw
    unit = re.search(r'href="/\?([^"]*unit=[^"]+)"', raw).group(1).replace("&amp;", "&").split("#")[0]
    params = dict(p.split("=", 1) for p in unit.split("&"))
    assert params.get("ver") == "2"
    from urllib.parse import unquote
    u = _app(**{k: unquote(v) for k, v in params.items()})                               # корпус → квартира → замечания
    uraw = _md(u)
    assert "Замечания по помещению" in "\n".join(x.value for x in u.subheader) and uraw.count('class="pf-path"') == 1
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
    assert "Положительный дневной риск не выявлен" in _render([], dict(risk_day=0, overdue_kv=0), [])
    s = _render([dict(key="a", name="<script>", risk_day=1, overdue_kv=1)], dict(risk_day=1, overdue_kv=1),
                [dict(key="a", dec=None, overdue=1, t2026=0, left2026=1)])
    assert "<script>" not in s and "Оценённое решение отсутствует" in s
