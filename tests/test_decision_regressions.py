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


def test_report_auth_and_first_screen_on_synthetic_data(monkeypatch):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_data.clear()

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

    monkeypatch.setattr(pf_demo, "build", lambda projects: data)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.run()
    assert not app.exception
    assert not app.text_input and "Пароль" not in " ".join(block.value for block in app.markdown)
    report = " ".join(block.value for block in app.markdown)
    captions = " ".join(block.value for block in app.caption)
    assert "Поручения к согласованию" in report
    assert "Чистый темп, квартир в неделю" in report and "При целевом темпе, недель" in report
    assert "Предполагаемая сумма прошлых выплат" not in report
    assert "Подтверждённые исходные данные" not in captions
    assert "нет данных" not in (report + captions).lower()
    summary = report.split('id="summary"', 1)[1].split('<div class="cmph">', 1)[0]
    assert "Сводка по портфелю" in summary and "10 ЖК в портфеле" in summary
    assert "сравнение за неделю по <b>04.11.2026</b>" in summary
    assert "Согласовать недельный план передач по каждому ЖК" in summary
    assert "Возможные требования по сценарию" not in summary
    assert "Возможные требования по сценарию" in report.split('id="money"', 1)[1]
    assert "Вторая смена приёмки · проверка перед согласованием" in [e.label for e in app.expander]
    priced_projects = PF.build(data, dict(params, prices={key: value * 1e6 for key, value in PF.DEFAULT_PRICES.items()}))
    priority = next(project for project in priced_projects["projects"] if project["key"] == "bunino")
    assert f'Приоритет недели — Бунинские кварталы · {C.fmt_money(priority["risk_day"])}/день' in summary
    share = priority["risk_day"] / priced_projects["totals"]["risk_day"]
    assert f"{C.fmt_pct(share, 1)} расчётной неустойки портфеля за день" in summary
    details = report.split('id="priority"', 1)[1].split('id="segments"', 1)[0]
    assert "Управленческий приоритет компании" in details and "Бунинские кварталы" in details
    assert summary.index("Приоритет недели") < summary.index("Решения недели по портфелю")
    orders = report.split('id="orders"', 1)[1].split('id="notes"', 1)[0]
    assert ">Бунинские кварталы</td>" in orders.split("</tr>", 2)[1]
    for section in (summary, orders):
        assert "до конца следующего рабочего дня после согласования" in section
        assert "через неделю после согласования" in section
    assert "Расчётная неустойка, ₽/день" in summary and "один дополнительный день просрочки" in summary
    assert "Накопленная неустойка (верхняя оценка)" in report
    assert '/?jk=bunino#drill" data-project-link>Открыть карточку ЖК' in summary
    assert '<summary>Ещё</summary>' in report
    assert "Открыть поручение" in summary
    assert report.count('class="contrib-row"') == 10
    assert "Итого, квартиры" in report and "тем больше квартир" in report
    app.radio(key="pf_matrix_metric").set_value("₽ в день").run()
    assert not app.exception
    money_report = " ".join(block.value for block in app.markdown)
    assert "Итого, ₽ в день" in money_report and "тем выше расчётная неустойка в ₽/день" in money_report
    assert len(app.selectbox(key="pf_goto").options) == 10
    assert app.selectbox(key="pf_reason_scope").value == "Весь портфель"
    portfolio_reasons = next(block.value for block in app.markdown if '<table class="fin ready-reasons">' in block.value)
    assert "Доля готовых" in portfolio_reasons and "Расчётная неустойка, ₽/день" in portfolio_reasons
    assert '<td class="r">40</td>' in portfolio_reasons
    app.selectbox(key="pf_reason_scope").select("Всеволожск").run()
    assert not app.exception
    project_reasons = next(block.value for block in app.markdown if '<table class="fin ready-reasons">' in block.value)
    assert '<td class="r">4</td>' in project_reasons and '<td class="r">40</td>' not in project_reasons
    app.selectbox(key="pf_goto").select("Всеволожск").run()
    assert not app.exception and app.selectbox(key="pf_sel").value == "Всеволожск"
    assert app.query_params["jk"] == "vsev"
    assert any('href="/?jk=vsev#drill" data-project-link>Открыть карточку ЖК «Всеволожск»' in block.value for block in app.markdown)
    assert "const jump = 1;" in app.get("html")[-1].proto.body
    app.selectbox(key="pf_goto").select("Дзен-кварталы").run()
    assert not app.exception and app.selectbox(key="pf_sel").value == "Дзен-кварталы"
    assert "const jump = 2;" in app.get("html")[-1].proto.body
    app.selectbox(key="pf_sel").select("Лаголово").run()
    assert not app.exception and app.selectbox(key="pf_goto").value == "Лаголово"
    assert app.query_params["jk"] == "lag"
    assert "const jump = null;" in app.get("html")[-1].proto.body
    linked = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    linked.query_params["jk"] = "bunino"
    linked.run()
    assert not linked.exception and linked.selectbox(key="pf_sel").value == "Бунинские кварталы"
    assert "const jump = 1;" in linked.get("html")[-1].proto.body
    st.cache_data.clear()  # синтетический набор не должен попасть в кэш других тестов
