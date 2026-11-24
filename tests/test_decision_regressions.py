import re
from pathlib import Path

import pandas as pd
import pytest

import pf_core as C
import pf_data
import pf_decide as DC
import pf_demo
import pf_model as PF


@pytest.mark.parametrize(("overdue", "pace", "weeks"), [(1008, 92, 1008 / 92), (25, 10, 2.5), (20, 10, 2), (0, 0, 0)])
def test_forecast_keeps_partial_final_week(overdue, pace, weeks):
    result = DC.simulate(overdue, pace, 100)
    assert result["weeks"] == pytest.approx(weeks)
    assert result["path"][-1][1] == 0
    assert result["accrued"] == pytest.approx(7 * 100 * overdue * weeks / 2)


def test_main_decision_is_never_repeated_across_projects():
    common = dict(key="batch", pool="queue", family="capacity", effect=100)
    first = dict(key="calls", pool="silent", family="comms", effect=10)
    second = dict(key="notify", pool="silent", family="legal", effect=20)
    assert DC.pick([first, common])[0] is common
    assert DC.pick([first, common], used={"batch"})[0] is first
    assert DC.pick([common, second, first], used={"batch", "notify"})[0] is first
    assert [c["key"] for c in DC.pick([common, second], used={"calls"})] == ["batch", "notify"]


def test_ready_forecast_subtracts_new_overdue_from_gross_handover():
    project = dict(overdue_kv=600, burn_pace=12, target_burn=16, risk_day=60_000, ready=272, inflow=6)
    result = DC.forecast(project)
    assert result["base"]["path"][1][1] == 588
    assert result["scn"]["path"][1][1] == 538  # 600 − 68 передано + 6 новых просрочек
    assert result["scn"]["path"][4][1] == 352
    assert result["scn"]["path"][5][1] == 340  # после сценария снова чистый темп 12
    assert DC.forecast(dict(project, ready=20))["saving"] == 0


def test_missing_dates_and_missed_appointments_have_separate_groups():
    visits = pd.DataFrame({
        "Исходный статус": "Открыта к передаче",
        "Готовность подтверждена": True,
        "Замечаний открыто": 0,
        "Просрочка ДДУ": C.NT_OVERDUE,
        "Тип объекта": "Квартира",
        "Ставка ЦБ на срок ДДУ, %": 15.0,
        "Статус записи собственника": ["Завершено", "Отменено", "Не состоялось", "Запланировано",
                                          "Запланировано", "Запланировано", "Запланировано", None, None, None],
        "Запись через, дн.": pd.array([None, None, None, 3, 12, None, -2, None, None, None], dtype="Float64"),
        "Официальный вызов, дн. назад": pd.array([None, None, None, None, None, None, None, 10, 80, -1], dtype="Float64"),
    })
    groups = DC.classify_ready(visits, 10_000_000)
    assert {key: value["n"] for key, value in groups.items()} == dict(
        booked=1, queue=1, refused=1, missed=2, date_check=2, called=1, expired=1, silent=1)
    assert sum(group["risk"] for group in groups.values()) == pytest.approx(100_000)


def test_projects_use_a_reproducible_demo_snapshot():
    projects = pf_demo.build(pf_data.PROJECTS)
    assert len(projects) == 10
    for project in projects.values():
        assert project["units"]["Объект"].is_unique and not project["units"]["Объект"].str.contains("DEMO", case=False).any()
        assert set(project["contractors"]["Подрядчик"]) <= {name for names in pf_demo.CONTRACTORS.values() for name in names}
        assert project["units"]["Замечаний открыто"].sum() == project["remarks"]["n"].sum()
    pd.testing.assert_frame_equal(projects["bunino"]["units"], pf_demo.build(pf_data.PROJECTS)["bunino"]["units"])


def test_report_auth_and_first_screen_on_synthetic_data(monkeypatch, request):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()
    request.addfinalizer(st.cache_data.clear)

    data = {}
    for key, name in pf_data.PROJECTS:
        units = pd.DataFrame({
            "Объект": [f"{key}-1-{n}" for n in range(1, 9)], "Квартира": range(1, 9),
            "Корпус": "1", "Секция": "1", "Этаж": 1, "Тип объекта": "Квартира",
            "Исходный статус": ["Открыта к передаче"] * 5 + ["Принята"] * 3,
            "Готовность подтверждена": [True] * 4 + [False] * 4,
            "Просрочка ДДУ": [C.NT_OVERDUE] * 5 + [C.LATE] * 3,
            "Просрочка ДДУ факт, дн.": 40, "Срок по ДДУ": pd.Timestamp("2026-08-01"),
            "Дата принятия собственником": pd.to_datetime(
                [None] * 5 + ["2026-10-21", "2026-10-28", "2026-11-04" if key == "zen" else "2026-11-06"]),
            "Результат передачи": [None] * 5 + (["Без замечаний"] * 3 if key == "zen" else ["С замечаниями", "Без замечаний", None]),
            "Коэф. неустойки на 1 ₽ цены (верх)": 0.04, "Коэф. неустойки на 1 ₽ цены (низ)": 0.03,
            "Ставка ЦБ на срок ДДУ, %": 15., "Мот. отказ / снятие готовности": False,
            "Плановая дата ключей в ОЗ": pd.NaT,
            "Статус записи собственника": "Запланировано", "Запись через, дн.": 12,
            "Официальный вызов, дн. назад": float("nan"),
            "Замечаний открыто": [0] * 4 + [1] + [0] * 3,
            "Критических": [0] * 4 + [1] + [0] * 3, "Просрочено (регл)": [0] * 4 + [1] + [0] * 3,
        })
        remarks = pd.DataFrame([{"Корпус": "1", "Группа": "Окна", "Важность": "Критическое",
                                 "n": 1, "Просрочено45": True, "Блокирует": True, "Нед": 7}])
        contractors = pd.DataFrame([{"Подрядчик": "Подрядчик 1", "Группа": "Окна", "Замечаний": 1, "Квартир": 1,
                                     "Просрочено": 1, "% просрочено": 1., "Критических": 1, "Блок. квартир": 1,
                                     "Балл риска": 65., "Класс риска": "высокий", "Оценка стоимости открытых, ₽": 10_000.}])
        data[key] = dict(key=key, name=name, units=units, remarks=remarks, contractors=contractors,
                         calc_date=pd.Timestamp("2026-11-11"))

    params = dict(price=C.ILLUSTR_PRICE, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
    comparison = PF.build(data, params)
    by_key = {p["key"]: p for p in comparison["projects"]}
    assert {p["act_date"] for p in by_key.values()} == {pd.Timestamp("2026-11-04")}
    assert by_key["bunino"]["overdue_week_current"] == 6  # акт от 06.11 позже общей даты сравнения
    assert by_key["zen"]["overdue_week_current"] == 5
    assert comparison["totals"]["overdue_delta"] == -1

    demo_for_ui = {key: dict(project, observed_through=project["calc_date"]) for key, project in data.items()}
    monkeypatch.setattr(pf_demo, "build", lambda projects: demo_for_ui)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.secrets["APP_PASSWORD"] = "test-password"
    app.run()
    assert not app.exception
    assert not app.text_input                     # отчёт открывается без пароля
    assert not app.exception
    def open_screen(**route):
        app.query_params.clear()
        app.query_params.update(route)
        app.run()
        assert not app.exception, [e.message for e in app.exception]
        return " ".join(block.value for block in app.markdown)

    report = " ".join(block.value for block in app.markdown)
    summary = report.split('id="summary"', 1)[1]
    assert "Сводка по ЖК" in summary and 'class="fin main-table"' in summary
    assert 'href="/?card=zen#card-zen" data-pf-route>Дзен-кварталы' in summary
    zen = summary.split('id="exec-project-zen"', 1)[1].split("</table>", 1)[0]
    bunino = summary.split('id="exec-project-bunino"', 1)[1].split("</table>", 1)[0]
    assert '/?jk=zen#drill" data-pf-route>Страница ЖК' in summary
    assert "Что согласовать" not in summary and "Цель по остатку просрочки" not in summary
    assert "Передано 2026" in summary and "Передачи по годам" in summary and "Срез <b>11.11.2026</b>" in summary
    assert '<th scope="row">2026</th><td>3</td><td>0</td><td>3</td>' in zen
    assert '<th scope="row">2026</th><td>3</td><td>1</td><td>1</td>' in bunino
    assert 'Результат указан по 2 из 3' in summary.split('id="exec-project-bunino"', 1)[1].split("</details>", 1)[0]
    assert report.count("Демо-данные") == 1
    assert "сравнение с <b>04.11.2026</b>" in summary
    assert "Утвердить бюджет" not in summary and "Возможные требования по сценарию" not in summary
    assert "Неустойка в день <strong>" in summary
    assert '<summary>Ещё</summary>' in report
    assert 'href="/?view=orders" data-pf-route>Поручения' in summary

    money = open_screen(view="money")
    assert "Возможные требования по сценарию" in money
    assert "Накопленная неустойка (верхняя оценка)" in money
    assert "Предполагаемая сумма прошлых выплат" not in money
    forecast = open_screen(view="forecast")
    assert "Чистый темп, квартир в неделю" in forecast and "При целевом темпе, недель" in forecast
    decisions = open_screen(view="decisions")
    assert "Вторая смена приёмки · проверка перед согласованием" in [e.label for e in app.expander]
    priced_projects = PF.build(demo_for_ui, dict(params, prices={key: value * 1e6 for key, value in PF.DEFAULT_PRICES.items()}))
    priority = max(priced_projects["projects"], key=lambda project: project["decisions"][0]["effect_day"])
    details = decisions.split('id="priority"', 1)[1]
    assert "Критерий выбора" in details and priority["name"] in details
    assert f'/?jk={priority["key"]}#drill" data-pf-route>{priority["name"]}' in summary
    assert "один дополнительный день просрочки" in decisions
    orders = open_screen(view="orders")
    assert ">Поручения</div>" in orders
    for section in (decisions, orders):
        assert "Нужно решение ГД" in section and "В рабочем порядке" in section
        assert "18.11.2026" not in section and "следующем срезе" in section   # v23: без дат в поручениях и решениях

    assert open_screen(view="contribution").count('class="contrib-row') == 10
    matrix = open_screen(view="matrix")
    assert "Итого, квартиры" in matrix and "тем больше квартир" in matrix
    app.radio(key="pf_matrix_metric").set_value("₽ в день").run()
    assert not app.exception
    money_report = " ".join(block.value for block in app.markdown)
    assert "Итого, ₽ в день" in money_report and "тем выше расчётная неустойка в ₽/день" in money_report

    open_screen(view="reasons")
    assert app.selectbox(key="pf_reason_scope").value == "Все ЖК"
    portfolio_reasons = next(block.value for block in app.markdown if '<table class="fin ready-reasons">' in block.value)
    assert "Доля готовых" in portfolio_reasons and "Расчётная неустойка, ₽/день" in portfolio_reasons
    assert '<td class="r">40</td>' in portfolio_reasons
    app.selectbox(key="pf_reason_scope").select("Всеволожск").run()
    assert not app.exception
    project_reasons = next(block.value for block in app.markdown if '<table class="fin ready-reasons">' in block.value)
    assert '<td class="r">4</td>' in project_reasons and '<td class="r">40</td>' not in project_reasons

    directory = open_screen(view="segments")
    assert directory.count("#drill") == 10
    linked = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    linked.secrets["APP_PASSWORD"] = "test-password"
    linked.query_params["jk"] = "bunino"
    linked.run()
    assert not linked.exception and linked.header[0].value == "Бунинские кварталы"
