from pathlib import Path

import pandas as pd
import pytest

import pf_core as C
import pf_data
import pf_decide as DC
import pf_model as PF


@pytest.mark.parametrize(("overdue", "pace", "weeks"), [(1008, 92, 1008 / 92), (25, 10, 2.5), (20, 10, 2), (0, 0, 0)])
def test_forecast_keeps_partial_final_week(overdue, pace, weeks):
    result = DC.simulate(overdue, pace, 100)
    assert result["weeks"] == pytest.approx(weeks)
    assert result["path"][-1][1] == 0
    assert result["accrued"] == pytest.approx(7 * 100 * overdue * weeks / 2)


def test_best_decision_can_repeat_across_projects():
    common = dict(key="crew", pool="queue", family="capacity", effect=100)
    first = dict(key="calls", pool="silent", family="comms", effect=10)
    second = dict(key="notice", pool="silent", family="legal", effect=20)
    assert DC.pick([first, common]) == [common, first]
    assert DC.pick([common, second]) == [common, second]


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


def test_report_auth_and_first_screen_on_synthetic_data(monkeypatch):
    from streamlit.testing.v1 import AppTest

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
    assert by_key["bunino"]["overdue_week_current"] == 6  # акт БК от 06.11 позже общей даты
    assert by_key["zen"]["overdue_week_current"] == 5
    assert comparison["totals"]["overdue_delta"] == -1

    monkeypatch.setattr(pf_data, "load", lambda allowed: data)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30)
    app.secrets["SHOW_REAL_DATA"] = "yes"
    app.secrets["APP_PASSWORD"] = "test-password"
    app.run()
    assert not app.exception
    assert app.text_input[0].label == "Пароль"
    assert not app.caption
    app.text_input[0].input("test-password")
    app.button[0].click().run()
    assert not app.exception
    report = " ".join(block.value for block in app.markdown)
    captions = " ".join(block.value for block in app.caption)
    assert "стоимость второй смены" in report and "Поручения к согласованию" in report
    assert "Расчётная неустойка и сценарий выплат" in report and "При расчётном ориентире, недель" in report
    assert "Подтверждённые исходные данные" not in captions
    assert "История закрытия замечаний: нет данных." in captions
    summary = report.split('id="summary"', 1)[1].split('<div class="cmph">', 1)[0]
    assert "Сводка по портфелю" in summary and "10 ЖК · портфель включает демонстрационные данные" in summary
    assert "неделя сравнения для всех выбранных ЖК по 04.11.2026" in summary
    assert "Бунинские кварталы" not in summary and "Дзен-кварталы" not in summary
    assert len(app.selectbox(key="pf_goto").options) == 10
    assert app.selectbox(key="pf_reason_scope").value == "Весь портфель"
    portfolio_reasons = next(block.value for block in app.markdown if '<table class="fin ready-reasons">' in block.value)
    assert "Доля готовых" in portfolio_reasons and "Расчётный риск, ₽/день" in portfolio_reasons
    assert '<td class="r">40</td>' in portfolio_reasons
    app.selectbox(key="pf_reason_scope").select("Всеволожск").run()
    assert not app.exception
    project_reasons = next(block.value for block in app.markdown if '<table class="fin ready-reasons">' in block.value)
    assert '<td class="r">4</td>' in project_reasons and '<td class="r">40</td>' not in project_reasons
    app.selectbox(key="pf_goto").select("Всеволожск").run()
    assert not app.exception and app.selectbox(key="pf_sel").value == "Всеволожск"
    assert any('href="#drill">Открыть карточку ЖК «Всеволожск»' in block.value for block in app.markdown)
    assert "Navigation 1" in app.get("html")[-1].proto.body
    app.selectbox(key="pf_goto").select("Дзен-кварталы").run()
    assert not app.exception and app.selectbox(key="pf_sel").value == "Дзен-кварталы"
    assert "Navigation 2" in app.get("html")[-1].proto.body
    app.selectbox(key="pf_sel").select("Лаголово").run()
    assert not app.exception and app.selectbox(key="pf_goto").value == "Лаголово"
    assert not app.get("html")
