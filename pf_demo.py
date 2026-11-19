"""Расчётный срез портфеля: все строки получены из вымышленных параметров, реальных объектов и лиц в нём нет."""
from __future__ import annotations

import numpy as np
import pandas as pd

import pf_core as C
import pf_stats


GROUPS = ("Отделка", "Окна", "Инженерные системы", "Двери", "Прочее")
CONTRACTORS = {
    "Отделка": ("ООО «СтройАльянс»", "ООО «Интерьер Групп»", "ООО «Монолит-Сервис»"),
    "Окна": ("ООО «ОкнаПроф»", "ООО «Рамос»"),
    "Инженерные системы": ("ООО «ИнжТех»", "ООО «Теплосеть Монтаж»"),
    "Двери": ("ООО «ДверьСтрой»", "ООО «Портал»"),
    "Прочее": ("ООО «ГенСервис»", "ООО «Строй-Ресурс»"),
}


def _contractor(index: int, category: int, number: int) -> str:
    """Каждый ЖК работает с одним–двумя подрядчиками по виду работ; наборы ЖК пересекаются, но не совпадают."""
    options = CONTRACTORS[GROUPS[category]]
    start = index % len(options)
    allowed = [options[(start + i) % len(options)] for i in range(1 + (index + category) % 2)]
    return allowed[number % len(allowed)]


# ЖК, где передачи за последнюю неделю замедлились
STALLED = ("zen", "scands", "vsev")
# порядок ЖК фиксирует параметры генератора и не связан с порядком показа в отчёте
SAMPLE_ORDER = ("bunino", "zen", "proksh", "desn", "scandc", "yuzh", "vsev", "lag", "zorge", "scands")
ACCRUAL_START = pd.Timestamp("2026-01-01")
BK_EXPIRED_POOL = 12
BK_NOTICE_AGE = 45


def build(projects: tuple) -> dict:
    snapshot = pd.Timestamp("2026-11-13")
    result = {}
    for key, name in projects:
        index = SAMPLE_ORDER.index(key)
        rng = np.random.default_rng(1847 + 31 * index)
        units = []
        remarks = []
        count = 190 + 34 * ((index * 7 + 3) % 9)
        readiness = (0.6, 0.72, 0.42, 0.63, 0.5)[index % 5]
        volume = (0.62, 0.42, 0.69, 0.36, 0.53)[index % 5]
        for number in range(1, count + 1):
            block = str((number - 1) // 48 + 1)
            section = str(((number - 1) % 48) // 24 + 1)
            floor = ((number - 1) % 24) // 3 + 1
            unit_id = f"{index + 1:02d}-{number:04d}"
            transferred = rng.random() < volume
            accepted = pd.NaT
            if transferred:
                recent = rng.random() < (0.30, 0.24, 0.33, 0.27, 0.29)[index % 5]
                accepted = snapshot - pd.Timedelta(days=int(rng.integers(4 if key in STALLED else 0, 28) if recent else rng.integers(28, 210)))
                due = accepted - pd.Timedelta(days=int(rng.integers(-14, 105)))
            else:
                late_share = (0.34, 0.46, 0.30, 0.40, 0.37)[(index * 3 + 1) % 5]
                due_offset = rng.integers(2, 150) if rng.random() < late_share else -rng.integers(5, 220)
                due = snapshot - pd.Timedelta(days=int(due_offset))
            comparison_date = accepted if transferred else snapshot
            overdue = comparison_date > due
            ready = not transferred and rng.random() < readiness
            status = "Принята" if transferred else "Открыта к передаче" if ready else rng.choice(
                ["Открыта к передаче", "В ОЗ, готовность не открыта", "Ключи в ОЗ не переданы", "Не принята"])
            visit, visit_day, notice_day = "", None, None
            if ready:
                visit_kind = (number + index * 3) % 16
                if visit_kind < 7:
                    visit, visit_day = "Запланировано", 2 + visit_kind * 2
                elif visit_kind < 10:
                    visit = "Завершено"
                elif visit_kind == 10:
                    visit = "Не состоялось"
                elif visit_kind in (11, 12):
                    notice_day = 12 if visit_kind == 11 else 45
            issue_count = int(rng.integers(1, 6)) if not ready and rng.random() < 0.64 else 0
            critical = late_remarks = 0
            for issue in range(issue_count):
                category = (number + issue) % 5
                age = int(rng.integers(6, 140))
                severity = rng.choice(["Критическое", "Значительное", "Стандартное"], p=[0.12, 0.33, 0.55])
                critical += int(severity == "Критическое")
                late_remarks += int(age > 45)
                remarks.append({"Объект": unit_id, "Корпус": block, "Группа": GROUPS[category],
                                "Подрядчик": _contractor(index, category, number), "Возраст": age, "Важность": severity,
                                "Просрочено45": age > 45, "Блокирует": not transferred and severity == "Критическое",
                                "Повтор": issue > 0})
            delay = max(0, (comparison_date - due).days)
            accrual_days = max(0, (comparison_date - max(due, ACCRUAL_START - pd.Timedelta(days=1))).days)
            rate = (12.0, 13.5, 15.0)[(index + number) % 3]
            units.append({"Объект": unit_id, "Квартира": number, "Корпус": block, "Секция": section, "Этаж": floor,
                          "Тип объекта": "Квартира", "Исходный статус": status, "Готовность подтверждена": ready,
                          "Просрочка ДДУ": (C.LATE if overdue else C.ONTIME) if transferred else (C.NT_OVERDUE if overdue else C.NOT_DUE),
                          "Просрочка ДДУ факт, дн.": delay, "Дней для неустойки (после моратория)": delay, "Срок по ДДУ": due, "Дата принятия собственником": accepted,
                          "Коэф. неустойки на 1 ₽ цены (верх)": accrual_days * rate / 15000,
                          "Коэф. неустойки на 1 ₽ цены (низ)": accrual_days * rate / 20000,
                          "Ставка ЦБ на срок ДДУ, %": rate, "Мот. отказ / снятие готовности": status == "Не принята",
                          "Плановая дата ключей в ОЗ": snapshot + pd.Timedelta(days=7) if status == "Ключи в ОЗ не переданы" else pd.NaT,
                          "Статус записи собственника": visit, "Запись через, дн.": visit_day, "Официальный вызов, дн. назад": notice_day,
                          "Замечаний открыто": issue_count, "Критических": critical, "Просрочено (регл)": late_remarks})
        source = pd.DataFrame(remarks)
        apartments = pd.DataFrame(units)
        if key == "bunino":
            overdue_ready = apartments[C.ready_mask(apartments) & apartments["Просрочка ДДУ"].eq(C.NT_OVERDUE)]
            notice = "Официальный вызов, дн. назад"
            expired = overdue_ready[notice].gt(30).sum()
            unbooked = overdue_ready["Статус записи собственника"].eq("") & overdue_ready[notice].isna()
            supplement = overdue_ready[unbooked].index[:max(0, BK_EXPIRED_POOL - expired)]
            apartments.loc[supplement, notice] = BK_NOTICE_AGE
        result[key] = dict(key=key, name=name, units=apartments, calc_date=snapshot, observed_through=snapshot,
                           remarks=pf_stats.remark_agg(source), contractors=pf_stats.contractor_table(source))
    return result
