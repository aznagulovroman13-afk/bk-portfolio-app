"""Демонстрационный срез. Все строки созданы из вымышленных параметров."""
from __future__ import annotations

import numpy as np
import pandas as pd

import pf_core as C
import pf_stats


def build(projects: tuple) -> dict:
    rng = np.random.default_rng(1847)
    snapshot = pd.Timestamp("2026-11-13")
    result = {}
    for index, (key, name) in enumerate(projects):
        units = []
        remarks = []
        count = 106 + 18 * ((index * 7 + 3) % 9)
        readiness = (0.6, 0.72, 0.42, 0.63, 0.5)[index % 5]
        volume = (0.62, 0.42, 0.69, 0.36, 0.53)[index % 5]
        for number in range(1, count + 1):
            block = str((number - 1) // 48 + 1)
            section = str(((number - 1) % 48) // 24 + 1)
            floor = ((number - 1) % 24) // 3 + 1
            unit_id = f"DEMO-{index + 1:02d}-{number:03d}"
            transferred = rng.random() < volume
            accepted = pd.NaT
            if transferred:
                recent = rng.random() < (0.7, 0.53, 0.74, 0.6, 0.65)[index % 5]
                accepted = snapshot - pd.Timedelta(days=int(rng.integers(0, 28) if recent else rng.integers(28, 90)))
                due = accepted - pd.Timedelta(days=int(rng.integers(-14, 105)))
            else:
                due_offset = rng.integers(-13, 37) if rng.random() < 0.16 else rng.integers(38, 150)
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
                category = (number + issue) % 3
                age = int(rng.integers(6, 140))
                severity = rng.choice(["Критическое", "Значительное", "Стандартное"], p=[0.12, 0.33, 0.55])
                critical += int(severity == "Критическое")
                late_remarks += int(age > 45)
                remarks.append({"Объект": unit_id, "Корпус": block, "Группа": ("Отделка", "Окна", "Инженерные системы")[category],
                                "Подрядчик": f"Учебный подрядчик {category + 1}", "Возраст": age, "Важность": severity,
                                "Просрочено45": age > 45, "Блокирует": not transferred and severity == "Критическое",
                                "Повтор": issue > 0})
            delay = max(0, (comparison_date - due).days)
            rate = (12.0, 13.5, 15.0)[(index + number) % 3]
            units.append({"Объект": unit_id, "Квартира": number, "Корпус": block, "Секция": section, "Этаж": floor,
                          "Тип объекта": "Квартира", "Исходный статус": status, "Готовность подтверждена": ready,
                          "Просрочка ДДУ": (C.LATE if overdue else C.ONTIME) if transferred else (C.NT_OVERDUE if overdue else "срок ДДУ не наступил"),
                          "Просрочка ДДУ факт, дн.": delay, "Срок по ДДУ": due, "Дата принятия собственником": accepted,
                          "Коэф. неустойки на 1 ₽ цены (верх)": delay * rate / 15000,
                          "Коэф. неустойки на 1 ₽ цены (низ)": delay * rate / 20000,
                          "Ставка ЦБ на срок ДДУ, %": rate, "Мот. отказ / снятие готовности": status == "Не принята",
                          "Плановая дата ключей в ОЗ": snapshot + pd.Timedelta(days=7) if status == "Ключи в ОЗ не переданы" else pd.NaT,
                          "Статус записи собственника": visit, "Запись через, дн.": visit_day, "Официальный вызов, дн. назад": notice_day,
                          "Замечаний открыто": issue_count, "Критических": critical, "Просрочено (регл)": late_remarks})
        source = pd.DataFrame(remarks)
        result[key] = dict(key=key, name=name, units=pd.DataFrame(units), calc_date=snapshot,
                           remarks=pf_stats.remark_agg(source), contractors=pf_stats.contractor_table(source))
    return result
