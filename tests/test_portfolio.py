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
    assert [d["name"] for d in D.values()] == ["Бунинские кварталы", "Прокшино", "Дзен-кварталы"]


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
    assert set(R["Группа"]) == {"Окна", "Отделка", "Двери", "Инженерка", "Прочее"}
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
    assert len(B["projects"]) == 3
    for p in B["projects"]:
        assert 1 <= len(p["problems"]) <= 3 and len(p["weekly"]) == PF.N_WEEKS and len(p["by_korpus"]) > 0
        assert p["remarks"] > 0 and p["critical"] > 0 and p["remarks_cost"] > 0 and p["claim_potential"] > 0 and p["week_fact"] > 0
        assert p["claims"] is None and p["confirmed"] is None
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
    by_risk = PF.table(B["projects"], "risk")["Расчётный риск, ₽/сутки"].tolist()
    by_over = PF.table(B["projects"], "overdue")["Просрочено по ДДУ, кв."].tolist()
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


def test_model_note_is_single_constant():
    assert PF.MODEL_NOTE == "Прокшино и Дзен-кварталы — модельный сценарий."
    src = [(f, (ROOT / f).read_text(encoding="utf-8")) for f in ("app.py", "pf_model.py", "pf_ui.py", "pf_detail.py", "pf_stats.py", "pf_core.py")]
    assert [f for f, s in src if "модельн" in s] == ["pf_model.py"]


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


def test_app_locked_without_flag():
    locked = _app(secret_yes=False)
    locked.run()
    assert [m.value for m in locked.markdown] == ["Приложение не активировано"]


def test_full_report_after_login_has_no_labels_and_no_toggle():
    at = _login()
    t = _screen_text(at)
    for s in ("Портфель ЖК", "Бунинские кварталы", "Прокшино", "Дзен-кварталы", "Нет данных", "Допущения модели", "Портфель:", "Матрица рисков", "Ориентир"):
        assert s in t, s
    assert not BAD.search(t)
    assert not [w for w in LABELS[:8] if w in t], [w for w in LABELS[:8] if w in t]
    assert not at.get("segmented_control") and "pf_mode" not in at.session_state
    assert t.count(PF.MODEL_NOTE) == 1 and "Допущения модели" in t.split(PF.MODEL_NOTE)[0]
    _no_dates_sources(at, t)


def test_model_note_disappears_when_constant_is_empty(monkeypatch):
    monkeypatch.setattr(PF, "MODEL_NOTE", "")
    at = _login()
    t = _screen_text(at)
    assert "модельн" not in t and "Допущения модели" in t


@pytest.mark.parametrize("name", ["Бунинские кварталы", "Прокшино", "Дзен-кварталы"])
def test_each_project_gets_identical_set_of_blocks(name):
    at = _login()
    at.session_state["pf_sel"] = name
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert [t.label for t in at.tabs] == ["Обзор", "Шахматка", "Замечания", "Подрядчики", "Деньги", "Динамика"]
    t = _screen_text(at)
    for s in ("Три главные проблемы", "Подключить", "Проверим на следующем совещании", "Корпуса", "Открытых замечаний", "Балл риска",
              "Мало данных", "Потенциал претензий", "Предъявленные требования", "Блокируют передачу",
              "срок ДДУ нарушен", "Открыта к передаче", "Не принята"):
        assert s in t, s
    assert not [w for w in LABELS[:8] if w in t]
    _no_dates_sources(at, t)
    assert len([m for m in at.markdown if 'class="cb"' in m.value]) == 1      # шахматка выбранного ЖК
    heads = [" ".join(map(str, d.value.columns)) for d in at.dataframe]
    assert any("Помещений" in h and "Критических" in h for h in heads) and any("Балл риска" in h for h in heads)
