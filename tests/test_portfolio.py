"""Портфель ЖК: сверка с действующим отчётом, готовые ⊂ просроченные, «Только факт», шлюз, тексты."""
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
import pf_model as PF  # noqa: E402

P0 = dict(price=C.ILLUSTR_PRICE, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
BAD = re.compile("(" + "|".join(["app" + "le", "айф" + "он", "iph" + "one", "а1" + "01", "a1" + "01", r"power\s*" + "bi", r"инн\b", r"\b\d{10,12}\b"]) + ")", re.I)
OLD = Path(os.environ.get("PF_OLD_REPO", "/nonexistent"))  # необязательная сверка с кодом исходного отчёта
_SEC = ROOT / ".streamlit" / "secrets.toml"
KEY = tomllib.loads(_SEC.read_text(encoding="utf-8")).get("DATA_KEY") if _SEC.exists() else os.environ.get("DATA_KEY")
pytestmark = pytest.mark.skipif(not KEY, reason="нет DATA_KEY: расшифровать данные нельзя")


@pytest.fixture(scope="module")
def D():
    return pf_data.load(True, key=KEY)


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
    files = sorted(p.name for p in (ROOT / "data" / "bunino").iterdir())
    assert files and all(n.endswith(".enc") for n in files), files
    for p in (ROOT / "data" / "bunino").iterdir():
        head = p.read_bytes()[:4]
        assert head != b"PAR1" and not head.startswith(b"{"), p.name


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
def test_reconciliation_all_ok(D, price):
    P = dict(P0, price=price)
    b = PF.build(D, P, False)
    bad = [c["name"] for c in PF.reconcile(D, P, b["real"]) if not c["ok"]]
    assert not bad, bad


def test_real_numbers_match_report(D):
    r = PF.build(D, P0, True)["real"]
    u, pen = C.unit_kpis(D["apartments"]), C.penalty(D["apartments"], **P0)
    n, daily = C.ready_overdue_daily(D["apartments"], P0["price"])
    assert (r["overdue_all"], r["overdue_kv"], r["ready"]) == (u["nt_overdue"], u["nt_overdue_kv"], n)
    assert r["risk_day"] == pytest.approx(pen["daily"]) and r["ready_risk"] == pytest.approx(daily)


@pytest.mark.skipif(not (OLD / "ceo_core.py").exists(), reason="старый проект недоступен")
def test_numbers_equal_old_report_code():
    """Те же функции старого отчёта (только чтение) дают те же числа на полном срезе старого проекта."""
    import importlib.util
    import json
    import pandas as pd
    spec = importlib.util.spec_from_file_location("old_core", OLD / "ceo_core.py")
    sys.path.insert(0, str(OLD))
    try:
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
        a = pd.read_parquet(OLD / "data/ceo/apartments.parquet")
    finally:
        sys.path.remove(str(OLD))
    D = pf_data.load(True, key=KEY)
    assert old.unit_kpis(a)["nt_overdue_kv"] == C.unit_kpis(D["apartments"])["nt_overdue_kv"]
    assert old.penalty(a, **P0)["daily"] == pytest.approx(C.penalty(D["apartments"], **P0)["daily"])
    assert old.penalty(a, **P0)["accrued_up"] == pytest.approx(C.penalty(D["apartments"], **P0)["accrued_up"])
    assert old.ready_overdue_daily(a, P0["price"]) == pytest.approx(C.ready_overdue_daily(D["apartments"], P0["price"]))
    assert json.loads((OLD / "data/ceo/kpis.json").read_text(encoding="utf-8"))["calc_date"] == D["kpis"]["calc_date"]


def test_ready_included_in_overdue_and_in_total_risk(D):
    for fact_only in (True, False):
        B = PF.build(D, P0, fact_only)
        for p in B["projects"]:
            assert 0 <= p["ready"] <= p["overdue_kv"], p["name"]
            assert 0 <= p["ready_risk"] <= p["risk_day"] + 1e-6, p["name"]
        t = B["totals"]
        assert t["ready"] <= t["overdue_kv"] and t["ready_risk"] <= t["risk_day"] + 1e-6
        assert t["overdue_kv"] == sum(p["overdue_kv"] for p in B["projects"])
        assert t["risk_day"] == pytest.approx(sum(p["risk_day"] for p in B["projects"]))


def test_fact_only_excludes_demo_and_totals_are_real(D):
    all_, fact = PF.build(D, P0, False), PF.build(D, P0, True)
    assert [p["name"] for p in fact["projects"]] == [PF.REAL_NAME]
    assert not fact["totals"]["has_demo"] and all_["totals"]["has_demo"]
    assert all_["totals"]["fact"] == {k: fact["totals"][k] for k in all_["totals"]["fact"]}
    assert all(p["demo"] for p in all_["projects"][1:])


def test_missing_indicators_are_explicit(D):
    r = PF.build(D, P0, True)["real"]
    assert r["week_plan"] is None and r["week_dev"] is None and r["claims"] is None and r["confirmed"] is None
    t = PF.table(PF.build(D, P0, False)["projects"])
    row = t[t["_name"] == PF.REAL_NAME].iloc[0]
    assert row["Отклонение от плана, кв."] == PF.NO_DATA
    demo = t[t["_name"] != PF.REAL_NAME]
    assert demo["ЖК"].str.contains("ДЕМО").all() and demo["Данные"].eq("ДЕМО").all()


def test_table_sorting_and_top3(D):
    B = PF.build(D, P0, False)
    by_risk = PF.table(B["projects"], "risk")["Расчётный риск, ₽/сутки"].tolist()
    by_over = PF.table(B["projects"], "overdue")["Просрочено по ДДУ, кв."].tolist()
    assert by_risk == sorted(by_risk, reverse=True) and by_over == sorted(by_over, reverse=True)
    for p in B["projects"]:
        assert 1 <= len(p["problems"]) <= 3
        for pr in p["problems"]:
            assert pr["roles"] and pr["metric"] and pr["action"]


def test_no_names_deadlines_brand_in_texts(D):
    B = PF.build(D, P0, False)
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


def test_data_has_no_pii_columns_and_sources_are_clean():
    import pandas as pd
    cols = " ".join(pf_data.load(True, key=KEY)["apartments"].columns).lower()
    assert not re.search(r"фио|телефон|e-?mail|подряд|инн|коммент|собственник\b", cols.replace("статус записи собственника", ""))
    src = " ".join((ROOT / f).read_text(encoding="utf-8") for f in ("app.py", "pf_model.py", "pf_ui.py", "pf_data.py", "pf_auth.py", "pf_crypto.py"))
    assert "/workspace" not in src and "logo" not in src.lower() and not BAD.search(src)


def _txt(at):
    t = " ".join(m.value for m in at.markdown)
    t = re.sub(r"<style>.*?</style>", "", t, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


PWD = "test-password-123"


def _no_dates_sources(at, t):
    """Даты среза, источники и сверка с действующим отчётом на экранах не показываются."""
    assert not re.search(r"\b\d{1,2}\.\d{2}\.\d{4}\b", t), re.findall(r"\b\d{1,2}\.\d{2}\.\d{4}\b", t)
    for w in ("срез", "Источник", "источник", "Сверка", "сверк", "kpis", "json", "parquet", "1С", "Совпало"):
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


def test_app_locked_without_flag_and_full_report_after_login(D):
    locked = _app(secret_yes=False)
    locked.run()
    assert [m.value for m in locked.markdown] == ["Приложение не активировано"]
    at = _app()
    at.run()
    at.text_input[0].input(PWD)
    at.button[0].click().run()
    assert not at.exception, [e.message for e in at.exception]
    t = _txt(at)
    for s in ("Портфель ЖК", "Прокшино", "Дзен-кварталы", "ДЕМО", "ФАКТ", "Нет данных", "Допущения модели"):
        assert s in t, s
    assert not BAD.search(t)
    assert "Портфель:" in t and "Главная проблема портфеля" not in t and "Матрица рисков" in t and "Ориентир" in t
    _no_dates_sources(at, t)
    at.session_state["pf_mode"] = "Только факт"
    at.run()
    assert not at.exception
    t = _txt(at)
    assert "Прокшино" not in t and "Дзен-кварталы" not in t
    _no_dates_sources(at, t)
    at.session_state["pf_mode"] = "Все ЖК"
    at.run()
    at.session_state["pf_sel"] = "Прокшино"
    at.run()
    assert not at.exception
    assert "Условные цифры для показа структуры отчёта" in _txt(at)
    _no_dates_sources(at, _txt(at))
