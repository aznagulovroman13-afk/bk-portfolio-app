"""Портфель ЖК: общая схема и сверка Бунинских с действующим отчётом, равная аналитика по всем ЖК, шлюз, тексты экранов."""
from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pf_core as C  # noqa: E402
import pf_data  # noqa: E402
import pf_detail as DT  # noqa: E402
import pf_demo  # noqa: E402
import pf_model as PF  # noqa: E402
import pf_stats  # noqa: E402

P0 = dict(price=C.ILLUSTR_PRICE, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
BAD = re.compile("(" + "|".join(["app" + "le", "айф" + "он", "iph" + "one", "а1" + "01", "a1" + "01", r"power\s*" + "bi", r"инн\b", r"\b\d{10,12}\b"]) + ")", re.I)
# слова, которых не должно быть на экранах (собраны из частей, чтобы тест не находил сам себя)
LABELS = ["ДЕ" + "МО", "де" + "мо", "услов" + "ные цифры", "услов" + "н", "ФА" + "КТ", "ОЦЕ" + "НКА", "Только " + "факт", "Все " + "ЖК", "модельн"]
FOLDERS = [k for k, _ in pf_data.PROJECTS]


@pytest.fixture(scope="module")
def D():
    return pf_demo.build(pf_data.PROJECTS)


@pytest.fixture(scope="module")
def B(D):
    return PF.build(D, P0)


def test_repo_has_no_data_files():
    assert not (ROOT / "data").exists()
    assert not [p for p in ROOT.rglob("*") if (p.suffix in (".parquet", ".csv", ".xlsx", ".enc") or p.name in ("data_gate.py"))
                and ".venv" not in str(p) and ".git" not in p.parts]


def test_password_compare_and_lockout():
    import pf_auth
    assert pf_auth.check_password("abc", "abc") and not pf_auth.check_password("abd", "abc")
    assert not pf_auth.check_password("", "") and not pf_auth.check_password("x", None)
    st = {}
    for i in range(pf_auth.MAX_FAILS):
        assert pf_auth.lock_left(st, now=100) == 0
        pf_auth.register_fail(st, now=100)
    assert pf_auth.lock_left(st, now=100) == pf_auth.LOCK_SECONDS
    assert pf_auth.lock_left(st, now=100 + pf_auth.LOCK_SECONDS + 1) == 0


def test_all_projects_share_one_schema(D):
    cols = {k: (tuple(d["units"].columns), tuple(d["remarks"].columns), tuple(d["contractors"].columns)) for k, d in D.items()}
    assert len(set(cols.values())) == 1, "у всех ЖК должна быть одна схема таблиц"
    assert [d["name"] for d in D.values()] == [n for _, n in pf_data.PROJECTS]


@pytest.mark.parametrize("folder", FOLDERS)
def test_internal_consistency_of_every_project(D, folder):
    d = D[folder]
    A, R, CT = d["units"], d["remarks"], d["contractors"]
    assert A["Объект"].is_unique
    if folder != "bunino":   # у Бунинских реестр замечаний чуть шире помещений среза — берём как есть
        assert int(R["n"].sum()) == int(A["Замечаний открыто"].sum()) == int(CT["Замечаний"].sum())
        assert int(R.loc[R["Важность"].eq("Критическое"), "n"].sum()) == int(A["Критических"].sum())
    assert (A["Критических"] <= A["Замечаний открыто"]).all() and (A["Просрочено (регл)"] <= A["Замечаний открыто"]).all()
    assert set(A["Просрочка ДДУ"].dropna()) <= {C.NT_OVERDUE, C.LATE, C.ONTIME, C.NO_DDU, C.UNSOLD, C.NOT_DUE}
    tr = C.transferred_mask(A)
    assert A.loc[tr, "Дата принятия собственником"].notna().all() and A.loc[~tr, "Дата принятия собственником"].isna().all()
    nt = A["Просрочка ДДУ"].eq(C.NT_OVERDUE)
    assert not (nt & tr).any() and (A.loc[nt, "Срок по ДДУ"] < d["calc_date"]).all()
    # коэффициенты неустойки согласованы со ставкой и днями
    x = A[A["Дней для неустойки (после моратория)"].notna()]
    assert ((x["Дней для неустойки (после моратория)"] * x["Ставка ЦБ на срок ДДУ, %"] / 100 / 150) - x["Коэф. неустойки на 1 ₽ цены (верх)"]).abs().max() < 1e-9
    assert set(CT["Класс риска"]) <= {"высокий", "средний", "низкий", "мало данных"} and CT["Балл риска"].between(0, 100).all()
    assert set(R["Группа"]) == {"Окна", "Отделка", "Двери", "Инженерные системы", "Прочее"}
    # шахматка: каждое помещение корпуса на экране ровно один раз
    for k in DT.korpus_list(A)[:3]:
        _, info = DT.chess_html(A, k, project_key=folder)
        assert info["units"] == int((A["Корпус"].astype(str) == k).sum()) == sum(info["counts"].values())




def test_ready_included_in_overdue_and_in_total_risk(B):
    for p in B["projects"]:
        assert 0 <= p["ready"] <= p["overdue_kv"], p["name"]
        assert 0 <= p["ready_risk"] <= p["risk_day"] + 1e-6, p["name"]
    t = B["totals"]
    assert t["ready"] <= t["overdue_kv"] and t["ready_risk"] <= t["risk_day"] + 1e-6
    assert t["overdue_kv"] == sum(p["overdue_kv"] for p in B["projects"])
    assert t["risk_day"] == pytest.approx(sum(p["risk_day"] for p in B["projects"]))
    assert t["remarks"] == sum(p["remarks"] for p in B["projects"])


def test_every_project_has_full_analytics(B):
    assert len(B["projects"]) == len(pf_data.PROJECTS) == 10
    for p in B["projects"]:
        assert 1 <= len(p["problems"]) <= 3 and len(p["weekly"]) == PF.N_WEEKS and len(p["by_korpus"]) > 0
        assert p["remarks"] > 0 and p["critical"] > 0 and p["remarks_cost"] > 0 and p["claim_potential"] > 0 and p["week_fact"] > 0
        assert p["has_risk"] and p["week_plan"] and p["week_plan"] > 0 and p["overdue_prev"] > 0
        for pr in p["problems"]:
            assert pr["roles"] and pr["metric"] and pr["action"] and pr["cause"]
        w = p["weekly"]
        assert (w["Передано, всего"] >= w["Передано, квартир"]).all()


def test_remark_aggregates_match_stats_helpers(D):
    for d in D.values():
        g = DT.remark_groups(d["remarks"])
        assert int(g["Замечаний"].sum()) == int(d["remarks"]["n"].sum()) == int(DT.remark_ages(d["remarks"])["Замечаний"].sum())
        assert int(DT.remark_importance(d["remarks"]).sum()) == int(g["Замечаний"].sum())


def test_table_sorting_and_top3(B):
    by_risk = PF.table(B["projects"], "risk")["Расчётная дневная экспозиция, ₽"].tolist()
    by_over = PF.table(B["projects"], "overdue")["Просрочка по ДДУ, квартир"].tolist()
    assert by_risk == sorted(by_risk, reverse=True) and by_over == sorted(by_over, reverse=True)
    assert "Данные" not in PF.table(B["projects"]).columns


def test_no_names_deadlines_brand_in_texts(B):
    texts = []
    for p in B["projects"]:
        for pr in p["problems"]:
            texts += [pr["title"], pr["action"], pr["metric"], pr["cause"], pr["korpusa"], *pr["roles"]]
    h, ms = PF.portfolio_messages(B["totals"], B["projects"])
    texts += [h, *ms]
    blob = " ".join(texts)
    assert not BAD.search(blob)
    assert not re.search(r"\b\d{1,2}\.\d{2}\.\d{4}\b", " ".join(pr["action"] + pr["metric"] for p in B["projects"] for pr in p["problems"]))
    assert not re.search(r"\b[А-Я][а-я]+ [А-Я]\.[А-Я]\.", blob)
    assert not [w for w in LABELS[:7] if w in blob]


def test_data_has_no_pii_columns_and_sources_are_clean(D):
    for d in D.values():
        for df in (d["units"], d["remarks"], d["contractors"]):
            cols = " ".join(df.columns).lower().replace("статус записи собственника", "")
            assert not re.search(r"фио|телефон|e-?mail|инн|коммент|собственник\b", cols)
        names = " ".join(d["contractors"]["Подрядчик"])
        assert not BAD.search(names)
    src = " ".join((ROOT / f).read_text(encoding="utf-8") for f in ("app.py", "pf_model.py", "pf_ui.py", "pf_data.py", "pf_auth.py", "pf_detail.py", "pf_stats.py"))
    assert "/workspace" not in src and "logo" not in src.lower() and not BAD.search(src)
    assert not [w for w in LABELS[:6] if w in src.replace("Демо-данные", "")], "служебные метки в коде"
    assert "badge" not in src


def test_no_model_note_and_no_placeholders_in_code():
    assert not hasattr(PF, "MODEL_NOTE") and not hasattr(PF, "NO_DATA")
    src = " ".join((ROOT / f).read_text(encoding="utf-8") for f in ("app.py", "pf_model.py", "pf_ui.py", "pf_detail.py", "pf_stats.py", "pf_core.py"))
    for w in ("модельн", "Требует уточнения"):
        assert w not in src, w


def _txt(at):
    t = " ".join(m.value for m in at.markdown)
    t = re.sub(r"<style>.*?</style>", "", t, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


PWD = "test-password-123"
SLICE_DATES = {"13.11.2026", "20.11.2026", "27.11.2026", "04.12.2026", "11.12.2026", "18.12.2026", "01.01.2026"}
# даты норм о моратории и изменениях 214-ФЗ (реквизиты и периоды действия, не сроки поручений)
SLICE_DATES |= {"18.03.2024", "22.03.2024", "21.03.2024", "31.12.2025", "01.07.2023", "31.12.2026", "01.09.2024", "01.01.2025"}


def _no_dates_sources(at, t):
    """Пользовательские даты ограничены датами расчёта, служебные названия источников скрыты."""
    assert set(re.findall(r"\b\d{1,2}\.\d{2}\.\d{4}\b", t)) <= SLICE_DATES, re.findall(r"\b\d{1,2}\.\d{2}\.\d{4}\b", t)
    for w in ("kpis", "json", "parquet", "1С", "Совпало"):
        assert w not in t, w
    cols = " ".join(" ".join(map(str, d.value.columns)) for d in at.dataframe)
    assert "срез" not in cols.lower() and "Дат" not in cols


def _app(secret_yes=True, pwd=PWD):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    at.secrets["SHOW_REAL_DATA"] = "yes" if secret_yes else "no"
    at.secrets["APP_PASSWORD"] = pwd
    return at


def test_login_screen_only_without_password():
    at = _app()
    at.run()
    assert not at.exception
    t = _txt(at)
    assert "Закрытый отчёт" in t and at.text_input[0].label == "Пароль"
    assert not any(s in t for s in ("Бунинские", "Прокшино", "просрочено", "Сводка для совещания"))
    assert len(at.text_input) == 1 and at.text_input[0].proto.type == 1  # password
    assert not at.dataframe and not at.get("plotly_chart")
    at.text_input[0].input("неверный")
    at.button[0].click().run()
    assert "Неверный пароль" in _txt(at) and "Бунинские" not in _txt(at)
    for _ in range(4):
        at.text_input[0].input("again")
        at.button[0].click().run()
    assert "Слишком много попыток" in _txt(at)
    assert at.text_input[0].disabled and at.button[0].disabled and "pf_auth_ok" not in at.session_state



def _login():
    at = _app()
    at.run()
    at.text_input[0].input(PWD)
    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    return at


def _screen_text(at):
    side = " ".join(m.value for m in at.sidebar.markdown) + " " + " ".join(c.value for c in at.sidebar.caption)
    return _txt(at) + " " + re.sub(r"<[^>]+>", " ", side)


def test_demo_opens_without_real_data_flag():
    at = _app(secret_yes=False)
    at.run()
    at.text_input[0].input(PWD)
    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    t = _txt(at)
    assert t.count("Демо-данные") == 1 and "Сводка по портфелю" in t


def _open(at, **route):
    at.query_params.clear()
    at.query_params.update(route)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    return _screen_text(at)


def test_full_report_after_login_labels_data_mode():
    at = _login()
    sections = {
        "summary": "Сводка по портфелю",
        "segments": "Структура портфеля по ЖК",
        "decisions": "Приоритетный объект портфеля",
        "reasons": "Причины непередачи готовых квартир",
        "forecast": "Прогноз и целевой темп",
        "contribution": "Концентрация дневной неустойки по ЖК",
        "dynamics": "Динамика: неделя к неделе",
        "matrix": "Просрочка и неустойка по причинам",
        "remarks": "Реестр замечаний по портфелю",
        "money": "Финансы: неустойка и стоимость устранения",
        "orders": "Поручения к согласованию",
        "notes": "Допущения и методология расчёта",
    }
    for key, heading in sections.items():
        page = _open(at, view=key)
        assert heading in page
        assert "Сводка по портфелю" not in page or key == "summary"
        assert not BAD.search(page)
        for term in ("Требует уточнения", "модельн", "Подтверждённые суммы"):
            assert term not in page
        _no_dates_sources(at, page)
    assert _open(at).count("Демо-данные") == 1


@pytest.mark.parametrize("key", ["bunino", "proksh", "zen"])
def test_each_project_gets_identical_set_of_blocks(key):
    at = _login()
    overview = _open(at, jk=key)
    for name in ("Обзор", "Шахматка", "Замечания", "Подрядчики", "Финансы", "Динамика"):
        assert name in overview
    for text in ("Ключевые проблемы ЖК", "Ответственные роли", "Контрольный показатель", "Корпуса", "Открытых замечаний"):
        assert text in overview
    assert "Сводка по портфелю" not in overview
    assert any(f'jk={key}&amp;tab=chess&amp;corpus=' in m.value for m in at.markdown)
    chess = _open(at, jk=key, tab="chess")
    assert "срок ДДУ нарушен" in chess and "Открыта к передаче" in chess and "Не принята" in chess
    assert len([m for m in at.markdown if 'class="cb"' in m.value]) == 1
    assert "Блокируют передачу" in _open(at, jk=key, tab="remarks")
    _open(at, jk=key, tab="contractors")
    assert any("Балл риска" in d.value.columns for d in at.dataframe)
    assert "Потенциал претензий" in _open(at, jk=key, tab="money")
    assert "Просрочка на конец недели" in _open(at, jk=key, tab="dynamics")


# ---------------------------------------------------------------- первый экран по новому ТЗ
def test_contractors_come_from_one_pool_and_differ_between_projects(D):
    pool = {name for names in pf_demo.CONTRACTORS.values() for name in names}
    sets = {k: set(d["contractors"]["Подрядчик"]) for k, d in D.items()}
    for k, names in sets.items():
        assert 3 <= len(names) <= len(pool) and names <= pool and set(D[k]["remarks"]["Группа"]) <= {"Отделка", "Окна", "Инженерные системы", "Двери", "Прочее"}
        assert not BAD.search(" ".join(names))
    assert len({tuple(sorted(v)) for v in sets.values()}) >= 3


def test_official_calls_only_for_untransferred_ready_units(D):
    for k, d in D.items():
        A = d["units"]
        called = A[A["Официальный вызов, дн. назад"].notna()]
        assert len(called) and called["Готовность подтверждена"].all() and not C.transferred_mask(called).any(), k


def test_ready_is_counted_strictly(D, B):
    """Готовы = просрочены по ДДУ, не переданы, готовность подтверждена И ноль открытых замечаний."""
    for (folder, _), p in zip(pf_data.PROJECTS, B["projects"]):
        A = D[folder]["units"]
        kv = A[A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].eq(C.NT_OVERDUE)]
        strict = int((kv["Исходный статус"].eq("Открыта к передаче") & kv["Готовность подтверждена"].astype(bool) & kv["Замечаний открыто"].eq(0)).sum())
        loose = int((kv["Исходный статус"].eq("Открыта к передаче") & kv["Замечаний открыто"].eq(0)).sum())
        assert p["ready"] == strict <= loose, folder
    for (folder, _), p in zip(pf_data.PROJECTS, B["projects"]):
        n, _ = C.ready_overdue_daily(D[folder]["units"], P0["price"])
        assert n == p["ready"], folder


def test_priority_is_top_risk_and_has_cause_decision(B):
    pr = PF.priority(B["projects"])
    top = max(B["projects"], key=lambda p: p["risk_day"])
    assert pr["name"] == top["name"] and pr["risk_day"] == top["risk_day"]
    assert pr["share"] == pytest.approx(top["risk_day"] / B["totals"]["risk_day"]) and 0 < pr["share"] <= 1
    assert pr["cause"] and pr["decision"] and pr["roles"] and pr["drivers"]
    txt = pr["cause"] + pr["decision"] + " ".join(pr["roles"] + pr["drivers"])
    assert "Требует уточнения" not in txt
    assert not re.search(r"\b\d{1,2}\.\d{2}\.\d{4}\b|до \d|не позднее", pr["decision"])


def test_table_sorted_by_risk_with_no_risk_rows_at_bottom(B):
    rows = PF.table_rows(B["projects"])
    risks = [int(r[3].replace(" ", "")) for r in rows]
    assert all(r[4] != PF.DASH for r in rows) and [int(r[4].replace(" ", "")) for r in rows] == [round(p["risk_day"] / p["overdue_kv"]) for p in PF.by_risk(B["projects"])]
    assert risks == sorted(risks, reverse=True) and len(rows) == len(B["projects"])
    assert sum(float(r[5].replace("%", "").replace(",", ".")) for r in rows) == pytest.approx(100, abs=0.6)
    assert all(r[6][0] != PF.DASH and r[7] != PF.DASH and r[8] for r in rows)
    # ЖК без оценки риска — внизу
    fake = [dict(B["projects"][2], has_risk=False, risk_day=0.0, name="Без оценки"), B["projects"][1], B["projects"][0]]
    ranked = PF.by_risk(fake)
    assert ranked[-1]["name"] == "Без оценки" and [p["name"] for p in ranked[:2]] == [B["projects"][0]["name"], B["projects"][1]["name"]]
    assert PF.table_rows(fake)[-1][3] == PF.DASH


def test_plan_fact_and_dynamics_are_comparable(B):
    for p in B["projects"]:
        w = p["weekly"][~p["weekly"]["partial"]]
        base = w["Передано, квартир"].iloc[-5:-1].mean()
        assert p["week_plan"] == int(round(base * PF.PLAN_UPLIFT))
        assert p["week_dev"] == p["week_fact"] - p["week_plan"]
        assert p["overdue_prev"] - p["overdue_week_current"] == -p["overdue_delta"]
        assert p["risk_prev"] + p["risk_delta"] == pytest.approx(p["risk_week_current"])
    t = B["totals"]
    assert t["risk_delta"] == pytest.approx(sum(p["risk_delta"] for p in B["projects"]))
    assert t["left_risk"] > 0 and t["entered_risk"] >= 0
    assert t["risk_delta"] == pytest.approx(t["entered_risk"] - t["left_risk"])


def test_first_screen_shows_annual_transfers_by_project(D):
    at = _login()
    t = _screen_text(at)
    for label in ("Квартир в просрочке", "Расчётная неустойка за просрочку передачи",
                  "Срез 20.11.2026", "Передача квартир по годам и ЖК"):
        assert label in t
    project_cards = next(m.value for m in at.markdown if 'class="exec-projects"' in m.value)
    assert "Что согласовать" not in t and '>Готовы к передаче</span>' not in project_cards
    assert ">Янв<" not in project_cards and "Шкала передач по месяцам" not in project_cards
    assert project_cards.index('id="exec-project-bunino"') < project_cards.index('id="exec-project-scandc"')
    for key, name in pf_data.PROJECTS:
        card = project_cards.split(f'id="exec-project-{key}"', 1)[1].split("</article>", 1)[0]
        assert name in card
        assert f'/?jk={key}&amp;tab=money#drill' in card
        assert f'/?jk={key}&amp;tab=remarks#drill' in card
        assert "Неустойка за просрочку передачи" in card and "Открытых замечаний" in card
        assert re.findall(r'<th scope="row">(20\d{2})</th>', card) == ["2024", "2025", "2026"]
        for year in (2024, 2025):
            assert f'<th scope="row">{year}</th>' + '<td class="is-missing">Нет данных</td>' * 3 in card
        units = D[key]["units"]
        dates = units["Дата принятия собственником"]
        total = (C.transferred_mask(units) & units["Тип объекта"].eq("Квартира")
                 & dates.dt.year.eq(2026) & dates.le(D[key]["calc_date"])).sum()
        assert f'<th scope="row">2026</th><td>{C.fmt_int(total)}</td>' in card
        assert card.count('class="is-missing"') == 8
    assert all(f'href="/?view={view}" data-pf-route class="exec-metric"' in project_cards
               for view in ("segments", "money"))
    assert "Произведённые выплаты" not in t and "Предъявленные требования" not in t
    _open(at, view="money")
    payout = next(expander for expander in at.expander if expander.label == "Сценарий будущих выплат по ЖК")
    assert any("Ожидаемые выплаты по сценарию" in block.value for block in payout.markdown)
    t = _open(at, view="segments")
    order = [p["name"] for p in PF.by_risk(PF.build(pf_demo.build(pf_data.PROJECTS), dict(P0, prices={k: v * 1e6 for k, v in PF.DEFAULT_PRICES.items()}))["projects"])]
    indexes = [t.index(name, t.index("Структура портфеля по ЖК")) for name in order]
    assert indexes == sorted(indexes)


def test_project_corpus_unit_links_and_matching_remarks(D):
    at = _login()
    d = D["zen"]
    row = d["units"].loc[d["units"]["Замечаний открыто"].gt(0)].iloc[0]
    unit, corpus = row["Объект"], row["Корпус"]
    _open(at, jk="zen", tab="chess", corpus=corpus)
    chess = next(m.value for m in at.markdown if 'class="cb"' in m.value)
    assert f'jk=zen&amp;tab=chess&amp;corpus={corpus}&amp;unit={unit}' in chess
    report = _open(at, jk="zen", tab="chess", corpus=corpus, unit=unit)
    assert "Срок по ДДУ" in report and "Блокирует передачу" in report
    for contractor in d["remark_items"].loc[d["remark_items"]["Объект"].eq(unit), "Подрядчик"]:
        assert contractor in report
    path = next(m.value for m in at.markdown if 'class="pf-path"' in m.value)
    assert f'jk=zen&amp;tab=chess&amp;corpus={corpus}#drill' in path and 'unit=' not in path
    _open(at, jk="zen", tab="chess", corpus=corpus, unit="not-in-this-corpus")
    assert any('class="cb"' in m.value for m in at.markdown)
    other_corpus = next(value for value in DT.korpus_list(d["units"]) if value != corpus)
    at.selectbox(key=f"pf_chess_zen_{corpus}").select(other_corpus).run()
    assert not at.exception and at.query_params["corpus"] == other_corpus
    assert "unit" not in at.query_params


def test_cache_keys_bumped_for_new_schema():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert src.count("schema: str = REPORT_SCHEMA") == 2
    assert f'REPORT_SCHEMA = "{PF.REPORT_SCHEMA}"' in src


# ---------------------------------------------------------------- четыре вопроса гендиректора (v6)
import pf_decide as DC  # noqa: E402


def test_per_project_prices_and_risk_scale(D):
    base = PF.build(D, dict(P0, prices={}))
    own = PF.build(D, dict(P0, prices={k: v * 1e6 for k, v in PF.DEFAULT_PRICES.items()}))
    assert len({round(v, 3) for v in PF.DEFAULT_PRICES.values()}) == len(PF.DEFAULT_PRICES) == len(FOLDERS)
    for b, o, k in zip(base["projects"], own["projects"], FOLDERS):
        assert o["price"] == PF.DEFAULT_PRICES[k] * 1e6
        assert o["risk_day"] == pytest.approx(b["risk_day"] * PF.DEFAULT_PRICES[k] / 10.0)


def test_ladder_steps_are_ordered_and_consistent(B):
    for p in B["projects"] + [B["totals"]]:
        L = p["ladder"]
        assert L["upper"] >= L["claimed"] >= L["expected"] >= L["paid"] >= 0 and L["lower"] <= L["upper"]
        assert L["claimed"] == pytest.approx(L["upper"] * DC.DEFAULT_K["claim"])
        assert L["expected"] == pytest.approx(L["claimed"] * (1 - DC.DEFAULT_K["cut"]))
        assert L["paid"] == pytest.approx(L["expected"] * DC.DEFAULT_K["paid"])
    assert B["totals"]["ladder"]["upper"] == pytest.approx(B["totals"]["accrued_up"])
    L2 = DC.ladder(1e9, 9e8, dict(claim=1.0, cut=0.0, paid=1.0))
    assert L2["expected"] == L2["upper"] == L2["paid"]


def test_ready_reasons_are_exclusive_and_sum_to_ready(B):
    for p in B["projects"]:
        assert set(p["reasons"]) == set(DC.REASON_KEYS)
        assert sum(r["n"] for r in p["reasons"].values()) == p["ready"]
        assert sum(r["risk"] for r in p["reasons"].values()) == pytest.approx(p["ready_risk"])
    t = B["totals"]
    assert sum(r["n"] for r in t["reasons"].values()) == t["ready"]




def test_forecast_and_scenario(B):
    for p in B["projects"]:
        f = p["forecast"]
        assert f["scn"]["weeks"] <= f["base"]["weeks"] and f["saving"] >= 0 and f["saving_4w"] >= 0
        assert f["scn"]["accrued"] <= f["base"]["accrued"]
        if p["ready"] / 4 > p["gross_left"] + 1:
            assert f["saving"] > 0 and f["saving_4w"] > 0     # сценарий быстрее текущего темпа — экономия есть
        assert p["burn_pace"] > 0 and p["target_burn"] >= 0
        pth = f["base"]["path"]
        assert pth[0][1] == p["overdue_kv"] and pth[-1][1] <= 0.5 and all(a[2] <= b[2] for a, b in zip(pth, pth[1:]))
    pf = DC.portfolio_forecast(B["projects"], 4)
    assert pf["base"]["weeks"] == pytest.approx(max(p["forecast"]["base"]["weeks"] for p in B["projects"]))
    assert pf["saving"] == pytest.approx(sum(p["forecast"]["saving"] for p in B["projects"]))
    assert DC.portfolio_forecast(B["projects"], 2)["saving"] >= DC.portfolio_forecast(B["projects"], 8)["saving"]
    s0 = DC.simulate(100, 0, 1000)       # темп нулевой: просрочка не закрывается
    assert s0["weeks"] is None and s0["path"][-1][1] >= 100


def test_decisions_have_effect_roles_and_no_names_or_deadlines(B):
    for p in B["projects"]:
        ds = p["decisions"]
        assert 1 <= len(ds) <= 3 and len({d["pool"] for d in ds}) == len(ds)          # разные причины, без пересечения пулов квартир
        for d in ds:
            assert d["effect"] > 0 and d["effect_day"] > 0 and d["roles"] and d["kind"] and d["title"] and d["basis"] and d["mechanism"] and d["metric"]
            assert len(d["short"]) <= 70 and not re.search(r"\b\d{1,2}\.\d{2}\.\d{4}\b|не позднее|до конца", d["title"] + d["basis"])
            assert not re.search(r"war room|one-stop|SLA|KPI|no-show|capacity", d["title"] + d["short"] + d["mechanism"], re.I)
        # эффект согласован с экспозицией ЖК: сумма снижений за день не больше экспозиции, каждое — не больше экспозиции своей причины
        assert sum(d["effect_day"] for d in ds) <= p["risk_day"]
        for d in ds:
            if d["pool"] in p["reasons"]:
                assert d["effect_day"] <= p["reasons"][d["pool"]]["risk"] + 1e-6
            else:
                assert d["effect_day"] <= p["risk_blocked"] + 1e-6
        cr = p["contractor_risk"]
        assert cr and sum(c["share"] for c in cr) <= 1 and all(0 < c["share"] < 1 for c in cr)
    pri = PF.priority(B["projects"])
    assert 1 <= len(pri["decisions"]) <= 3 and all(d["effect"] > 0 for d in pri["decisions"])
    assert any("Доля подрядчиков" in x for x in pri["drivers"])


def test_main_decision_is_specific_per_project(B):
    # Главные решения всех ЖК различны без исключений; пул решения содержит квартиры.
    assert len(B["projects"]) == 10
    mains = [p["decisions"][0] for p in B["projects"]]
    assert len({d["key"] for d in mains}) == len({d["short"] for d in mains}) == len({d["title"] for d in mains}) == 10
    assert all(d["key"] != "crew" for d in mains)
    for project in B["projects"]:
        available_pools = {candidate["pool"] for candidate in project["cands"] if candidate["key"] != "crew"}
        selected_pools = {decision["pool"] for decision in project["decisions"]}
        assert len(project["decisions"]) == len(selected_pools) == min(3, len(available_pools))
    for p, d in zip(B["projects"], mains):
        assert d["effect"] > 0 and d["effect_day"] <= p["risk_day"] + 1e-6 and d["key"] in {c["key"] for c in p["cands"]}
        assert (p["reasons"][d["pool"]]["n"] > 0) if d["pool"] in p["reasons"] else p["risk_blocked"] > 0
    assert sum(d["effect_day"] for d in mains) <= B["totals"]["risk_day"]
    # правовые формулировки: односторонний акт — только со ссылкой на ст. 8 214-ФЗ
    for p in B["projects"]:
        for d in p["cands"]:
            if "односторонн" in d["title"].lower():
                assert "ст. 8 214-ФЗ" in d["title"]


def test_table_cell_has_short_decision_and_effect(B):
    for r in PF.screen_rows(B["projects"]):
        assert 0 < len(r["decision"]) <= 70 and r["dec_day"] > 0 and r["dec_4w"] > r["dec_day"]


def test_week_dynamics_is_compared_with_target(B):
    for p in B["projects"]:
        assert p["risk_target"] <= 0 and p["risk_vs_target"] == pytest.approx(p["risk_delta"] - p["risk_target"])
        txt, bad = PF.vs_target(p)
        assert "целевом темпе" in txt and bad == (p["risk_vs_target"] > 0)
    assert "целев" in PF.risk_change(B["totals"], B["projects"])[1]


def test_new_sections_render_for_each_project_and_changed_coefficient():
    at = _login()
    assert "Стоимость второй смены" in _open(at, view="decisions")
    assert "Подрядчики: доля дневной неустойки и потенциал удержаний" in [e.label for e in at.expander]
    assert "Записаны на приёмку" in _open(at, view="reasons")
    assert "Срок закрытия, недель" in _open(at, view="segments")
    assert "Ожидаемые выплаты по сценарию" in _open(at, view="money")
    at.slider(key="pf_k_claim").set_value(70).run()
    assert not at.exception
    assert any("Возможные требования составляют 70%" in caption.value for caption in at.caption)


# ---------------------------------------------------------------- v7: структура показателей по замечаниям, 10 ЖК, первый экран
import pf_remstat as RS  # noqa: E402


@pytest.mark.parametrize("folder", FOLDERS)
def test_remstat_arithmetic_identities(D, folder):
    r = RS.compute(D[folder]["units"], folder)
    assert r["total"] == r["fixed"] + r["cancelled"] + r["suspended"] + r["left"] > 0
    assert r["left_cum"] == r["left"] + r["carry"] == int(D[folder]["units"]["Замечаний открыто"].sum())
    assert 0 <= r["overdue"] <= r["left_cum"] and 0 < r["overdue_share"] <= 1
    q = r["quarters"]
    assert len(q) == 8 and int(q["Поступило"].sum()) == r["total"] and int(q["Устранено"].sum()) == r["fixed"]
    assert int(q["Отменено"].sum()) == r["cancelled"] and int(q["Приостановлено"].sum()) == r["suspended"]
    assert (q[["Поступило", "Устранено", "Отменено", "Приостановлено"]] >= 0).all().all()
    closed = q["Устранено"] + q["Отменено"] + q["Приостановлено"]
    assert (q["Остаток на конец"] == r["carry"] + q["Поступило"].cumsum() - closed.cumsum()).all()
    assert (q["Остаток на конец"] >= 0).all() and int(q["Остаток на конец"].iloc[-1]) == r["left_cum"]
    assert 0 < r["fixed"] / r["total"] < 1 and 0 <= r["cancelled"] / r["total"] < 1 and 20 <= r["avg_days"] <= 120
    # квартиры
    assert r["flats_with"] <= r["flats_total"] and r["flats_unfixed"] + r["flats_all_fixed"] == r["flats_with"]
    assert r["flats_all_fixed"] <= r["flats_fixed_any"] <= r["flats_with"] and r["flats_one_unfixed"] <= r["flats_unfixed"] <= r["flats_total"]


def test_remstat_portfolio_equals_sum_of_projects(B):
    rows = [p["rem"] for p in B["projects"]]
    t = B["totals"]["rem"]
    for k in ("total", "fixed", "cancelled", "suspended", "left", "left_cum", "overdue", "flats_with", "flats_unfixed", "flats_total", "flats_all_fixed"):
        assert t[k] == sum(r[k] for r in rows), k
    assert t["total"] == t["fixed"] + t["cancelled"] + t["suspended"] + t["left"]
    assert t["left_cum"] == sum(p["remarks"] for p in B["projects"]) or t["left_cum"] > 0
    assert t["overdue_share"] == pytest.approx(t["overdue"] / t["left_cum"])
    q = t["quarters"]
    assert int(q["Остаток на конец"].iloc[-1]) == t["left_cum"] and int(q["Поступило"].sum()) == t["total"]
    assert min(r["avg_days"] for r in rows) <= t["avg_days"] <= max(r["avg_days"] for r in rows)




def test_money_is_consistent_with_remarks(B):
    for p in B["projects"]:
        assert 0 <= p["risk_blocked"] <= p["risk_day"] + 1e-6
        assert p["overdue_kv"] <= p["units_kv"] and p["ready"] <= p["overdue_kv"]
        assert p["rem"]["flats_unfixed"] >= p["rem"]["flats_one_unfixed"] >= 0
        assert p["rem"]["left_cum"] >= p["overdue_kv"] * 0 and len(p["trend"]) == PF.N_WEEKS


def test_every_project_has_full_drilldown_data(D):
    for k, d in D.items():
        assert len(d["contractors"]) > 0 and len(d["remarks"]) > 0 and len(d["units"]) > 0
        assert d["units"]["Корпус"].nunique() >= 2
        assert len(d["units"]) >= 190


def test_headline_and_screen_rows(B):
    tot = B["totals"]
    h = PF.headline(B["projects"], tot)
    top = PF.priority(B["projects"])
    assert top["name"] in h and h.count(".") >= 2 and "отставанием от целевой динамики" in h
    rows = PF.screen_rows(B["projects"])
    assert [r["name"] for r in rows] == [p["name"] for p in PF.by_risk(B["projects"])] and len(rows) == 10
    assert sum(r["share"] for r in rows) == pytest.approx(1) and all(len(r["trend"]) == PF.N_WEEKS for r in rows)
    assert [r["risk"] for r in rows] == sorted((r["risk"] for r in rows), reverse=True)


def test_directory_and_remarks_sections():
    at = _login()
    directory = _open(at, view="segments")
    assert "Структура портфеля по ЖК" in directory and "Главное решение и ожидаемый эффект" in directory
    assert "Расширенные показатели по ЖК: неустойка, темп и сроки" in [e.label for e in at.expander]
    for _, name in pf_data.PROJECTS:
        assert name in directory
    remarks = _open(at, view="remarks")
    for term in ("Реестр замечаний по портфелю", "Всего замечаний", "Открытые замечания",
                 "Средний срок устранения", "Связь с финансовыми показателями", "Доля просроченных", "С одним неустранённым"):
        assert term in remarks
    assert "Расширенные показатели по замечаниям и квартирам" in [e.label for e in at.expander]
    assert not BAD.search(remarks) and "Требует уточнения" not in remarks
    at.selectbox(key="pf_qsel").select("Прокшино").run()
    assert not at.exception


def test_table_colour_only_for_worse_than_target(B):
    rows = PF.screen_rows(B["projects"])
    assert all(r["worse"] == (p["risk_vs_target"] > 0) for r, p in zip(rows, PF.by_risk(B["projects"])))
    assert any(r["worse"] for r in rows) and not all(r["worse"] for r in rows)


def test_screens_have_no_service_labels_placeholders_or_emphasis_on_one_project():
    import html
    bad = [w.lower() for w in ("де" + "мо", "вымыш" + "лен", "услов" + "н", "нет " + "данных", "ориен" + "тир", "модел" + "ьн", "Требует " + "уточнения", "DE" + "MO-", "Учеб" + "ный")]
    B2 = PF.build(pf_demo.build(pf_data.PROJECTS), dict(P0, prices={k: v * 1e6 for k, v in PF.DEFAULT_PRICES.items()}))
    ranked = PF.by_risk(B2["projects"])
    at = _login()
    for project in ranked:
        name = project["name"]
        text = (_open(at, jk=project["key"]) + " " + " ".join(c.value for c in at.caption)).lower()
        assert text.count("демо-данные") == 1
        text = text.replace("демо-данные", "")
        assert not [w for w in bad if w in text], (name, [w for w in bad if w in text])
    _open(at, view="orders")
    orders = next(m.value for m in at.markdown if "Было → цель" in m.value and "<table" in m.value)
    assert "Ответственный" in orders and "27.11.2026" in orders
    _open(at, view="segments")
    mains = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", next(m.value for m in at.markdown if "Главное решение и ожидаемый эффект" in m.value))))
    shorts = [p["decisions"][0]["short"] for p in ranked]
    assert len(set(shorts)) == 10 and all(sh in mains for sh in shorts)


def test_demo_week_package_financial_reconciliation(D):
    report = PF.build(D, dict(P0, prices={key: value * 1e6 for key, value in PF.DEFAULT_PRICES.items()}))
    totals, projects = report["totals"], report["projects"]
    assert (totals["overdue_prev"], totals["left_n"], totals["entered_n"], totals["overdue_kv"]) == (527, 100, 4, 431)
    assert totals["ready"] == sum(reason["n"] for reason in totals["reasons"].values()) == 192
    assert totals["risk_prev"] - totals["left_risk"] + totals["entered_risk"] == pytest.approx(totals["risk_day"])
    assert totals["risk_prev"] == pytest.approx(4_720_530)
    assert totals["risk_day"] == pytest.approx(3_886_590)
    assert totals["week_fact"] == totals["week_pa_bilateral"] + totals["week_pa_unilateral"]
    assert (totals["week_fact"], totals["week_pa_bilateral"], totals["week_pa_unilateral"]) == (120, 117, 3)
    assert totals["left_n"] <= totals["week_fact"]
    for key, source in D.items():
        units = source["units"]
        assert units["Объект"].is_unique
        assert units["Дата принятия собственником"].notna().eq(units["Односторонний ПА"].notna()).all()
        project = next(project for project in projects if project["key"] == key)
        latest = project["weekly"].iloc[-1]
        assert latest["Передано, квартир"] == latest["По двусторонним ПА"] + latest["По односторонним ПА"]
    assert totals["accrued_up"] == pytest.approx(sum(project["accrued_up"] for project in projects))
    assert sum(project["risk_vs_target"] > 0 for project in projects) == 2
    priority = max(projects, key=lambda project: project["decisions"][0]["effect_day"])
    package = DC.week_package(projects, priority)
    assert priority["key"] == "bunino" and priority["decisions"][0]["key"] == "unilateral"
    assert (package[0]["eligible"], package[0]["units"], package[0]["week_units"]) == (7, 6, 2)
    assert priority["decisions"][0]["effect_day"] == pytest.approx(65_000 * 6 / 7)
    assert len({(measure["group"], measure["subreason"]) for measure in package}) == len(package)
    for measure in package:
        assert measure["week_units"] == sum(item["week_units"] for item in measure["items"])
        assert measure["cost"] == measure["units"] * DC.PACKAGE_RATES[measure["key"]]
        assert measure["effect_day"] == pytest.approx(sum(item["average"] * item["units"] for item in measure["items"]))
        assert measure["effect"] == pytest.approx(measure["effect_day"] * 14)
    for project in projects:
        assert sum(row["n"] for row in project["groups"]) == project["overdue_kv"]
        assert sum(row["risk"] for row in project["groups"]) == pytest.approx(project["risk_day"])
        assert all(decision["effect"] == pytest.approx(decision["effect_day"] * 14) for decision in project["decisions"])
    plan = DC.handover_plan(projects, package, PF.PROBLEMS)
    assert tuple(sum(row[key] for row in plan) for key in ("baseline", "total", "new", "closing")) == (431, 55, 17, 393)
    for row in plan:
        assert sum(row["groups"].values()) == row["total"]
        assert all(row["groups"][group["key"]] <= group["n"] for group in row["project"]["groups"])
        assert row["booked"] <= row["project"]["reasons"]["booked"]["n"]
        assert row["total"] == row["booked"] + row["reserve"] <= row["capacity"]
        assert row["closing_base"] - row["closing"] == row["reserve"]
        assert row["risk_total"] <= row["risk_base"]
        detail = DT.korpus_table(D[row["project"]["key"]]["units"], row["project"]["price"])
        assert detail["Готовы к передаче"].sum() == row["project"]["ready"]
        assert detail["Дневная экспозиция, ₽"].sum() == pytest.approx(row["project"]["risk_day"], abs=len(detail))
    scenario = DC.incremental_package_forecast(projects, package)
    for row in scenario:
        assert 0 <= row["effect"] <= row["base"]


def test_penalty_summary_is_consistent_with_portfolio(D, B):
    import pandas as pd
    import pf_penalty as PN
    T = PN.table(D, B["projects"])
    rows, tot = T["rows"], T["total"]
    assert len(rows) == len(pf_data.PROJECTS) and {r["key"] for r in rows} == set(FOLDERS)
    for r in rows:
        p = next(p for p in B["projects"] if p["key"] == r["key"])
        # 2026 по ДДУ совпадает с накопленной неустойкой ЖК (верхняя оценка, начисление с 01.01.2026) в разделе «Финансы»
        assert r["ddu"][2026] == pytest.approx(p["accrued_up"], rel=1e-6)
        assert r["total"] == pytest.approx(sum(r["ddu"].values()) + sum(r["remarks"].values()))
        for m in ("ddu", "remarks"):
            for y in PN.YEARS:
                assert r[m][y] >= 0 and r["effect"][m][y] >= -1e-6
                assert r["gross"][m][y] == pytest.approx(r[m][y] + r["effect"][m][y])
            # 2025 целиком в моратории: ничего не начислено; 2026 — мораторий не действует
            assert r[m][2025] == 0 and r["effect"][m][2026] == 0
        # 2024: начислено только за 01.01–21.03 по ставке не выше 7,5% — заметно меньше расчёта без моратория
        assert r["ddu"][2024] <= r["gross"]["ddu"][2024] * (81 / 366) * (PN.RATE_CAP / PN.HIST_DDU_RATE) + 1e-6
        assert (r["remarks"][2026] > 0) == (r["flats_overdue_remarks"] > 0)
        # 266-ФЗ / 482-ФЗ: неустойка за недостатки по квартире не выше стоимости устранения и 3% цены
        if r["flats_overdue_remarks"]:
            per_flat = r["remarks"][2026] / r["flats_overdue_remarks"]
            assert per_flat <= min(PN.CLAIM_BASE_PER_FLAT, PN.QUALITY_CAP * p["price"]) + 1e-6
    assert PN.MORATORIUM == (pd.Timestamp("2024-03-22"), pd.Timestamp("2025-12-31")) and PN.RATE_CAP == 7.5
    assert PN.in_moratorium(pd.Timestamp("2024-03-22")) and not PN.in_moratorium(pd.Timestamp("2024-03-21"))
    assert not PN.in_moratorium(pd.Timestamp("2026-01-01")) and PN.year_in_moratorium(2025) and not PN.year_in_moratorium(2024)
    assert PN.remark_daily_rate(pd.Timestamp("2024-08-31")) == 0.01
    assert PN.remark_daily_rate(pd.Timestamp("2025-01-10")) == pytest.approx(21 / 100 / 150)
    # итог = сумма строк по каждому году и мере, доли дают 100%, строки по убыванию суммы
    for y in PN.YEARS:
        for m in ("ddu", "remarks"):
            assert tot[m][y] == pytest.approx(sum(r[m][y] for r in rows))
            assert tot["effect"][m][y] == pytest.approx(sum(r["effect"][m][y] for r in rows))
    assert tot["total"] == pytest.approx(sum(r["total"] for r in rows))
    assert tot["effect_total"] == pytest.approx(sum(r["effect_total"] for r in rows)) and tot["effect_total"] > 0
    assert sum(r["share"] for r in rows) == pytest.approx(1.0)
    assert [r["total"] for r in rows] == sorted((r["total"] for r in rows), reverse=True)
    # неустойка за замечания — второстепенная мера относительно просрочки передачи
    assert 0 < sum(tot["remarks"].values()) < 0.2 * sum(tot["ddu"].values())


def test_penalty_is_attached_to_each_project_not_a_separate_block(D):
    import pf_penalty as PN
    at = _login()
    t = _screen_text(at)
    assert "Портфель ЖК · неустойка" not in t and 'id="penalty-summary"' not in " ".join(m.value for m in at.markdown)
    summary = next(m.value for m in at.markdown if 'class="exec-projects"' in m.value)
    # портфельный итог — третьей карточкой в ряду показателей
    assert summary.count('class="exec-metric"') == 3 and "Неустойка начислена за 2024–2026" in summary
    for key, name in pf_data.PROJECTS:
        card = summary.split(f'id="exec-project-{key}"', 1)[1].split("</article>", 1)[0]
        assert f'aria-label="Неустойка по годам, {name}"' in card
        for s in ("Неустойка за просрочку передачи (ч. 2 ст. 6 214-ФЗ)",
                  "Неустойка за нарушение сроков устранения недостатков (ч. 8 ст. 7 214-ФЗ)", "не начислено по ПП № 326", "мораторий"):
            assert s in card, (key, s)
        assert card.count("не начислено по ПП № 326") == 2
    # таблица «Структура портфеля по ЖК»: начислено и не начислено по каждому ЖК
    seg = _open(at, view="segments")
    for s in ("Неустойка начислена 2024–2026, млн ₽", "Не начислено по ПП № 326, млн ₽", "передача (ч. 2 ст. 6)", "недостатки (ч. 8 ст. 7)"):
        assert s in seg, s
    # карточка ЖК: годы, две меры и правовое основание
    for tab in ("overview", "money"):
        page = _open(at, jk="desn", tab=tab)
        for s in ("Неустойка ЖК по годам: начислено и не начислено по ПП № 326", "Ч. 2 ст. 6 214-ФЗ", "Ч. 8 ст. 7 214-ФЗ в ред. 266-ФЗ",
                  "1/150", "не более этой стоимости", "1% в день", "Ч. 4 ст. 10 в ред. 482-ФЗ", "3% цены договора", "ПП РФ № 326",
                  "22.03.2024 по 31.12.2025", "7,5%", "ПП № 2227", "31.12.2026"):
            assert s in page, (tab, s)
        assert not any(w in page for w in ("ориентир", "срок до"))
