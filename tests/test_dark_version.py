"""Версия 2 (?view=portfolio2, далее ver=2): тот же отчёт, что версия 1, в тёмной теме; версии 1 и 3 не меняются."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pf_ux_dark as UXD  # noqa: E402

BANNED = re.compile("(" + "|".join(["[AА]1" + "01", "power\\s*" + "bi", "app" + "le", "де" + "мо-?данн[а-я]* по", "Нет " + "данных", "ориен" + "тир", "РН" + "В"]) + ")", re.I)


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


def test_v3_route_same_report_dark_theme():
    v1, v3 = _md(_app()), _md(_app(view=UXD.VIEW))
    assert "--bg:#0f1419" in v3 and "--bg:#0f1419" not in v1                    # тема — только в версии 3
    assert _table(v1) == _table(v3)                                             # те же цифры и строки, что в версии 1
    for s in ('id="portfolio-total"', "Раскрытие по ЖК", "Отчёт по заселению"):
        assert s in v3
    nav = re.search(r'<span class="pf-ver".*?</a></span>', v3).group(0)
    assert 'aria-label="Версия 2" aria-current="page"' in nav and nav.index("Версия 1") < nav.index("Версия 2") < nav.index("Версия 3")
    assert 'href="/?ver=1"' in nav and re.search(r'href="/\?(ver=1&amp;view=portfolio3|view=portfolio3&amp;ver=1)"', nav)    # возврат в версии 1 и 3
    links = re.findall(r'href="(/\?[^"]*)" data-pf-route', _body(v3))
    assert links and all("ver=2" in h or "ver=1" in h for h in links)                # переходы сохраняют версию 2
    assert not BANNED.search(_body(v3)) and "gd-strip" not in _body(v3)


def test_v3_drill_and_charts_are_dark_v1_unchanged():
    at = _app(ver="2", jk="bunino")
    raw = _md(at)
    assert "--bg:#0f1419" in raw and "Шахматка" in raw
    assert _fig_bg(at) and all(bg == UXD.CARD for bg in _fig_bg(at))            # Plotly — тёмный фон
    card = _app(ver="2", card="bunino", cell="overdue")
    assert 'id="cell-bunino-overdue"' in _md(card) and _fig_bg(card) and all(bg == UXD.CARD for bg in _fig_bg(card))
    v1 = _app(card="bunino")                                                    # после версии 2 версия 1 — светлая
    assert _fig_bg(v1) and all(bg != UXD.CARD for bg in _fig_bg(v1)) and "--bg:#0f1419" not in _md(v1)
    nav = re.search(r'<span class="pf-ver".*?</a></span>', _md(v1)).group(0)
    assert 'href="/?view=portfolio2"' in nav and 'aria-label="Версия 1" aria-current="page"' in nav
    p3 = _md(_app(view="portfolio3"))                                          # бывший «Портфель 2» — светлый, как раньше
    assert "--bg:#0f1419" not in p3 and 'aria-label="Версия 3" aria-current="page"' in p3 and 'class="p2-head"' in p3


def test_dark_fig_recolors_light_palette():
    import plotly.graph_objects as go
    f = go.Figure(go.Bar(x=[1], y=[1], marker_color="#0B1F3A", text=['<span style="color:#B3261E">+5 дн.</span>']))
    f.update_layout(paper_bgcolor="#FFFFFF", font_color="#14213D")
    d = UXD.dark_fig(f)
    assert d.layout.paper_bgcolor == UXD.CARD and d.layout.font.color == UXD.TEXT and d.data[0].marker.color == UXD.BLUE
    assert "#f87171" in d.data[0].text[0]
    assert UXD.recolor(".a{color:#14213D;background:#fff}") == ".a{color:#e8eef7;background:#1a2332}"
