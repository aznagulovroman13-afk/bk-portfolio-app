"""Матрёшка ЖК → дом (корпус) → квартира: те же квартиры среза, та же неустойка 2026 года, что в сводке и в «Финансах».

Неустойка квартиры за просрочку передачи = цена ДДУ × ставка/150 × дни начисления 2026 года (коэффициент квартиры среза).
Неустойка за замечания = расчёт pf_penalty на квартиру с просроченными замечаниями (одинаковая сумма на квартиру).
Этап задержки квартиры: для переданных с нарушением срока — критический этап ЖК (диаграмма Ганта), для непереданных — по статусу.
"""
from __future__ import annotations

import pandas as pd

import pf_core as C
import pf_gantt as GT
import pf_penalty as PN

DRILL_SCHEMA = "d3"
KV = "Квартира"


def _status(r) -> str:
    s = str(r["Исходный статус"])
    if s.startswith("Принята"):
        return "Принята"
    if s == "Открыта к передаче":
        rec = str(r.get("Статус записи собственника") or "")
        return {"Запланировано": "Назначена приёмка", "Не состоялось": "Осмотр не состоялся"}.get(rec, "Открыта к передаче")
    return s


def _stage(r, crit: str) -> str:
    s = str(r["Исходный статус"])
    if s.startswith("Принята"):
        return crit if r["Просрочка ДДУ"] == C.LATE else ("fix" if r["Просрочено (регл)"] > 0 else "")
    if bool(r["Мот. отказ / снятие готовности"]) or s == "В ОЗ, готовность не открыта":
        return "ready"
    if s == "Ключи в ОЗ не переданы":
        return "keys"
    if s == "Не принята":
        return "fix" if r["Замечаний открыто"] > 0 else "app"
    if s == "Открыта к передаче":
        if pd.isna(r["Официальный вызов, дн. назад"]) and not str(r.get("Статус записи собственника") or ""):
            return "notice"
        return "inspect"
    return "fix" if r["Просрочено (регл)"] > 0 else ""


def _d(x):
    return f"{pd.Timestamp(x):%d.%m.%y}" if pd.notna(x) else "—"


def build(d: dict, sched: dict, price: float, pen_row: dict, cause_key: str) -> dict:
    """Квартиры и дома ЖК. Суммы квартир = дома, суммы домов = ЖК (просрочка, остаток 2026, замечания, неустойка 2026)."""
    A = d["units"]
    kv = A[A["Тип объекта"].eq(KV)].copy()
    cd = d["calc_date"]
    rem26, flats = pen_row["remarks"][2026], pen_row["flats_overdue_remarks"]
    per_rem = rem26 / flats if flats else 0.0
    crit = sched["critical"]
    names = {k: short for k, short, *_ in GT.STAGES}
    owners = {k: GT.owner(k, cause_key, d) for k in GT.STAGE_KEYS}
    done = C.transferred_mask(kv)
    due = pd.to_datetime(kv["Срок по ДДУ"])
    apts = []
    for col, default in (("Коэф. неустойки на 1 ₽ цены (верх)", 0.0), ("Просрочено (регл)", 0), ("Замечаний открыто", 0), ("Критических", 0),
                         ("Просрочка ДДУ факт, дн.", 0), ("Дней для неустойки (после моратория)", 0), ("Ставка ЦБ на срок ДДУ, %", 0.0),
                         ("Мот. отказ / снятие готовности", False), ("Официальный вызов, дн. назад", float("nan")),
                         ("Запись через, дн.", float("nan")), ("Статус записи собственника", ""), ("Дата принятия собственником", pd.NaT),
                         ("Односторонний ПА", pd.NA), ("Корпус", "1"), ("Результат передачи", "")):
        if col not in kv.columns:
            kv[col] = default
    for col in ("Просрочено (регл)", "Замечаний открыто", "Критических", "Просрочка ДДУ факт, дн.", "Дней для неустойки (после моратория)"):
        kv[col] = pd.to_numeric(kv[col], errors="coerce").fillna(0).astype(int)
    kv["Коэф. неустойки на 1 ₽ цены (верх)"] = pd.to_numeric(kv["Коэф. неустойки на 1 ₽ цены (верх)"], errors="coerce").fillna(0.0)
    for (i, r), dn, du in zip(kv.iterrows(), done, due):
        ddu = float(r["Коэф. неустойки на 1 ₽ цены (верх)"] or 0) * price
        rp = per_rem if r["Просрочено (регл)"] > 0 else 0.0
        stage = _stage(r, crit)
        over = r["Просрочка ДДУ"] == C.NT_OVERDUE
        problem = bool(over or r["Просрочено (регл)"] > 0 or ddu > 0)
        call = cd - pd.Timedelta(days=int(r["Официальный вызов, дн. назад"])) if pd.notna(r["Официальный вызов, дн. назад"]) else None
        visit = cd + pd.Timedelta(days=int(r["Запись через, дн."])) if pd.notna(r["Запись через, дн."]) else None
        apts.append(dict(
            id=str(r["Объект"]), house=str(r["Корпус"]), status=_status(r), over=bool(over),
            late=int(r["Просрочка ДДУ факт, дн."] or 0), days26=int(r["Дней для неустойки (после моратория)"] or 0),
            rate=float(r["Ставка ЦБ на срок ДДУ, %"]) if pd.notna(r["Ставка ЦБ на срок ДДУ, %"]) else 0.0, ddu=ddu, rem=rp, total=ddu + rp,
            open=int(r["Замечаний открыто"]), overdue_rem=int(r["Просрочено (регл)"]), crit_rem=int(r["Критических"]),
            stage=stage, stage_name=names.get(stage, "—"), owner=owners[stage]["short"] if stage else "—",
            owner_company=owners[stage]["company"] if stage else "",
            left26=bool(du.year == 2026 and not dn), done=bool(dn), problem=problem,
            due=du, call=call, visit=visit, visit_status=str(r.get("Статус записи собственника") or ""),
            accepted=r["Дата принятия собственником"], result=str(r.get("Результат передачи") or ""), unilateral=bool(r["Односторонний ПА"]) if pd.notna(r["Односторонний ПА"]) else False))
    houses = []
    for h in sorted({a["house"] for a in apts}, key=lambda x: (len(x), x)):
        items = sorted([a for a in apts if a["house"] == h], key=lambda a: (-a["total"], -a["late"], a["id"]))
        by_owner = {}
        for a in items:
            if a["stage"]:
                by_owner[a["owner"]] = by_owner.get(a["owner"], 0.0) + a["total"]
        resp = max(by_owner, key=lambda o: (by_owner[o], o == sched["responsible"]["short"])) if by_owner else "—"
        comp = next((a["owner_company"] for a in items if a["owner"] == resp and a["owner_company"]), "")
        dues = pd.Series([a["due"] for a in items])
        houses.append(dict(
            house=h, apts=items, total_kv=len(items), done=sum(a["done"] for a in items), left26=sum(a["left26"] for a in items),
            left=sum(not a["done"] for a in items), over=sum(a["over"] for a in items), ddu=sum(a["ddu"] for a in items),
            rem=sum(a["rem"] for a in items), open=sum(a["open"] for a in items), problems=sum(a["problem"] for a in items),
            due=dues.median(), resp=resp, resp_company=comp))
    return dict(key=d["key"], houses=houses, apts=apts, price=price, per_rem=per_rem, late_days=pen_row["late_days"],
                totals=dict(over=sum(h["over"] for h in houses), left26=sum(h["left26"] for h in houses),
                            ddu=sum(h["ddu"] for h in houses), rem=sum(h["rem"] for h in houses), open=sum(h["open"] for h in houses)))


def timeline(a: dict) -> list[tuple[str, str]]:
    """Короткая хронология квартиры: срок ДДУ → уведомление → осмотр → замечания → акт."""
    out = [("Срок ДДУ", _d(a["due"]))]
    out.append(("Уведомление", _d(a["call"]) if a["call"] is not None else ("направлено" if a["done"] else "не направлено")))
    if a["visit"] is not None:
        out.append(("Осмотр", f'{_d(a["visit"])} · {a["visit_status"].lower() or "запланирован"}'))
    elif a["done"]:
        out.append(("Осмотр", "проведён"))
    else:
        out.append(("Осмотр", "не назначен"))
    out.append(("Замечания", f'открыто {a["open"]}, просрочено {a["overdue_rem"]}' if a["open"] or a["overdue_rem"] else "нет"))
    out.append(("Акт", (_d(a["accepted"]) + (" · односторонний" if a["unilateral"] else "")) if a["done"] else "не подписан"))
    return out


# ── HTML: дома → квартиры → карточка квартиры (уровни матрёшки внутри карточки ЖК) ──────────────────────────────
import html as _html

f = C.fmt_int
MONTHS = ("янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")
HIST_MONTH_W = (4, 5, 6, 6, 7, 8, 8, 9, 10, 11, 12, 14)     # сезонность передач ранее переданных очередей


def mln(v, nd=1):
    return f"{v / 1e6:,.{nd}f}".replace(",", "\u00a0").replace(".", ",")


def rub(v):
    return f"{f(round(v))} ₽" if v else "—"


def split_months(total: int, weights=HIST_MONTH_W) -> list[int]:
    """Разбивка годового числа по месяцам (метод наибольших остатков): сумма месяцев = году."""
    s = sum(weights)
    raw = [total * w / s for w in weights]
    out = [int(x) for x in raw]
    for i in sorted(range(12), key=lambda i: -(raw[i] - out[i]))[: total - sum(out)]:
        out[i] += 1
    return out


# колонки квартир: ключ → (заголовок, подсказка, класс, функция ячейки)
def _apt_cells(a, price):
    return {
        "id": ("Квартира", "", "", _html.escape(a["id"])),
        "status": ("Статус", "", "", _html.escape(a["status"]) + ('<i class="dr-over">Срок передачи нарушен</i>' if a["over"] else "")),
        "late": ("Дней", "Дней просрочки по ДДУ на дату среза", "r", f(a["late"]) if a["late"] else "—"),
        "ddu": ("Задержка, ₽", "Неустойка 2026 за просрочку передачи, ч. 2 ст. 6 214-ФЗ", "r", rub(a["ddu"])),
        "rem": ("Замечания, ₽", "Неустойка 2026 за просрочку устранения, ч. 8 ст. 7 214-ФЗ", "r", rub(a["rem"])),
        "open": ("Замеч.", "Открытых замечаний / из них просрочено", "r", f'{a["open"]}/{a["overdue_rem"]}' if a["open"] or a["overdue_rem"] else "—"),
        "stage": ("Этап", "Этап, на котором возникла задержка", "", _html.escape(a["stage_name"])),
        "owner": ("Ответственный", "", "", _html.escape(a["owner"])),
        "due": ("Срок ДДУ", "", "r", f'{a["due"]:%m.%Y}'),
        "accepted": ("Акт", "Дата передаточного акта", "r", _d(a["accepted"])),
    }


def apt_l4(a, dr) -> str:
    """Уровень 4: хронология и расчёт неустойки квартиры."""
    tl = "".join(f'<li><span>{_html.escape(k)}</span><b>{_html.escape(v)}</b></li>' for k, v in timeline(a))
    calc = []
    if a["ddu"]:
        calc.append(f'<p><b>Задержка:</b> цена ДДУ {f(round(dr["price"]))} ₽ × {str(a["rate"]).replace(".", ",")}% / 150 × {a["days26"]} дн. 2026 = '
                    f'<b>{rub(a["ddu"])}</b> · ч. 2 ст. 6 214-ФЗ; период моратория ПП № 326 (22.03.2024–31.12.2025) не начисляется.</p>')
    if a["rem"]:
        calc.append(f'<p><b>Замечания:</b> 1/150 ставки от стоимости устранения {f(round(PN.CLAIM_BASE_PER_FLAT))} ₽ × {dr["late_days"]} дн. '
                    f'сверх 45 дней, не более 3% цены = <b>{rub(a["rem"])}</b> · ч. 8 ст. 7 214-ФЗ.</p>')
    if not calc:
        calc.append('<p>Неустойка 2026 года не начислена.</p>')
    return f'<div class="dr-l4"><ol class="dr-tl">{tl}</ol>{"".join(calc)}</div>'


MODES = {
    # режим: (фильтр квартир, колонки квартир, сортировка, текст фильтра по умолчанию)
    "all": (lambda a: a["problem"], ("id", "status", "late", "ddu", "rem", "open", "stage", "owner"), "total", "проблемные"),
    "t2026": (lambda a: a["done"] and pd.notna(a["accepted"]) and pd.Timestamp(a["accepted"]).year == 2026,
              ("id", "accepted", "late", "ddu", "rem", "open"), "accepted", None),
    "left2026": (lambda a: a["left26"], ("id", "status", "due", "late", "stage", "owner"), "due", None),
    "over": (lambda a: a["over"], ("id", "status", "late", "ddu", "stage", "owner"), "late", None),
    "ddu": (lambda a: a["ddu"] > 0, ("id", "status", "late", "ddu", "stage", "owner"), "ddu", None),
    "rem": (lambda a: a["rem"] > 0, ("id", "status", "open", "rem", "owner"), "rem", None),
}
SORT = {"total": lambda a: (-a["total"], a["id"]), "accepted": lambda a: (pd.Timestamp(a["accepted"]), a["id"]),
        "due": lambda a: (a["due"], a["id"]), "late": lambda a: (-a["late"], a["id"]), "ddu": lambda a: (-a["ddu"], a["id"]),
        "rem": lambda a: (-a["rem"], a["id"])}


def _row(cells, cls="dr-row"):
    return f'<div class="{cls}">' + "".join(f'<span class="{c}">{v}</span>' for c, v in cells) + "</div>"


def apts_html(dr, items, cols, uid, extra=None) -> str:
    """Список квартир; extra — квартиры, скрытые фильтром (раскрываются переключателем «Все квартиры»)."""
    if not items and not extra:
        return '<p class="dr-empty">Квартир нет</p>'
    head = _row([("r" if _apt_cells(items[0] if items else extra[0], 0)[k][2] else "", f'<b title="{_html.escape(_apt_cells(items[0] if items else extra[0], 0)[k][1])}">{_apt_cells(items[0] if items else extra[0], 0)[k][0]}</b>') for k in cols], "dr-row dr-h")
    def one(a, hide=False):
        c = _apt_cells(a, dr["price"])
        return (f'<details class="dr-apt{" ok" if hide else ""}" id="apt-{_html.escape(a["id"])}"><summary>'
                + _row([(c[k][2], c[k][3]) for k in cols]) + f'</summary>{apt_l4(a, dr)}</details>')
    body = "".join(one(a) for a in items) + "".join(one(a, True) for a in (extra or []))
    toggle = ""
    if extra:
        toggle = (f'<input type="checkbox" id="dr-all-{uid}" class="dr-all"><label class="dr-tog" for="dr-all-{uid}">'
                  f'<span class="o">▾ Все квартиры · ещё {len(extra)}</span><span class="c">▴ Только проблемные</span></label>')
    return f'<div class="dr-apts" style="--cols:{len(cols)}">{toggle}<div class="dr-list">{head}{body}</div></div>'


HOUSE_COLS = {
    "all": (("total_kv", "Квартир"), ("done", "Передано"), ("left26", "Остаток 2026"), ("over", "Нарушен срок, кв."),
            ("due", "Срок ДДУ"), ("ddu", "Задержка 2026"), ("rem", "Замечания 2026")),
    "t2026": (("t2026", "Передано 2026"), ("ontime", "В срок"), ("lateacc", "С нарушением"), ("unil", "Односторонние")),
    "left2026": (("left26", "Остаток 2026"), ("due", "Срок ДДУ"), ("over", "Нарушен срок, кв.")),
    "over": (("over", "Нарушен срок, кв."), ("maxlate", "Макс. дней"), ("ddu", "Задержка 2026")),
    "ddu": (("ddun", "Квартир"), ("ddu", "Задержка 2026")),
    "rem": (("remn", "Квартир"), ("open", "Замечаний"), ("rem", "Замечания 2026")),
}


def _house_val(h, k, items):
    acc = [a for a in h["apts"] if a["done"] and pd.notna(a["accepted"]) and pd.Timestamp(a["accepted"]).year == 2026]
    v = {
        "total_kv": f(h["total_kv"]), "done": f(h["done"]), "left26": f(h["left26"]), "over": f(h["over"]),
        "due": f'{h["due"]:%m.%Y}' if pd.notna(h["due"]) else "—", "ddu": mln(h["ddu"]), "rem": mln(h["rem"], 2),
        "resp": _html.escape(h["resp"]) + (f'<i>{_html.escape(h["resp_company"])}</i>' if h["resp_company"] else ""),
        "t2026": f(len(acc)), "lateacc": f(sum(a["late"] > 0 for a in acc)),
        "ontime": f(sum(a["late"] == 0 for a in acc)), "unil": f(sum(a["unilateral"] for a in acc)),
        "maxlate": f(max([a["late"] for a in items], default=0)), "ddun": f(len(items)), "remn": f(len(items)), "open": f(sum(a["open"] for a in items)),
    }
    return v[k]


def houses_html(dr, mode="all", uid="") -> str:
    """Уровень «Дома»: строка дома раскрывает квартиры (уровень «Квартиры»), строка квартиры — её карточку."""
    flt, cols, sort, _ = MODES[mode]
    hc = HOUSE_COLS[mode]
    tips = {"ddu": "Неустойка 2026 за просрочку передачи, млн ₽", "rem": "Неустойка 2026 за просрочку устранения замечаний, млн ₽",
            "due": "Медианный срок по ДДУ квартир дома"}
    head = _row([("", "<b>Дом</b>")] + [("r" if k != "resp" else "resp", f'<b title="{tips.get(k, "")}">{t}</b>') for k, t in hc], "dr-row dr-h")
    out = []
    for h in dr["houses"]:
        items = sorted([a for a in h["apts"] if flt(a)], key=SORT[sort])
        if mode != "all" and not items:
            continue
        extra = sorted([a for a in h["apts"] if not flt(a)], key=SORT[sort]) if mode == "all" else None
        cells = [("", f'Корпус {_html.escape(h["house"])}')] + [("r" if k != "resp" else "resp", _house_val(h, k, items)) for k, _ in hc]
        out.append(f'<details class="dr-house" id="house-{dr["key"]}-{h["house"]}"><summary>{_row(cells)}</summary>'
                   + apts_html(dr, items, cols, f'{uid}{dr["key"]}-{h["house"]}', extra) + "</details>")
    tot = ""
    if mode == "all":
        t = dr["totals"]
        tv = {"total_kv": f(sum(h["total_kv"] for h in dr["houses"])), "done": f(sum(h["done"] for h in dr["houses"])),
              "left26": f(t["left26"]), "over": f(t["over"]), "due": "", "ddu": mln(t["ddu"]), "rem": mln(t["rem"], 2), "resp": ""}
        tot = _row([("", "<b>Итого ЖК</b>")] + [("r" if k != "resp" else "resp", f'<b>{tv[k]}</b>') for k, _ in hc], "dr-row dr-tot")
    return f'<div class="dr-houses" style="--hcols:{len(hc) + 1}">{head}{"".join(out)}{tot}</div>'
