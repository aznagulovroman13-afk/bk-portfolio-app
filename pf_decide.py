# v9
"""Расчётная неустойка и ожидаемые выплаты, причины непередачи готовых, прогноз и решения уровня генерального директора.

Факты — из данных ЖК (статусы записи, дата записи, реестр официальных вызовов, замечания, подрядчики).
Расчётные коэффициенты собраны здесь и в DEFAULT_K; их описание выводится в «Допущениях».
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import pf_core as C
import pf_roles as R

# ---- расчётные коэффициенты сценария (претензии, иски, выплаты и стоимость мер задаются допущениями)
DEFAULT_K = dict(claim=0.35,   # доля неустойки, по которой собственники предъявляют претензии и иски
                 cut=0.50,     # на сколько в среднем суд снижает неустойку по ст. 333 ГК РФ
                 paid=0.25)    # доля ожидаемых выплат, уже выплаченная
BOOK_DAYS = 7          # запись в пределах 7 дней — «записан», позже — очередь на слоты приёмщиков
CALL_WAIT_DAYS = 30    # официальный вызов не старше 30 дней — ждём срок, старше — срок истёк
EXTRA_CAPACITY = 0.25  # дополнительные бригады приёмки: +25% к фактическому темпу передачи
SHIFT_UNIT_COST = 40_000  # стоимость одной дополнительной приёмки во второй смене, ₽
CALL_RESPONSE = 0.50   # доля собственников, пришедших после официального вызова
UNILATERAL_SHARE = 0.90
REFUSAL_RESOLVED = 0.40
PRESSURE_SHARE = 0.25  # доля риска подрядчика, снимаемая удержаниями/штрафами за 4 недели
MONTH_W = 4
HORIZON_W = 104

REASONS = [
    ("booked", "Записаны на приёмку в ближайшие 7 дней"),
    ("queue", "Записаны на приёмку позже 7 дней"),
    ("refused", "Приёмка проведена, акт не подписан"),
    ("missed", "Запись отменена или приёмка не состоялась"),
    ("date_check", "Запись есть, дату нужно проверить"),
    ("called", "Вызваны официально, срок не истёк"),
    ("expired", "Срок официального вызова истёк"),
    ("silent", "Нет записи и официального вызова"),
]
REASON_KEYS = [k for k, _ in REASONS]


def ladder(up: float, lo: float, K: dict) -> dict:
    """Каскад оценок: расчётная неустойка (верхняя граница) → предъявлено → ожидаемые выплаты → уже выплачено."""
    claimed = up * K["claim"]
    expected = claimed * (1 - K["cut"])
    paid = expected * K["paid"]
    return dict(upper=up, lower=lo, claimed=claimed, expected=expected, paid=paid, left=expected - paid)


def ready_rows(A: pd.DataFrame) -> pd.DataFrame:
    return A[C.ready_mask(A) & A["Просрочка ДДУ"].eq(C.NT_OVERDUE) & A["Тип объекта"].eq("Квартира")]


def classify_ready(A: pd.DataFrame, price: float) -> dict:
    """Взаимоисключающие причины, по которым готовые квартиры не переданы: количество и дневная экспозиция по каждой."""
    r = ready_rows(A)
    rec = r["Статус записи собственника"].fillna("")
    days = r["Запись через, дн."]
    call = r["Официальный вызов, дн. назад"]
    planned = rec.isin(["Запланировано", "Демонстрация началась", "Демонстрация завершена"])
    refused = rec.eq("Завершено")
    missed = rec.isin(["Отменено", "Не состоялось"])
    dated = planned & days.ge(0).fillna(False)
    called = call.ge(0).fillna(False)
    masks = (refused, missed, dated & days.gt(BOOK_DAYS).fillna(False), dated, planned,
             called & call.le(CALL_WAIT_DAYS).fillna(False), called)
    cat = np.select(
        [mask.to_numpy(dtype=bool) for mask in masks],
        ["refused", "missed", "queue", "booked", "date_check", "called", "expired"], default="silent")
    rate = r["Ставка ЦБ на срок ДДУ, %"].fillna(0) / 100 / 150 * price
    out = {}
    for k in REASON_KEYS:
        m = cat == k
        out[k] = dict(n=int(m.sum()), risk=float(rate[m].sum()))
    return out


def simulate(n0: float, burn: float, r_unit: float, ready: float = 0.0, ready_weeks: int | None = None,
             cap: int = HORIZON_W, *, inflow: float = 0.0) -> dict:
    """burn — чистый темп; сценарий задаёт объём передач готовых до вычета притока."""
    n, acc, path, left = float(n0), 0.0, [(0, float(n0), 0.0)], float(ready)
    if n <= 0:
        return dict(weeks=0.0, accrued=acc, path=path)
    for w in range(1, cap + 1):
        b = burn
        if ready_weeks and w <= ready_weeks and left > 0:
            transfers = max(burn + inflow, ready / ready_weeks)
            b = transfers - inflow
            left = max(0.0, left - transfers)
        if b > 0 and b >= n - 1e-9:
            frac = min(1.0, n / b)
            acc += 7 * frac * r_unit * n / 2
            path.append((w, 0.0, acc))
            return dict(weeks=w - 1 + frac, accrued=acc, path=path)
        n2 = n - b
        acc += 7 * r_unit * (n + n2) / 2
        n = n2
        path.append((w, n, acc))
    return dict(weeks=None, accrued=acc, path=path)


def forecast(p: dict, ready_weeks: int = 4) -> dict:
    """Прогноз по ЖК: срок закрытия просрочки при текущем и целевом темпе, накопленный риск, сценарий «все готовые за N недель»."""
    n, burn = p["overdue_kv"], p["burn_pace"]
    r_unit = p["risk_day"] / n if n else 0.0
    base = simulate(n, burn, r_unit)
    tgt = simulate(n, p["target_burn"], r_unit)
    scn = simulate(n, burn, r_unit, ready=p["ready"], ready_weeks=ready_weeks, inflow=p["inflow"])
    return dict(base=base, target=tgt, scn=scn, r_unit=r_unit, saving=base["accrued"] - scn["accrued"],
                saving_4w=_acc_at(base, MONTH_W) - _acc_at(scn, MONTH_W))


def _acc_at(sim: dict, w: int) -> float:
    path = sim["path"]
    return path[min(w, len(path) - 1)][2]


def portfolio_forecast(projects: list[dict], ready_weeks: int = 4) -> dict:
    fs = [forecast(p, ready_weeks) for p in projects]
    out = {}
    for key in ("base", "target", "scn"):
        L = max(len(f[key]["path"]) for f in fs)
        n = np.zeros(L); acc = np.zeros(L)
        for f in fs:
            pth = f[key]["path"]
            for i in range(L):
                j = min(i, len(pth) - 1)
                n[i] += pth[j][1]
                acc[i] += pth[j][2]
        closed = [f[key]["weeks"] for f in fs]
        out[key] = dict(weeks=(max(closed) if all(c is not None for c in closed) else None), accrued=float(acc[-1]),
                        path=[(i, float(n[i]), float(acc[i])) for i in range(L)])
    out["saving"] = out["base"]["accrued"] - out["scn"]["accrued"]
    out["saving_4w"] = sum(f["saving_4w"] for f in fs)
    return out


def contractor_risk(p: dict, ct: pd.DataFrame, n: int = 3) -> list[dict]:
    """Доля дневной экспозиции ЖК на подрядчиках: риск просроченных квартир с открытыми замечаниями делится по числу квартир с замечаниями подрядчика."""
    big = ct[ct["Квартир"] > 0]
    tot = float(big["Квартир"].sum())
    if not len(big) or tot <= 0 or p["risk_day"] <= 0 or p["risk_blocked"] <= 0:
        return []
    out = []
    for _, r in big.sort_values("Квартир", ascending=False).head(n).iterrows():
        risk = p["risk_blocked"] * float(r["Квартир"]) / tot
        out.append(dict(name=r["Подрядчик"], risk=risk, share=risk / p["risk_day"], blocked=int(r["Блок. квартир"]), units=int(r["Квартир"]),
                        claim=float(r.get("Потенциал претензии, ₽", 0.0) or 0.0)))
    return out


NO_SHOW_SHARE = 0.20       # доля записанных на приёмку, не явившихся или перенёсших визит
SLOT_SHARE = 0.30          # доля очереди, снимаемая перераспределением приёмщиков
BATCH_SHARE = 0.25         # доля очереди, снимаемая пакетной приёмкой по секциям
COMPENSATION_SHARE = 0.25  # доля приёмок без подписи, закрываемых соглашением о компенсации
REPLY_SHARE = 0.30         # доля отказов, закрываемых мотивированным ответом и повторной приёмкой
CALLED_SHARE = 0.50        # доля вызванных, переходящих к подписанию после контроля вручения
NOTIFY_SHARE = 0.35        # доля собственников без записи, записавшихся через личный кабинет
EDO_SHARE = 0.20           # доля собственников без записи, подписывающих пакет документов дистанционно
SLA_SHARE = 0.12           # снижение расчётной экспозиции под замечаниями при регламентном сроке устранения
REMARKS_HANDOVER_SHARE = 0.25
SPRINT_SHARE = 0.20        # доля экспозиции корпуса, снимаемая графиком ускоренного закрытия
CROSS_SHARE = 0.15         # доля экспозиции по виду работ, снимаемая вторым подрядчиком
FAMILIES = {"capacity": "Мощность приёмки", "legal": "Правовой режим передачи", "comms": "Работа с собственниками",
            "contractor": "Подрядчики и устранение замечаний", "settle": "Досудебное урегулирование"}

PACKAGE_SPECS = (
    ("unilateral", "ready", "expired", "Односторонняя передача после правовой проверки", R.DECISION_ROLE["unilateral"]),
    ("realloc", "ready", "queue", "Предложить более ранние даты приёмки", R.DECISION_ROLE["realloc"]),
    ("onestop", "ready", "refused", "Подписать акты после повторной приёмки", R.DECISION_ROLE["onestop"]),
    ("brigades", "remarks", None, "Устранить замечания в открытых к передаче квартирах", R.DECISION_ROLE["brigades"]),
    ("calls", "ready", "silent", "Обзвонить собственников без записи и вызова", R.DECISION_ROLE["calls"]),
)
PACKAGE_OWNERS = {key: owner for key, _, _, _, owner in PACKAGE_SPECS}


def four_week_effect(daily_effect):
    return daily_effect * (MONTH_W * 7) / 2


def _cand(c: list, key, fam, pool, title, short, roles, eff_day, basis, mech, metric):
    """Мера ЖК. roles: первая — роль справочника pf_roles, получающая поручение; needs_gd — мера требует решения ГД."""
    if eff_day <= 0:
        return
    needs_gd = R.CEO in roles
    main = R.DECISION_ROLE.get(key, PACKAGE_OWNERS.get(key, R.role(roles[0])))
    roles = [main] + [x for x in dict.fromkeys(R.role(r) for r in roles) if x not in (main, R.CEO)]
    c.append(dict(key=key, family=fam, kind=FAMILIES[fam], pool=pool, title=title, short=short, short3=R.DECISION_SHORT.get(key, short),
                  roles=roles, needs_gd=needs_gd, effect_day=float(eff_day),
                  effect=four_week_effect(eff_day), basis=basis, mechanism=mech, metric=metric))


def candidates(p: dict, ct: pd.DataFrame, remarks: pd.DataFrame | None = None) -> list[dict]:
    """Все применимые к ЖК решения с расчётным эффектом: снижение дневной экспозиции к концу 4-й недели и за 4 недели.
    Эффект рассчитывается от доли причины в экспозиции ЖК (число квартир причины × средняя дневная ставка этой причины × доля, которую снимает мера)."""
    rs = p["reasons"]
    fi = C.fmt_int
    out: list[dict] = []
    unit = lambda k: (rs[k]["risk"] / rs[k]["n"]) if rs[k]["n"] else 0.0
    mv = lambda share, k, lo=3: min(rs[k]["n"], max(1, round(share * rs[k]["n"]))) if rs[k]["n"] >= lo else 0   # пул меньше lo квартир — мера не имеет смысла
    # --- мощность приёмки
    n = mv(NO_SHOW_SHARE, "booked")
    _cand(out, "noshow", "capacity", "booked", "Ввести управление явкой на приёмку: подтверждение записи за двое суток, резервные слоты и вечерние смены",
          "Управление явкой: подтверждение записи, резервные слоты", ["Директор по заселению", "Клиентский сервис"], n * unit("booked"),
          f"{fi(rs['booked']['n'])} готовых квартир записаны на ближайшую неделю; часть визитов не состоится или переносится",
          "Доля несостоявшихся приёмок снижается; записанные квартиры не выпадают из графика передачи",
          "Передано за неделю; доля несостоявшихся приёмок")
    extra = min(max(1, round(EXTRA_CAPACITY * p["week_fact"])), p["ready"] // MONTH_W)
    if extra > 0 and rs["queue"]["n"] >= 3:
        _cand(out, "crew", "capacity", "queue", f"Рассмотреть вторую смену приёмки после проверки спроса и стоимости: до +{fi(extra)} передач в неделю по сценарию",
              "Вторая смена приёмки: дополнительные бригады", ["Генеральный директор", "Финансовый директор", "Директор по заселению"],
              min(4 * extra, rs["queue"]["n"]) * unit("queue"),
              f"По {fi(rs['queue']['n'])} готовым квартирам визит назначен позже недели. За последнюю полную неделю передано {fi(p['week_fact'])} квартир",
              "Сценарий предполагает рост темпа до 25%. Нужно подтвердить спрос на ранние визиты, число слотов и стоимость смены",
              "Подтверждённые переносы на ранние даты; дополнительные передачи за неделю; стоимость смены")
        out[-1].update(extra=extra, moved=min(MONTH_W * extra, rs["queue"]["n"]), cost=extra * MONTH_W * SHIFT_UNIT_COST)
    _cand(out, "realloc", "capacity", "queue", "Проверить загрузку приёмщиков и перераспределить смены в пользу ЖК с подтверждённой нехваткой слотов",
          "Перераспределение приёмщиков между ЖК", ["Директор по заселению", "Операционный директор"],
          mv(SLOT_SHARE, "queue") * unit("queue"),
          f"У {fi(rs['queue']['n'])} готовых квартир визит назначен позже недели",
          "Мощность приёмки по всем ЖК используется равномерно: простаивающие бригады переходят на ЖК с очередью",
          "Загрузка приёмщиков по ЖК; длина очереди на слоты")
    _cand(out, "batch", "capacity", "queue", "Перейти на пакетную приёмку по секциям: слоты закрепляются за секцией, приёмщики работают без переездов",
          "Пакетная приёмка по секциям", ["Директор по заселению", "Начальник приёмочной группы"],
          mv(BATCH_SHARE, "queue") * unit("queue"),
          f"У {fi(rs['queue']['n'])} готовых квартир визит назначен позже недели",
          "Растёт число приёмок на бригаду в смену; снижаются потери времени на переезды между корпусами",
          "Приёмок на бригаду в смену")
    # --- приёмка без подписанного акта
    n_ref = rs["refused"]["n"]
    _cand(out, "onestop", "comms", "refused", "Перейти на сквозную приёмку с выездной группой: замечания фиксируются и устраняются в день осмотра, акт подписывается в тот же визит",
          "Сквозная приёмка с выездной группой", ["Директор по заселению", "Юридический департамент"],
          mv(REFUSAL_RESOLVED, "refused") * unit("refused"),
          f"Приёмка завершена по {fi(n_ref)} квартирам, акты не подписаны",
          "Устранение мелких замечаний переносится на день осмотра, число повторных визитов сокращается",
          "Доля актов, подписанных с первого визита")
    _cand(out, "compensation", "settle", "refused", "Заключать соглашения о компенсации за просрочку передачи с подписанием акта и отказом от дальнейших претензий в согласованной части",
          "Досудебное соглашение о компенсации", ["Юридический департамент", "Финансовый директор"],
          mv(COMPENSATION_SHARE, "refused") * unit("refused"),
          f"По {fi(n_ref)} завершённым приёмкам акты не подписаны; причину нужно установить отдельно",
          "Экономический спор закрывается до суда; неустойка по ст. 333 ГК РФ фиксируется по соглашению",
          "Число подписанных актов; сумма фактической компенсации к расчётной неустойке")
    _cand(out, "reply", "legal", "refused", "Направлять мотивированные ответы на отказы и проводить повторную приёмку; при необоснованном отказе составлять односторонний акт по ч. 6 ст. 8 214-ФЗ после правовой оценки",
          "Мотивированный ответ и повторная приёмка", ["Юридический департамент", "Директор по заселению"],
          mv(REPLY_SHARE, "refused") * unit("refused"),
          f"{fi(n_ref)} завершённых приёмок без подписанного акта; применимость меры зависит от причины",
          "Обоснованные недостатки устраняются, необоснованные отказы оформляются правовым путём",
          "Доля повторных приёмок, завершённых актом")
    # --- вызовы и уведомления
    n_c = rs["called"]["n"]
    _cand(out, "called", "legal", "called", "Контролировать вручение и сроки официальных вызовов и готовить пакет документов к одностороннему акту по ч. 6 ст. 8 214-ФЗ",
          "Контроль вручения и сроков вызовов", ["Юридический департамент", "Клиентский сервис"],
          mv(CALLED_SHARE, "called", 1) * unit("called"),
          f"{fi(n_c)} готовых квартир ожидают окончания срока по официальному вызову",
          "Подтверждается юридически значимое вручение уведомления; подготовленные пакеты сокращают время до акта",
          "Доля вызовов с подтверждённым вручением")
    n_e = rs["expired"]["n"]
    _cand(out, "unilateral", "legal", "expired", "Оформлять односторонние акты по ч. 6 ст. 8 214-ФЗ там, где срок вызова истёк, уведомление вручено и мотивированного отказа нет; каждый случай проверяет юридический департамент",
          "Односторонний акт по ч. 6 ст. 8 214-ФЗ", ["Юридический департамент", "Генеральный директор"],
          mv(UNILATERAL_SHARE, "expired", 1) * unit("expired"),
          f"По {fi(n_e)} готовым квартирам срок официального вызова истёк, собственник не явился",
          "В расчётном сценарии квартира исключается из просрочки после правовой проверки и оформления передачи",
          "Число квартир, переведённых из просрочки односторонним актом")
    n_s = rs["silent"]["n"]
    _cand(out, "calls", "comms", "silent", "Провести обзвон по сегментам: сначала квартиры с наибольшей дневной ставкой и давностью просрочки, затем остальные; без ответа — официальный вызов",
          "Обзвон по сегментам с приоритетом по ставке", ["Клиентский сервис", "Юридический департамент"],
          mv(CALL_RESPONSE, "silent") * unit("silent"),
          f"{fi(n_s)} готовых квартир без записи и вызова; после контакта приходит около {C.fmt_pct(CALL_RESPONSE)} собственников",
          "Растёт доля собственников, записанных на приёмку; нерезультативные контакты переходят в официальный вызов",
          "Доля собственников, записанных после контакта")
    _cand(out, "notify", "legal", "silent", "Направить официальные уведомления о готовности по ч. 4 ст. 8 214-ФЗ с записью на приёмку в личном кабинете",
          "Уведомление по ч. 4 ст. 8 214-ФЗ с онлайн-записью", ["Юридический департамент", "Клиентский сервис"],
          mv(NOTIFY_SHARE, "silent") * unit("silent"),
          f"По {fi(n_s)} готовым квартирам нет ни записи, ни официального вызова",
          "Возникают юридически значимые сроки для собственника; запись становится самостоятельной операцией",
          "Доля уведомлённых; доля записавшихся в личном кабинете")
    _cand(out, "edo", "comms", "silent", "Перевести подписание пакета документов в электронный вид (электронный документооборот, усиленная квалифицированная подпись) для согласных собственников",
          "Дистанционное подписание пакета документов", ["Директор по заселению", "Юридический департамент"],
          mv(EDO_SHARE, "silent") * unit("silent"),
          f"{fi(n_s)} готовых квартир без записи; часть собственников проживает вне региона",
          "Подписание не требует личного визита; сокращается время от согласия собственника до акта",
          "Доля пакетов, подписанных дистанционно")
    # --- замечания и подрядчики (экспозиция под неустранёнными замечаниями)
    blk = p["risk_blocked"]
    cr = p["contractor_risk"]
    if cr and blk > 0:
        c0 = cr[0]
        _cand(out, "escalation", "contractor", "blocked",
              f"Эскалировать вопрос на уровень руководства подрядчика {c0['name']}: претензия по договору подряда и удержание из гарантийного резерва по блокирующим замечаниям",
              f"Претензионная работа и удержание из резерва: {c0['name']}", ["Генеральный директор", "Договорной отдел", "Служба качества"],
              PRESSURE_SHARE * c0["risk"],
              f"Замечания подрядчика в {fi(c0['units'])} квартирах, блокирует передачу {fi(c0['blocked'])}; потенциал удержаний до {C.fmt_money(c0['claim'])}",
              "Подрядчик несёт финансовую ответственность за срыв устранения; ресурсы направляются на блокирующие замечания",
              "Остаток блокирующих замечаний подрядчика")
    ov = p["rem"]["overdue_share"] if p.get("rem") else 0.0
    _cand(out, "sla", "contractor", "blocked", "Установить регламентный срок устранения замечаний со штрафом за каждый день просрочки и ввести ключевые показатели эффективности подрядчиков",
          "Регламентный срок устранения и штрафы подрядчикам", ["Служба качества", "Договорной отдел"],
          SLA_SHARE * blk * ov,
          f"Просрочено по регламенту {C.fmt_pct(ov)} остатка замечаний; средний срок устранения {p['rem']['avg_days']:.0f} дн." if p.get("rem") else "",
          "Срок устранения становится договорным обязательством, просрочка ведёт к штрафу и удержанию",
          "Средний срок устранения; доля замечаний, просроченных по регламенту")
    kt = p["by_korpus"]
    if len(kt) > 1:
        k0 = kt.iloc[0]
        share_k = float(k0["risk"]) / p["risk_day"] if p["risk_day"] else 0.0
        _cand(out, "sprint", "contractor", "blocked",
              f"Создать штаб оперативного закрытия по корпусу {k0['k']} ({C.fmt_pct(share_k)} экспозиции ЖК): сводная бригада и ежедневный контроль остатка замечаний",
              f"Штаб закрытия по корпусу {k0['k']}: сводная бригада", ["Операционный директор", "Служба качества", "Директор по заселению"],
              SPRINT_SHARE * float(k0["risk"]) * (blk / p["risk_day"] if p["risk_day"] else 0),
              f"Корпус {k0['k']} — {fi(int(k0['n']))} просроченных квартир и {C.fmt_pct(share_k)} дневной экспозиции ЖК",
              "Ресурсы концентрируются на корпусе с наибольшей экспозицией; остаток замечаний сокращается быстрее среднего по ЖК",
              "Остаток замечаний по корпусу; число квартир, готовых к передаче")
    if remarks is not None and len(remarks) and blk > 0:
        import pf_detail as DT
        g = DT.remark_groups(remarks)
        if len(g):
            g0 = g.iloc[0]
            sh = float(g0["Замечаний"]) / float(g["Замечаний"].sum())
            _cand(out, "cross", "contractor", "blocked",
                  f"Привлечь второго подрядчика на вид работ «{g0['Группа']}» ({C.fmt_pct(sh)} остатка замечаний) за счёт гарантийного резерва первого",
                  f"Второй подрядчик по виду работ «{g0['Группа']}»", ["Операционный директор", "Договорной отдел", "Служба качества"],
                  CROSS_SHARE * sh * blk,
                  f"На вид работ «{g0['Группа']}» приходится {C.fmt_pct(sh)} остатка замечаний, просрочено более 45 дней — {C.fmt_pct(float(g0['% просрочено']) / 100)}",
                  "Мощность устранения по проблемному виду работ удваивается; сроки перестают зависеть от одного подрядчика",
                  "Остаток замечаний по виду работ")
    remarks_group = next((g for g in p["groups"] if g["key"] == "remarks"), {"n": 0, "risk": 0.0})
    remark_units = max(1, round(REMARKS_HANDOVER_SHARE * remarks_group["n"])) if remarks_group["n"] else 0
    _cand(out, "brigades", "contractor", "blocked", "Перейти на специализированные бригады по видам работ с двухсменным графиком устранения замечаний",
          "Специализированные бригады и двухсменный график", ["Операционный директор", "Служба качества"],
          remark_units * remarks_group["risk"] / max(1, remarks_group["n"]),
          f'{fi(remarks_group["n"])} просроченных квартир открыты к передаче, но имеют замечания',
          "Сокращается время устранения одного замечания; бригады не простаивают между видами работ",
          "Средний срок устранения")
    out.sort(key=lambda d: -d["effect"])
    return out


def pick(cands: list[dict], used: set | None = None, n: int = 3) -> list[dict]:
    """Главная мера — наиболее результативная из мер, ещё не назначенных главными в других ЖК; дополнительные охватывают другие группы квартир."""
    used = used or set()
    if not cands:
        return []
    ranked = sorted(cands, key=lambda c: -c["effect"])
    main = next((c for c in ranked if c["key"] not in used), ranked[0])
    out, pools, fams = [main], {main["pool"]}, {main["family"]}
    for fam_strict in (True, False):
        for c in ranked:
            if len(out) >= n:
                break
            if c in out or c["pool"] in pools or (fam_strict and c["family"] in fams):
                continue
            out.append(c); pools.add(c["pool"]); fams.add(c["family"])
    return out


def decisions(p: dict, ct: pd.DataFrame, remarks: pd.DataFrame | None = None, used: set | None = None) -> list[dict]:
    return pick(candidates(p, ct, remarks), used)


PACKAGE_RATES = {"unilateral": 18_000, "realloc": 12_000, "onestop": 30_000, "brigades": 45_000, "calls": 5_000}


def week_package(projects, focus):
    """Пакет мер по непересекающимся группам квартир. Затраты — на плановый результат за четыре недели."""
    package = []
    for key, group_key, subreason, title, owner in PACKAGE_SPECS:
        items = []
        for project in projects:
            if key == "unilateral" and project["key"] != focus["key"]:
                continue
            candidate = next((c for c in project["cands"] if c["key"] == key), None)
            if not candidate:
                continue
            cohort = (project["reasons"][subreason] if subreason
                      else next(g for g in project["groups"] if g["key"] == group_key))
            average = cohort["risk"] / cohort["n"]
            units = round(candidate["effect_day"] / average)
            items.append(dict(project=project, eligible=cohort["n"], units=units, average=average,
                              effect_day=candidate["effect_day"]))
        if not items:
            continue
        result_units = sum(item["units"] for item in items)
        week_units = (result_units + MONTH_W - 1) // MONTH_W
        for item in items:
            item["week_units"] = item["units"] // MONTH_W
        order = sorted(items, key=lambda item: -(item["units"] % MONTH_W))
        for item in order[:week_units - sum(item["week_units"] for item in items)]:
            item["week_units"] += 1
        daily = sum(item["effect_day"] for item in items)
        package.append(dict(key=key, group=group_key, subreason=subreason, title=title, owner=owner, items=items,
                            eligible=sum(item["eligible"] for item in items), units=result_units, week_units=week_units,
                            effect_day=daily, effect=four_week_effect(daily), cost=result_units * PACKAGE_RATES[key]))
    return package


def handover_plan(projects, package, group_keys):
    """База — готовые с записью. Резерв — заявки из пакета в пределах мощности."""
    plan = []
    for project in projects:
        capacity = int(round(project["gross_left"] * 1.10))
        booked = project["reasons"]["booked"]
        booked_n = min(booked["n"], capacity)
        booked_risk = booked_n * booked["risk"] / booked["n"] if booked["n"] else 0.0
        by_group = dict.fromkeys(group_keys, 0)
        by_group["ready"] = booked_n
        reserve_risk = 0.0
        for measure in package:
            for item in measure["items"]:
                if item["project"]["key"] != project["key"]:
                    continue
                n = min(item["week_units"], capacity - sum(by_group.values()))
                by_group[measure["group"]] += n
                reserve_risk += n * item["average"]
        total, backlog = sum(by_group.values()), project["overdue_kv"]
        new = project["next_week_new"]
        risk_before = project["risk_day"] + project["next_week_new_risk"]
        plan.append(dict(project=project, groups=by_group, baseline=backlog, capacity=capacity,
                         booked=booked_n, reserve=total-booked_n, total=total, new=new,
                         closing_base=backlog-booked_n+new, closing=backlog-total+new,
                         risk_base=max(0.0, risk_before-booked_risk),
                         risk_total=max(0.0, risk_before-booked_risk-reserve_risk)))
    return plan


def incremental_package_forecast(projects, package):
    """Прогноз от текущего темпа с ограничением эффекта оставшейся просрочкой ЖК."""
    daily_by_project = {}
    for measure in package:
        for item in measure["items"]:
            key = item["project"]["key"]
            daily_by_project[key] = daily_by_project.get(key, 0.0) + item["effect_day"]
    rows = []
    for project in projects:
        key = project["key"]
        forecast_data = forecast(project)
        simulation = forecast_data["base"]
        potential = daily_by_project.get(key, 0.0)
        previous_credit = 0.0
        previous_accrued = 0.0
        effect = 0.0
        for week in range(1, MONTH_W + 1):
            _, remaining, accrued = simulation["path"][min(week, len(simulation["path"])-1)]
            credit = min(potential * week / MONTH_W, remaining * forecast_data["r_unit"])
            effect += min(accrued-previous_accrued, 7 * (previous_credit+credit)/2)
            rows.append(dict(key=key, week=week, base=accrued, effect=effect, day=credit,
                             closing=remaining, potential=potential))
            previous_credit, previous_accrued = credit, accrued
    return rows
