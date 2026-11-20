"""Детализация ЖК: корпуса, шахматка, замечания, подрядчики. Одни и те же функции для каждого ЖК."""
from __future__ import annotations

import html

import pandas as pd

import pf_core as C

# статусы и пастельные цвета шахматки: заливка, рамка, текст
STATUS = {
    "Принята (ПА)": ("pa", "Принята по передаточному акту", ("#E9F6EE", "#BFE2CB", "#23704A")),
    "Принята (односторонний ПА)": ("one", "Односторонний передаточный акт", ("#F2F9F4", "#D3EBDB", "#4C8463")),
    "Открыта к передаче": ("wait", "Открыта к передаче", ("#FFF5D9", "#EBD596", "#865900")),
    "В ОЗ, готовность не открыта": ("oz", "В ОЗ, готовность не открыта", ("#EAF3FC", "#C3DAF1", "#2C5F92")),
    "Ключи в ОЗ не переданы": ("keys", "Ключи в ОЗ не переданы", ("#FFFFFF", "#CBD3DD", "#4F5D6E")),
    "Не принята": ("na", "Не принята", ("#FFF0EE", "#EEC5C0", "#A43D3E")),
}
TYPE_SHORT = {"Квартира": "", "НХП": "НХП", "Машиноместо": "М/м", "Нежилое": "Неж."}
AGE_LABELS = [("до 4 недель", range(0, 4)), ("4–8 недель", range(4, 8)), ("8–12 недель", range(8, 12)),
              ("12–25 недель", [12]), ("26–51 недель", [13]), ("52 недели и более", [14])]


def chess_css() -> str:
    rules = "".join(f".cb .{c}{{background:{p[0]};border-color:{p[1]};color:{p[2]}}}.cb i.{c}{{background:{p[0]};border:1px solid {p[1]}}}"
                    for c, _, p in STATUS.values())
    return ("<style>.cb{background:#fff;border:1px solid #D5DBE3;border-radius:4px;padding:14px 16px;overflow-x:auto}"
            ".cb .secs{display:flex;gap:22px;align-items:flex-start}.cb .sec1{flex:none}"
            ".cb h5{margin:0 0 6px;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:#7A8494;font-weight:700}"
            ".cb .fl{display:flex;align-items:center;gap:4px;margin-bottom:3px}.cb .fn{width:26px;text-align:right;font-size:10.5px;color:#7A8494;"
            "font-variant-numeric:tabular-nums;padding-right:4px}.cb .row{display:flex;flex-wrap:wrap;gap:3px;max-width:640px}"
            ".cb .c{position:relative;width:46px;height:34px;border:1px solid;border-radius:4px;font-size:11px;line-height:1.1;"
            "display:flex;flex-direction:column;align-items:center;justify-content:center;font-variant-numeric:tabular-nums}"
            ".cb .c b{font-weight:700}.cb .c s{text-decoration:none;font-size:8.5px;opacity:.85}"
            ".cb .c.d::after{content:'';position:absolute;top:2px;right:2px;width:5px;height:5px;border-radius:50%;background:#B3261E}"
            ".cb .c.k::before{content:'';position:absolute;top:2px;left:2px;width:5px;height:5px;border-radius:1px;background:#0B1F3A}"
            ".cb .lg{display:flex;flex-wrap:wrap;gap:6px 18px;margin:10px 0 0;font-size:12px;color:#4A5568}"
            ".cb .lg span{display:inline-flex;align-items:center;gap:6px}.cb .lg i{width:12px;height:12px;border-radius:3px;display:inline-block}"
            ".cb .lg i.dm{background:#B3261E;border:none;border-radius:50%;width:7px;height:7px}"
            ".cb .lg i.km{background:#0B1F3A;border:none;border-radius:1px;width:7px;height:7px}" + rules + "</style>")


def _d(v) -> str:
    return "" if v is None or pd.isna(v) else pd.Timestamp(v).strftime("%d.%m")


def _num(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def korpus_list(A: pd.DataFrame) -> list[str]:
    ks = sorted(A["Корпус"].astype(str).unique(), key=lambda k: (k.startswith("П"), [(_num(x) if x.isdigit() else 0, x) for x in k.replace("П", "").split(".")]))
    return ks


def chess_html(A: pd.DataFrame, korpus: str) -> tuple[str, dict]:
    """Шахматка корпуса: секции → этажи → помещения; цвет — статус, красная точка — срок ДДУ нарушен, синяя — есть критические замечания."""
    a = A[A["Корпус"].astype(str) == str(korpus)].copy()
    a["_sec"] = a["Секция"].astype(str)
    a["_fl"] = a["Этаж"].astype(int)
    a["_n"] = a["Квартира"].astype(int)
    counts: dict[str, int] = {}
    secs = []
    for sec, gs in sorted(a.groupby("_sec"), key=lambda kv: _num(kv[0])):
        rows = []
        for fl, g in sorted(gs.groupby("_fl"), key=lambda kv: -kv[0]):
            cells = []
            for r in g.sort_values("_n").to_dict("records"):
                code, label, _ = STATUS.get(r["Исходный статус"], STATUS["Ключи в ОЗ не переданы"])
                counts[label] = counts.get(label, 0) + 1
                if code in ("pa", "one"):
                    dt = _d(r["Дата принятия собственником"])
                elif code == "keys":
                    dt = ("≈" + _d(r["Плановая дата ключей в ОЗ"])) if pd.notna(r["Плановая дата ключей в ОЗ"]) else ""
                else:
                    dt = ""
                bad = r["Просрочка ДДУ"] == C.NT_OVERDUE
                crit = _num(r["Критических"]) > 0
                days = r["Просрочка ДДУ факт, дн."]
                tip = (f"{r['Тип объекта']} {r['_n']} · {label}" + (f" · срок ДДУ нарушен, {_num(days)} дн." if bad else "")
                       + (f" · замечаний {_num(r['Замечаний открыто'])}, критических {_num(r['Критических'])}" if _num(r["Замечаний открыто"]) else ""))
                t = TYPE_SHORT.get(r["Тип объекта"], "")
                cells.append(f'<div class="c {code}{" d" if bad else ""}{" k" if crit else ""}" title="{html.escape(tip)}">'
                             f'<b>{html.escape(t + (" " if t else "") + str(r["_n"]))}</b><s>{dt}</s></div>')
            rows.append(f'<div class="fl"><div class="fn">{fl}</div><div class="row">{"".join(cells)}</div></div>')
        secs.append(f'<div class="sec1"><h5>Секция {html.escape(str(sec))}</h5>{"".join(rows)}</div>')
    legend = "".join(f'<span><i class="{c}"></i>{html.escape(lab)} — {C.fmt_int(counts.get(lab, 0))}</span>' for c, lab, _ in STATUS.values())
    legend += '<span><i class="dm"></i>срок ДДУ нарушен</span><span><i class="km"></i>есть критические замечания</span>'
    out = f'{chess_css()}<div class="cb"><div class="secs">{"".join(secs)}</div><div class="lg">{legend}</div></div>'
    return out, {"units": int(len(a)), "counts": counts}


def korpus_table(A: pd.DataFrame, price: float) -> pd.DataFrame:
    a = A.assign(k=A["Корпус"].astype(str))
    tr = C.transferred_mask(a)
    nt = a["Просрочка ДДУ"].eq(C.NT_OVERDUE)
    kv = a["Тип объекта"].eq("Квартира")
    ready = C.ready_mask(a) & nt & kv
    risk = (a["Ставка ЦБ на срок ДДУ, %"].fillna(0) / 100 / 150 * price).where(nt & kv, 0.0)
    g = a.assign(tr=tr, nt=nt, ntkv=nt & kv, ready=ready, risk=risk).groupby("k").agg(
        n=("Объект", "size"), tr=("tr", "sum"), nt=("nt", "sum"), ntkv=("ntkv", "sum"), ready=("ready", "sum"),
        risk=("risk", "sum"), rem=("Замечаний открыто", "sum"), crit=("Критических", "sum"))
    g = g.reindex([k for k in korpus_list(A) if k in g.index])
    out = pd.DataFrame({
        "Корпус": g.index, "Помещений": g["n"].values, "Передано, %": (100 * g["tr"] / g["n"]).round(1).values,
        "Просрочка по ДДУ": g["nt"].values, "из них квартир": g["ntkv"].values, "Готовы к передаче": g["ready"].values,
        "Дневная экспозиция, ₽": g["risk"].round().astype(int).values, "Замечаний": g["rem"].astype(int).values,
        "Критических": g["crit"].astype(int).values})
    return out


def remark_groups(rem: pd.DataFrame) -> pd.DataFrame:
    g = rem.assign(c=rem["n"].where(rem["Важность"].eq("Критическое"), 0), o=rem["n"].where(rem["Просрочено45"], 0),
                   b=rem["n"].where(rem["Блокирует"], 0)).groupby("Группа", observed=True).agg(n=("n", "sum"), c=("c", "sum"), o=("o", "sum"), b=("b", "sum"))
    g = g.sort_values("n", ascending=False)
    return pd.DataFrame({"Группа": g.index, "Замечаний": g["n"].values, "Доля, %": (100 * g["n"] / g["n"].sum()).round(1).values,
                         "Критических": g["c"].values, "Просрочено более 45 дней": g["o"].values,
                         "% просрочено": (100 * g["o"] / g["n"]).round(1).values, "Блокируют передачу": g["b"].values})


def remark_importance(rem: pd.DataFrame) -> pd.Series:
    s = rem.groupby("Важность", observed=True)["n"].sum()
    return s.reindex(["Критическое", "Значительное", "Стандартное"]).fillna(0).astype(int)


def remark_ages(rem: pd.DataFrame) -> pd.DataFrame:
    w = rem.groupby("Нед", observed=True)["n"].sum()
    return pd.DataFrame({"Возраст замечания": [lab for lab, _ in AGE_LABELS],
                         "Замечаний": [int(sum(w.get(i, 0) for i in rg)) for _, rg in AGE_LABELS]})


def remark_korpus(rem: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    g = rem.groupby("Корпус", observed=True).agg(n=("n", "sum")).sort_values("n", ascending=False).head(top)
    return g.reset_index()
