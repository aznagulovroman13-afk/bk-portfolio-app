"""Графики Ганта по этапам передачи: план и факт, критический этап, связь задержки с неустойкой и рисками.

Расчётная модель: опорная дата — медианный срок по ДДУ просроченных квартир ЖК; итоговая задержка — медианная
просрочка этих квартир (дни); задержка распределяется между критическим и сопутствующим этапом по причине,
соответствующей главному решению ЖК. Неустойка 2026 года по ч. 2 ст. 6 214-ФЗ делится между этапами пропорционально
их задержке; неустойка по ч. 8 ст. 7 относится к этапу «Устранение замечаний».
"""
from __future__ import annotations

import pandas as pd

import pf_core as C
import pf_penalty as PN

GANTT_SCHEMA = "g1"

# этап → (начало, окончание) плана в днях относительно срока по ДДУ
STAGES = (
    ("rnv", "РНВ", "Разрешение на ввод объекта в эксплуатацию", -240, -200),
    ("keys", "Ключи в ОЗ", "Передача ключей в офис заселения / обслуживающую организацию", -200, -170),
    ("ready", "Открытие готовности", "Подтверждение готовности квартир к передаче", -170, -120),
    ("notice", "Уведомления", "Сообщения о готовности к передаче по ч. 4 ст. 8 214-ФЗ", -120, -85),
    ("inspect", "Осмотры", "Осмотры и приёмки квартир", -85, -20),
    ("fix", "Устранение замечаний", "Устранение недостатков в регламентный срок 45 дней", -65, -10),
    ("app", "Подписание АПП", "Подписание передаточных актов", -45, 0),
)
STAGE_KEYS = tuple(s[0] for s in STAGES)

# главное решение ЖК → критический этап, сопутствующий этап, причина
CAUSES = {
    "calls": ("inspect", "notice", "Неявка на осмотр: дольщики записываются позже 7 дней после уведомления"),
    "escalation": ("fix", "inspect", "Подрядчик не соблюдает регламент устранения, решения на уровне участка не исполняются"),
    "notify": ("notice", "inspect", "Сообщения о готовности по ч. 4 ст. 8 направлены с задержкой, срок принятия не запущен"),
    "onestop": ("inspect", "fix", "Повторные осмотры: замечания устраняются отдельными выездами, цикл осмотр—устранение растянут"),
    "sla": ("fix", "app", "Нет регламентного срока устранения: замечания открыты дольше 45 дней"),
    "unilateral": ("app", "inspect", "Уклонение от подписания актов, односторонние акты по ч. 6 ст. 8 не оформляются"),
    "cross": ("fix", "keys", "Один подрядчик по виду работ «Двери»: очередь на устранение; ключи в ОЗ переданы позже"),
    "sprint": ("ready", "inspect", "Мотивированные отказы по корпусу 4: готовность снимается и открывается повторно"),
    "realloc": ("inspect", "rnv", "Пропускная способность приёмки ниже потока записей; ввод объекта сдвинут"),
    "brigades": ("ready", "fix", "Отделка не завершена: готовность квартир не открыта в плановый срок"),
}
DEFAULT_CAUSE = ("app", "inspect", "Передача актов идёт ниже планового темпа")
CRITICAL_SHARE = 0.7


def project_schedule(d: dict, p: dict, pen: dict) -> dict:
    """План и факт по этапам ЖК, задержки по этапам и связь с неустойкой."""
    A = d["units"]
    kv = A[A["Тип объекта"].eq("Квартира")]
    over = kv[kv["Просрочка ДДУ"].isin([C.NT_OVERDUE, C.LATE])]
    if len(over):
        anchor = pd.to_datetime(over["Срок по ДДУ"]).median().normalize()
        delay = int(round(over["Просрочка ДДУ факт, дн."].median()))
    else:
        anchor = pd.to_datetime(kv["Срок по ДДУ"]).median().normalize()
        delay = 0
    key = p["decisions"][0]["key"] if p.get("decisions") else ""
    crit, sec, cause = CAUSES.get(key, DEFAULT_CAUSE)
    slip = {k: 0 for k in STAGE_KEYS}
    slip[crit] = int(round(delay * CRITICAL_SHARE))
    slip[sec] += delay - slip[crit]
    ddu26, rem26 = pen["ddu"][2026], pen["remarks"][2026]
    rows, cum = [], 0
    order = {k: i for i, k in enumerate(STAGE_KEYS)}
    for k, short, full, s0, s1 in STAGES:
        ps, pe = anchor + pd.Timedelta(days=s0), anchor + pd.Timedelta(days=s1)
        fs = ps + pd.Timedelta(days=cum)
        fe = pe + pd.Timedelta(days=cum + slip[k])
        share = slip[k] / delay if delay else 0.0
        rows.append(dict(key=k, stage=short, full=full, plan_start=ps, plan_end=pe, fact_start=fs, fact_end=fe,
                         shift=cum, slip=slip[k], penalty_ddu=ddu26 * share,
                         penalty_rem=rem26 if k == "fix" else 0.0, critical=k == crit, secondary=k == sec and slip[k] > 0))
        cum += slip[k]
    risk = p["problems"][0]["title"] if p.get("problems") else ""
    return dict(key=p["key"], name=p["name"], anchor=anchor, delay=delay, fact_end=anchor + pd.Timedelta(days=delay),
                rows=rows, critical=crit, critical_name=rows[order[crit]]["stage"], secondary=sec,
                secondary_name=rows[order[sec]]["stage"], cause=cause, decision=p["decisions"][0]["title"] if p.get("decisions") else "",
                risk=risk, penalty_ddu=ddu26, penalty_rem=rem26, overdue=len(over), snapshot=d["calc_date"])


def portfolio(D: dict, projects: list[dict], pen_rows: dict) -> list[dict]:
    out = [project_schedule(D[p["key"]], p, pen_rows[p["key"]]) for p in projects]
    return sorted(out, key=lambda s: (-s["delay"], s["name"]))


# ---------------------------------------------------------------- графики
NAVY, SILVER, RISK, GOLD, INK2 = "#0B1F3A", "#B7C0CC", "#B3261E", "#A67C00", "#4A5568"
MS_DAY = 86_400_000


def _ms(days: float) -> float:
    return days * MS_DAY


def _mln(v: float) -> str:
    return f"{v / 1e6:,.1f}".replace(",", "\u00a0").replace(".", ",")


def _moratorium(fig, x0):
    m0, m1 = PN.MORATORIUM
    if x0 <= m1:
        fig.add_vrect(x0=max(x0, m0), x1=m1 + pd.Timedelta(days=1), fillcolor="#E3E7ED", opacity=0.6, line_width=0, layer="below",
                      annotation_text="Мораторий ПП № 326", annotation_position="bottom left",
                      annotation_font=dict(size=10, color=INK2))


def project_figure(s: dict):
    import plotly.graph_objects as go
    rows = list(reversed(s["rows"]))
    y = [r["stage"] for r in rows]
    fig = go.Figure()
    fig.add_bar(y=y, base=[r["plan_start"] for r in rows], x=[_ms((r["plan_end"] - r["plan_start"]).days) for r in rows],
                orientation="h", width=0.22, offset=0.18, marker_color=SILVER, name="План",
                customdata=[[r["full"], f'{r["plan_start"]:%d.%m.%Y}', f'{r["plan_end"]:%d.%m.%Y}'] for r in rows],
                hovertemplate="%{customdata[0]}<br>План: %{customdata[1]} – %{customdata[2]}<extra></extra>")
    on_time = [max(0, (r["fact_end"] - r["fact_start"]).days - r["slip"]) for r in rows]
    fig.add_bar(y=y, base=[r["fact_start"] for r in rows], x=[_ms(d) for d in on_time], orientation="h", width=0.42, offset=-0.3,
                marker_color=NAVY, name="Факт",
                customdata=[[r["full"], f'{r["fact_start"]:%d.%m.%Y}', f'{r["fact_end"]:%d.%m.%Y}', r["shift"]] for r in rows],
                hovertemplate="%{customdata[0]}<br>Факт: %{customdata[1]} – %{customdata[2]}<br>Сдвиг от предыдущих этапов: %{customdata[3]} дн.<extra></extra>")
    fig.add_bar(y=y, base=[r["fact_start"] + pd.Timedelta(days=d) for r, d in zip(rows, on_time)], x=[_ms(r["slip"]) for r in rows],
                orientation="h", width=0.42, offset=-0.3, marker_color=RISK, name="Задержка этапа",
                customdata=[[r["slip"]] for r in rows], hovertemplate="Задержка этапа: %{customdata[0]} дн.<extra></extra>")
    for r in rows:
        if r["slip"] > 0:
            law = []
            if r["penalty_ddu"] > 0:
                law.append(f'{_mln(r["penalty_ddu"])} млн ₽ (ч. 2 ст. 6)')
            if r["penalty_rem"] > 0:
                law.append(f'{_mln(r["penalty_rem"])} млн ₽ (ч. 8 ст. 7)')
            fig.add_annotation(x=r["fact_end"], y=r["stage"], text=f'<b>+{r["slip"]} дн.</b> → {" · ".join(law)}', showarrow=False,
                               xanchor="left", xshift=6, yshift=-5, font=dict(size=11, color=RISK if r["critical"] else INK2))
    x0 = min(r["plan_start"] for r in s["rows"]) - pd.Timedelta(days=20)
    x1 = max(max(r["fact_end"] for r in s["rows"]), s["snapshot"]) + pd.Timedelta(days=75)
    _moratorium(fig, x0)
    fig.add_vline(x=s["anchor"], line=dict(color=GOLD, width=2, dash="dash"))
    fig.add_annotation(x=s["anchor"], y=1.02, yref="paper", text=f'Срок ДДУ {s["anchor"]:%d.%m.%Y}', showarrow=False,
                       font=dict(size=10, color=GOLD), xanchor="right")
    fig.add_vline(x=s["snapshot"], line=dict(color=INK2, width=1, dash="dot"))
    fig.add_annotation(x=s["snapshot"], y=1.02, yref="paper", text="Срез", showarrow=False, font=dict(size=10, color=INK2), xanchor="left")
    fig.update_layout(barmode="overlay", margin=dict(l=8, r=16, t=36, b=8), legend=dict(orientation="h", y=-0.12, x=0),
                      title=dict(text=f'Этапы передачи · задержка {s["delay"]} дн.', font=dict(size=14)))
    fig.update_xaxes(type="date", range=[x0, x1], tickformat="%m.%Y")
    return fig


def portfolio_figure(scheds: list[dict]):
    import plotly.graph_objects as go
    rows = list(reversed(scheds))
    y = [s["name"] for s in rows]
    fig = go.Figure()
    plan = [next(r for r in s["rows"] if r["key"] == "app") for s in rows]
    fig.add_bar(y=y, base=[r["plan_start"] for r in plan], x=[_ms((r["plan_end"] - r["plan_start"]).days) for r in plan],
                orientation="h", width=0.22, offset=0.18, marker_color=SILVER, name="Плановая передача",
                hovertemplate="План передачи до срока ДДУ<extra></extra>")
    fig.add_bar(y=y, base=[s["anchor"] for s in rows], x=[_ms(s["delay"]) for s in rows], orientation="h", width=0.42, offset=-0.3,
                marker_color=RISK, name="Задержка массовой передачи",
                customdata=[[s["delay"], _mln(s["penalty_ddu"]), s["critical_name"]] for s in rows],
                hovertemplate="Задержка %{customdata[0]} дн.<br>Неустойка 2026: %{customdata[1]} млн ₽<br>Критический этап: %{customdata[2]}<extra></extra>")
    for s in rows:
        fig.add_annotation(x=s["fact_end"], y=s["name"], text=f'+{s["delay"]} дн. · {_mln(s["penalty_ddu"] + s["penalty_rem"])} млн ₽ · {s["critical_name"]}',
                           showarrow=False, xanchor="left", xshift=6, yshift=-5, font=dict(size=11, color=INK2))
    x0 = min(r["plan_start"] for r in plan) - pd.Timedelta(days=20)
    x1 = max(max(s["fact_end"] for s in rows), rows[0]["snapshot"]) + pd.Timedelta(days=110)
    for s in rows:
        fig.add_shape(type="line", x0=s["anchor"], x1=s["anchor"], y0=y.index(s["name"]) - 0.4, y1=y.index(s["name"]) + 0.4,
                      line=dict(color=GOLD, width=2))
    fig.add_vline(x=rows[0]["snapshot"], line=dict(color=INK2, width=1, dash="dot"))
    fig.update_layout(barmode="overlay", margin=dict(l=8, r=16, t=30, b=8), legend=dict(orientation="h", y=-0.1, x=0),
                      title=dict(text="Срок ДДУ (золотая отметка) и массовая передача", font=dict(size=14)))
    fig.update_xaxes(type="date", range=[x0, x1], tickformat="%m.%Y")
    return fig
