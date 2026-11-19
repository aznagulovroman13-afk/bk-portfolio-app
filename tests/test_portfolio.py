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
import pf_model as PF  # noqa: E402
import pf_stats  # noqa: E402

P0 = dict(price=C.ILLUSTR_PRICE, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
BAD = re.compile("(" + "|".join(["app" + "le", "айф" + "он", "iph" + "one", "а1" + "01", "a1" + "01", r"power\s*" + "bi", r"инн\b", r"\b\d{10,12}\b"]) + ")", re.I)
# слова, которых не должно быть на экранах (собраны из частей, чтобы тест не находил сам себя)
LABELS = ["ДЕ" + "МО", "де" + "мо", "услов" + "ные цифры", "услов" + "н", "ФА" + "КТ", "ОЦЕ" + "НКА", "Только " + "факт", "Все " + "ЖК", "модельн"]
_SEC = ROOT / ".streamlit" / "secrets.toml"
KEY = tomllib.loads(_SEC.read_text(encoding="utf-8")).get("DATA_KEY") if _SEC.exists() else os.environ.get("DATA_KEY")
pytestmark = pytest.mark.skipif(not KEY, reason="нет DATA_KEY: расшифровать данные нельзя")
FOLDERS = [k for k, _ in pf_data.PROJECTS]


@pytest.fixture(scope="module")
def D():
    return pf_data.load(True, key=KEY)


@pytest.fixture(scope="module")
def B(D):
    return PF.build(D, P0)


def test_locked_gate_does_not_read_files(tmp_path, monkeypatch):
    monkeypatch.setattr(pf_data, "_key", lambda k: k or None)
    with pytest.raises(pf_data.LockedError):
        pf_data.load(False, root=tmp_path, key=KEY)
    with pytest.raises(pf_data.LockedError):
        pf_data.load(True, key="")  # нет ключа — не читаем и не расшифровываем


def test_wrong_key_does_not_decrypt():
    from cryptography.fernet import Fernet
    with pytest.raises(pf_data.LockedError):
        pf_data.load(True, key=Fernet.generate_key().decode())


def test_repo_data_is_encrypted_only():
    assert sorted(p.name for p in (ROOT / "data").iterdir()) == sorted(FOLDERS)
    for folder in FOLDERS:
        files = list((ROOT / "data" / folder).iterdir())
        assert files and all(p.name.endswith(".enc") for p in files), folder
        for p in files:
            head = p.read_bytes()[:4]
            assert head != b"PAR1" and not head.startswith(b"{"), p.name
    assert not [p for p in ROOT.rglob("*") if p.suffix in (".parquet", ".csv", ".xlsx") and ".venv" not in str(p)]


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


@pytest.mark.parametrize("price", [10e6, 14e6])
def test_bunino_reconciliation_all_ok(D, price):
    P = dict(P0, price=price)
    p = PF.project(D["bunino"], P)
    rows = PF.reconcile(D["bunino"], P, p)
    assert len(rows) >= 14
    assert not [c["name"] for c in rows if not c["ok"]]


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
    assert set(A["Просрочка ДДУ"].dropna()) <= {C.NT_OVERDUE, C.LATE, C.ONTIME, C.NO_DDU, C.UNSOLD}
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
        _, info = DT.chess_html(A, k)
        assert info["units"] == int((A["Корпус"].astype(str) == k).sum()) == sum(info["counts"].values())


def test_synthetic_projects_are_better_and_worse_with_own_scale(D):
    def m(k):
        a, d = D[k]["units"], D[k]
        kv = a["Тип объекта"].eq("Квартира")
        pen = C.penalty(a)
        wk = PF.weekly(a, d["calc_date"])
        return dict(units=len(a), nt_kv=C.unit_kpis(a)["nt_overdue_kv"] / kv.sum(), rem=a["Замечаний открыто"].sum() / len(a),
                    crit=a["Критических"].sum() / len(a), over=a["Просрочено (регл)"].sum() / len(a), risk=pen["daily"] / kv.sum(),
                    pace=wk["Передано, квартир"].iloc[:11].mean() / kv.sum())
    b, p, z = m("bunino"), m("proksh"), m("zen")
    assert 0.80 <= p["nt_kv"] / b["nt_kv"] <= 0.96 and 1.10 <= z["nt_kv"] / b["nt_kv"] <= 1.30
    for k in ("rem", "crit", "over", "risk"):
        assert 0.84 <= p[k] / b[k] <= 0.96, k
        assert 1.12 <= z[k] / b[k] <= 1.30, k
    assert 1.03 <= p["pace"] / b["pace"] <= 1.18 and 0.72 <= z["pace"] / b["pace"] <= 0.90
    # масштаб свой, не копия
    assert len({b["units"], p["units"], z["units"]}) == 3 and p["units"] / b["units"] not in (0.9, 1.2)
    # шум: распределение по корпусам не кратно Бунинским
    assert D["proksh"]["units"]["Корпус"].nunique() != D["bunino"]["units"]["Корпус"].nunique()


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
    src = " ".join((ROOT / f).read_text(encoding="utf-8") for f in ("app.py", "pf_model.py", "pf_ui.py", "pf_data.py", "pf_auth.py", "pf_crypto.py", "pf_detail.py", "pf_stats.py"))
    assert "/workspace" not in src and "logo" not in src.lower() and not BAD.search(src)
    assert not [w for w in LABELS[:6] if w in src], "служебные метки в коде"
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
SLICE_DATES = {"11.11.2026", "06.11.2026"}   # дата среза и дата последних актов приёма — единственные даты на экранах


def _no_dates_sources(at, t):
    """Даты среза, источники и сверка с действующим отчётом на экранах не показываются."""
    assert set(re.findall(r"\b\d{1,2}\.\d{2}\.\d{4}\b", t)) <= SLICE_DATES, re.findall(r"\b\d{1,2}\.\d{2}\.\d{4}\b", t)
    for w in ("Сверка", "сверк", "kpis", "json", "parquet", "1С", "Совпало"):
        assert w not in t, w
    cols = " ".join(" ".join(map(str, d.value.columns)) for d in at.dataframe)
    assert "срез" not in cols.lower() and "Дат" not in cols


def _app(secret_yes=True, pwd=PWD):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=240)
    at.secrets["SHOW_REAL_DATA"] = "yes" if secret_yes else "no"
    at.secrets["APP_PASSWORD"] = pwd
    at.secrets["DATA_KEY"] = KEY
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
    return at.radio(key="pf_data_mode").set_value("Демонстрационный портфель").run()


def _screen_text(at):
    side = " ".join(m.value for m in at.sidebar.markdown) + " " + " ".join(c.value for c in at.sidebar.caption)
    return _txt(at) + " " + re.sub(r"<[^>]+>", " ", side)


def test_app_locked_without_flag():
    locked = _app(secret_yes=False)
    locked.run()
    assert [m.value for m in locked.markdown] == ["Приложение не активировано"]


def test_full_report_after_login_labels_data_mode():
    at = _login()
    t = _screen_text(at)
    for s in ("Портфель ЖК", "Бунинские кварталы", "Прокшино", "Дзен-кварталы", "Допущения и методология расчёта", "Приоритетный объект портфеля", "Матрица экспозиции по причинам просрочки", "Расчётный ориентир"):
        assert s in t, s
    for s in ("Требует уточнения", "модельн", "Подтверждённые суммы"):
        assert s not in t, s
    assert not BAD.search(t)
    assert not [w for w in LABELS[:8] if w in t], [w for w in LABELS[:8] if w in t]
    assert at.radio(key="pf_data_mode").value == "Демонстрационный портфель"
    _no_dates_sources(at, t)


@pytest.mark.parametrize("name", ["Бунинские кварталы", "Прокшино", "Дзен-кварталы"])
def test_each_project_gets_identical_set_of_blocks(name):
    at = _login()
    at.session_state["pf_sel"] = name
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert [t.label for t in at.tabs] == ["Обзор", "Шахматка", "Замечания", "Подрядчики", "Финансы", "Динамика"]
    t = _screen_text(at)
    for s in ("Ключевые проблемы ЖК", "Ответственные роли", "Контрольный показатель", "Корпуса", "Открытых замечаний", "Балл риска",
              "Мало данных", "Потенциал претензий", "Блокируют передачу",
              "срок ДДУ нарушен", "Открыта к передаче", "Не принята"):
        assert s in t, s
    assert not [w for w in LABELS[:8] if w in t]
    _no_dates_sources(at, t)
    assert len([m for m in at.markdown if 'class="cb"' in m.value]) == 1      # шахматка выбранного ЖК
    heads = [" ".join(map(str, d.value.columns)) for d in at.dataframe]
    assert any("Помещений" in h and "Критических" in h for h in heads) and any("Балл риска" in h for h in heads)


def test_other_projects_use_the_same_contractors_as_bunino(D):
    bk = set(D["bunino"]["contractors"]["Подрядчик"])
    for k in ("proksh", "zen"):
        names = set(D[k]["contractors"]["Подрядчик"])
        assert names and names <= bk and len(names) < len(bk)
        assert set(D[k]["remarks"]["Подрядчик"]) <= bk
        assert not BAD.search(" ".join(names))
    # состав и объёмы у ЖК разные
    assert set(D["proksh"]["contractors"]["Подрядчик"]) != set(D["zen"]["contractors"]["Подрядчик"])
    a, b = (D[k]["contractors"].set_index("Подрядчик")["Замечаний"] for k in ("proksh", "zen"))
    common = a.index.intersection(b.index)
    assert len(common) >= 15 and not (a[common] == b[common]).any()


# ---------------------------------------------------------------- первый экран по новому ТЗ
def test_ready_is_counted_strictly(D, B):
    """Готовы = просрочены по ДДУ, не переданы, готовность подтверждена И ноль открытых замечаний."""
    for (folder, _), p in zip(pf_data.PROJECTS, B["projects"]):
        A = D[folder]["units"]
        kv = A[A["Тип объекта"].eq("Квартира") & A["Просрочка ДДУ"].eq(C.NT_OVERDUE)]
        strict = int((kv["Исходный статус"].eq("Открыта к передаче") & kv["Готовность подтверждена"].astype(bool) & kv["Замечаний открыто"].eq(0)).sum())
        loose = int((kv["Исходный статус"].eq("Открыта к передаче") & kv["Замечаний открыто"].eq(0)).sum())
        assert p["ready"] == strict <= loose, folder
    bk = B["projects"][0]
    assert (bk["overdue_kv"], bk["ready"]) == (1008, 522)      # прежнее определение давало 523: одна квартира без подтверждения готовности
    n, _ = C.ready_overdue_daily(D["bunino"]["units"], P0["price"])
    assert n == 522


def test_priority_is_top_risk_and_has_cause_decision(B):
    pr = PF.priority(B["projects"])
    top = max(B["projects"], key=lambda p: p["risk_day"])
    assert pr["name"] == top["name"] and pr["risk_day"] == top["risk_day"]
    assert pr["share"] == pytest.approx(top["risk_day"] / B["totals"]["risk_day"]) and 0 < pr["share"] <= 1
    assert pr["cause"] and pr["decision"] and pr["roles"] and pr["drivers"]
    txt = pr["cause"] + pr["decision"] + " ".join(pr["roles"] + pr["drivers"])
    assert "Требует уточнения" not in txtxt
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


def test_first_screen_shows_three_cards_slice_date_and_methodology():
    at = _login()
    t = _screen_text(at)
    for s in ("Просрочка по ДДУ", "Из них готовы к передаче", "Расчётная дневная экспозиция", "Дата среза: 11.11.2026", "Расчётная экспозиция определена по 10 из 10 ЖК в выбранном режиме",
              "1/300 ключевой ставки", "Приоритетный объект портфеля", "Основная причина (по данным)", "Предлагаемые решения и ожидаемый эффект", "Доля в общей экспозиции",
              "Изменение за неделю к целевому темпу", "Передано за неделю: факт / расчётный ориентир", "Дневная экспозиция на одну просроченную квартиру, ₽",
              "Расчётная неустойка и сценарий выплат", "Возможные требования по сценарию", "Ожидаемые выплаты по сценарию", "Предполагаемая сумма прошлых выплат", "Причины непередачи готовых квартир", "Прогноз и расчётный ориентир",
              "Управленческие решения и ожидаемый эффект"):
        assert s in t, s
    assert at.selectbox(key="pf_goto").options == [n for _, n in pf_data.PROJECTS]
    assert t.index("Расчётная дневная экспозиция") < t.index("Приоритетный объект портфеля") < t.index("Структура портфеля по ЖК")
    assert not [w for w in LABELS if w in t]
    # порядок строк таблицы: по убыванию риска
    order = [p["name"] for p in PF.by_risk(PF.build(pf_data.load(True, key=KEY), dict(P0, prices={k: v * 1e6 for k, v in PF.DEFAULT_PRICES.items()}))["projects"])]
    i = [t.index(n, t.index("Структура портфеля по ЖК")) for n in order]
    assert i == sorted(i)


def test_jump_button_opens_selected_project_detail():
    at = _login()
    at.selectbox(key="pf_goto").select("Лаголово").run()
    assert not at.exception and at.session_state["pf_sel"] == "Лаголово"
    assert at.selectbox(key="pf_sel").value == "Лаголово"


def test_cache_keys_bumped_for_new_schema():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert src.count('schema: str = "v11"') == 1


# ---------------------------------------------------------------- четыре вопроса гендиректора (v6)
import pf_decide as DC  # noqa: E402


def test_per_project_prices_and_risk_scale(D):
    base = PF.build(D, dict(P0, prices={}))
    own = PF.build(D, dict(P0, prices={k: v * 1e6 for k, v in PF.DEFAULT_PRICES.items()}))
    assert len({round(v, 3) for v in PF.DEFAULT_PRICES.values()}) == len(PF.DEFAULT_PRICES) == len(FOLDERS)
    for b, o, k in zip(base["projects"], own["projects"], FOLDERS):
        assert o["price"] == PF.DEFAULT_PRICES[k] * 1e6
        assert o["risk_day"] == pytest.approx(b["risk_day"] * PF.DEFAULT_PRICES[k] / 10.0)
    assert own["projects"][0]["risk_day"] == pytest.approx(base["projects"][0]["risk_day"])    # БК: 10 млн ₽ как в действующем отчёте


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
    bk = {k: v["n"] for k, v in B["projects"][0]["reasons"].items()}
    assert bk["refused"] + bk["missed"] == 115  # завершённые, отменённые и несостоявшиеся записи из среза БК


def test_official_calls_matched_by_room_code(D):
    A = D["bunino"]["units"]
    assert A["Официальный вызов, дн. назад"].notna().sum() > 1400            # коды помещений из реестра вызовов совпали с помещениями БК
    assert int(DC.ready_rows(A)["Официальный вызов, дн. назад"].notna().sum()) == 1   # среди готовых к передаче вызван лишь один


def test_forecast_and_scenario(B):
    for p in B["projects"]:
        f = p["forecast"]
        assert f["scn"]["weeks"] <= f["base"]["weeks"] and f["saving"] >= 0 and f["saving_4w"] >= 0
        assert f["scn"]["accrued"] <= f["base"]["accrued"]
        if p["ready"] / 4 > p["gross_left"] + 1:
            assert f["saving"] > 0 and f["saving_4w"] > 0     # сценарий быстрее текущего темпа — экономия есть
        assert p["burn_pace"] > 0 and p["target_burn"] > 0
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
    # Главное решение на каждом ЖК выбирается по эффекту, его пул содержит квартиры.
    assert len(B["projects"]) == 10
    for p in B["projects"]:
        d = p["decisions"][0]
        assert d["effect"] == max(c["effect"] for c in p["cands"])
        assert (p["reasons"][d["pool"]]["n"] > 0) if d["pool"] in p["reasons"] else p["risk_blocked"] > 0
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
        assert p["risk_target"] < 0 and p["risk_vs_target"] == pytest.approx(p["risk_delta"] - p["risk_target"])
        txt, bad = PF.vs_target(p)
        assert "целевом темпе" in txt and bad == (p["risk_vs_target"] > 0)
    assert "целев" in PF.risk_change(B["totals"], B["projects"])[1]


def test_new_sections_render_for_each_project_and_changed_coefficient():
    at = _login()
    t = _screen_text(at)
    for s in ("стоимость второй смены", "Записаны на приёмку", "Срок закрытия, недель", "Ожидаемые выплаты по сценарию"):
        assert s in t, s
    assert "Подрядчики: доля расчётной экспозиции и потенциал удержаний" in [e.label for e in at.expander]
    assert not re.search(r"Требует уточнения", t)
    at.slider(key="pf_k_claim").set_value(70).run()
    assert not at.exception
    t2 = _screen_text(at)
    assert "предъявляется 70%" in t2


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


def test_scale_differs_old_nearly_closed_new_high_remainder(B):
    by = {p["key"]: p for p in B["projects"]}
    share = lambda k: by[k]["rem"]["left_cum"] / by[k]["rem"]["total"] if by[k]["rem"]["total"] else 0
    assert share("scands") < share("lag") < share("vsev") < share("desn")
    assert by["scands"]["rem"]["left_cum"] < by["scandc"]["rem"]["left_cum"] / 10
    assert max(p["overdue_kv"] for p in B["projects"]) == by["bunino"]["overdue_kv"] == 1008     # Бунинские — факт, как в действующем отчёте


def test_money_is_consistent_with_remarks(B):
    for p in B["projects"]:
        assert 0 <= p["risk_blocked"] <= p["risk_day"] + 1e-6
        assert p["overdue_kv"] <= p["units_kv"] and p["ready"] <= p["overdue_kv"]
        assert p["rem"]["flats_unfixed"] >= p["rem"]["flats_one_unfixed"] >= 0
        assert p["rem"]["left_cum"] >= p["overdue_kv"] * 0 and len(p["trend"]) == PF.N_WEEKS


def test_new_projects_have_full_drilldown_and_fewer_contractors_than_bk(D):
    bk = set(D["bunino"]["contractors"]["Подрядчик"])
    for k in ("desn", "scandc", "yuzh", "vsev", "lag", "zorge", "scands"):
        c = D[k]["contractors"]
        assert 0 < len(c) <= len(bk) and set(c["Подрядчик"]) <= bk
        assert len(D[k]["remarks"]) > 0 and len(D[k]["units"]) > 0
        assert D[k]["units"]["Корпус"].nunique() >= 2 or len(D[k]["units"]) < 1000


def test_headline_and_screen_rows(B):
    tot = B["totals"]
    h = PF.headline(B["projects"], tot)
    top = PF.priority(B["projects"])
    assert top["name"] in h and h.count(".") >= 2 and "отставанием от целевой динамики" in h
    rows = PF.screen_rows(B["projects"])
    assert [r["name"] for r in rows] == [p["name"] for p in PF.by_risk(B["projects"])] and len(rows) == 10
    assert sum(r["share"] for r in rows) == pytest.approx(1) and all(len(r["trend"]) == PF.N_WEEKS for r in rows)
    assert [r["risk"] for r in rows] == sorted((r["risk"] for r in rows), reverse=True)


def test_first_screen_v7_has_table_and_remarks_section_without_brands():
    at = _login()
    t = _screen_text(at)
    for s in ("Структура портфеля по ЖК", "Реестр замечаний по портфелю", "Всего замечаний за период", "Открытые замечания", "Средний срок устранения", "Связь с финансовыми показателями",
              "Доля просроченных", "С одним неустранённым", "Главное решение и ожидаемый эффект", "Наибольшая расчётная экспозиция —"):
        assert s in t, s
    labels = [e.label for e in at.expander]
    assert "Расширенные показатели по ЖК: экспозиция, темп и сроки" in labels and "Расширенные показатели по замечаниям и квартирам" in labels
    for _, n in pf_data.PROJECTS:
        assert n in t
    assert t.index("Наибольшая расчётная экспозиция —") < t.index("Приоритетный объект портфеля")
    assert not BAD.search(t) and not [w for w in LABELS if w in t] and "Требует уточнения" not in t
    at.selectbox(key="pf_qsel").select("Прокшино").run()
    assert not at.exception


def test_table_colour_only_for_worse_than_target(B):
    rows = PF.screen_rows(B["projects"])
    assert all(r["worse"] == (p["risk_vs_target"] > 0) for r, p in zip(rows, PF.by_risk(B["projects"])))
    assert any(r["worse"] for r in rows) and not all(r["worse"] for r in rows)
