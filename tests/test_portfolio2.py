"""«Портфель 2» (?view=portfolio2): логика выбора мер и затрат из архива, экран, переключатель версий, переходы до квартиры и замечаний."""
from __future__ import annotations

import html as H
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pf_data  # noqa: E402
import pf_portfolio2 as P2  # noqa: E402

BANNED = ["де" + "мо", "Де" + "мо", "Нет " + "данных", "нет " + "данных", "ориен" + "тир", "услов" + "н", "модел" + "ьн", "РН" + "В",
          "А1" + "01", "A1" + "01", "None", "nan ", "Требует " + "уточнения"]
DATE = re.compile(r"\b\d{1,2}\.\d{2}\.\d{4}\b")


def measure(key="unilateral", effect=2_000_000):
    return {"key": key, "effect": effect, "effect_day": effect / 14, "roles": ["Юридический департамент"], "pool": "expired",
            "needs_gd": True, "short3": key, "title": key}


def test_archive_rules_repeat_measure_and_unknown_budget():
    """Тест из архива (адаптирован): мера выбирается в каждом ЖК независимо и может повторяться; затраты всегда в рублях;
    выбор — по наибольшему эффекту после затрат, убыточная мера не выбирается при наличии плюсовой."""
    for _ in range(3):
        p = {"cands": [measure(effect=2_000_000), measure("realloc", effect=500_000)], "reasons": {"expired": {"n": 100, "risk": 200_000}}}
        assert P2.best_decision(p)["measure"]["key"] == "unilateral"
    p = {"reasons": {"expired": {"n": 100, "risk": 200_000}}}
    cost, why = P2.budget_estimate(p, measure(effect=1_400_000))
    assert cost == 900_000 and "тариф" in why, (cost, why)
    cost, why = P2.budget_estimate(p, measure("unknown"))
    assert cost > 0 and "тариф" in why                                    # без тарифа — средняя ставка, не пусто
    assert P2.fmt_mln(-110_000) == "−0,11 млн ₽"
    # убыточная по затратам мера (большой эффект, ещё большие затраты) уступает плюсовой
    loss = dict(measure("crew", effect=370_000), cost=480_000)
    plus = measure("calls", effect=240_000)
    d = P2.best_decision({"cands": [loss, plus], "reasons": {"expired": {"n": 100, "risk": 200_000}}})
    assert d["measure"]["key"] == "calls" and d["net"] > 0
    d = P2.best_decision({"cands": [measure("unknown", effect=10)], "reasons": {}, "overdue_kv": 5, "risk_day": 10_000})
    assert d["cost"] > 0 and d["net"] == d["effect"] - d["cost"]
    for key in ("notify", "called", "reply", "noshow", "edo", "batch", "compensation", "escalation", "sla", "sprint", "cross", "crew",
                "unilateral", "realloc", "onestop", "brigades", "calls"):
        assert P2.RATES[key] > 0, key
    assert P2.day_week(1_000_000) == "1,00 / 7,00"


def _app(**route):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    at.query_params.update(route)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _md(at):
    return "\n".join(m.value for m in at.markdown)


def _text(raw):
    raw = re.sub(r"<style>.*?</style>", " ", raw, flags=re.S)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", raw)))


def test_portfolio2_screen_rules_and_reconciliation():
    at = _app(view="portfolio2")
    raw = _md(at)
    t = _text(raw) + " " + " ".join(c.value for c in at.caption) + " " + " ".join(e.label for e in at.expander)
    assert not [w for w in BANNED if w in t], [w for w in BANNED if w in t]
    assert "Портфель 2" in t and "Сводка по ЖК" not in t
    assert 'class="p2-ok"' in raw and 'class="p2-bad">Расхождение' not in raw            # сверка итогов сходится
    assert "не подтвержден" in t and "расчётная оценка" in t                 # суммы не выдаются за факт
    names = dict(pf_data.PROJECTS)
    table = raw.split('id="p2-table"', 1)[1].split("</table>", 1)[0]
    for key in names:
        assert f"view=portfolio2&amp;card={key}" in table                    # каждый ЖК ведёт в карточку
    assert table.count("<tr") == len(names) + 2 and "не суммируются" in table
    assert "не оценено" not in t and "Готовы" not in t and "готовы к передаче" not in t
    head = table.split("</thead>", 1)[0]
    assert "день / нед." in head and "Готовы" not in head
    tot = table.split('<tr class="tot">', 1)[1].split("</tr>", 1)[0]
    assert tot.count("<td") == 5 and 'colspan="5"' in tot and "<td></td>" not in table and '"></td>' not in table
    for row in re.findall(r"<tr><td>.*?</tr>", table):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row)
        assert len(cells) == 9 and all(_text(c).strip() for c in cells), row
        assert re.fullmatch(r"\d+,\d\d / \d+,\d\d", _text(cells[2]).strip()), cells[2]
        assert "−" not in cells[8]                                               # эффект после затрат не отрицательный
    kpis = raw.split('class="p2-kpis"', 1)[1].split('class="p2-focus"', 1)[0]
    assert kpis.count('class="p2-kpi"') == 3 and "Неустойка за день / неделю" in kpis and re.search(r"\d,\d\d / \d+,\d млн ₽", kpis)
    focus = raw.split('class="p2-focus"', 1)[1].split("</div>", 1)[0]
    assert "₽/день / " in focus and "млн ₽/нед." in focus and "готовы к передаче" not in focus
    for sec in ("p2-decisions", "p2-orders"):
        part = raw.split(f'id="{sec}"', 1)[1].split("</table>", 1)[0]
        assert not DATE.search(_text(part)), sec                              # без дат у решений и поручений
    import pf_roles as R
    orders = raw.split('id="p2-orders"', 1)[1].split("</table>", 1)[0]
    roles = re.findall(r"<tr><td[^>]*>([^<]+)</td>", orders)
    assert roles and all(r in R.ROLES for r in roles)


def test_version_switch_in_both_menus():
    for route, cur in (({}, "Версия 1"), ({"view": "portfolio2"}, "Версия 2"), ({"jk": "bunino"}, "Версия 1")):
        raw = _md(_app(**route))
        nav = re.search(r'<span class="pf-ver".*?</a></span>', raw).group(0)
        assert 'href="/"' in nav and 'href="/?view=portfolio2"' in nav
        assert f'aria-label="{cur}" aria-current="page"' in nav, (route, nav)
    assert "<b>ОТЧЁТ ПО ЗАСЕЛЕНИЮ</b>" not in _md(_app())


def test_portfolio2_card_drill_to_house_apartment_and_remarks():
    """Портфель 2 → ЖК (карточка) → корпус → квартира → замечания; общие страницы ЖК открываются по ссылкам карточки."""
    at = _app(view="portfolio2", card="bunino")
    raw = _md(at)
    assert 'id="p2-card-bunino"' in raw and at.selectbox(key="p2_card").value == "bunino"
    assert raw.count('<details class="dr-house') == 7 and "dr-apt" in raw and "dr-l4" in raw
    m = re.search(r'href="/\?jk=bunino&amp;tab=chess&amp;corpus=([^&]+)&amp;unit=([^&"#]+)#drill"', raw)
    assert m, "нет ссылки на квартиру с замечаниями"
    corpus, unit = m.group(1), m.group(2)
    assert f'jk=bunino&amp;tab=chess&amp;corpus={corpus}#drill' in raw and 'jk=bunino&amp;tab=remarks#drill' in raw
    at.selectbox(key="p2_card").set_value("zen").run()
    assert not at.exception and 'id="p2-card-zen"' in _md(at)
    house = _app(jk="bunino", tab="chess", corpus=corpus)
    assert "Корпус " + corpus in _text(_md(house))
    flat = _app(jk="bunino", tab="chess", corpus=corpus, unit=unit)
    assert any("Замечания по помещению" in s.value for s in flat.subheader)
    assert flat.get("markdown") and "Вид работ" in _md(flat)
    rem = _app(jk="bunino", tab="remarks")
    assert "Открытых замечаний" in _md(rem)


def test_original_summary_unchanged_and_p2_does_not_leak():
    raw = _md(_app())
    assert "Сводка по ЖК" in raw and 'class="fin main-table"' in raw and 'class="p2-head"' not in raw
