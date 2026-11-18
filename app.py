"""Портфель ЖК — отчёт для генерального директора (отдельное закрытое приложение).

Запуск: streamlit run app.py   ·   доступ: SHOW_REAL_DATA = "yes" в secrets (иначе — нейтральная заглушка).
"""
import html

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from data_gate import LOCKED_MESSAGE, real_data_allowed

# Шлюз до любой загрузки данных: без секрета — только заглушка.
_ALLOWED = real_data_allowed()
st.set_page_config(page_title="Портфель ЖК" if _ALLOWED else "Приложение",
                   page_icon="🏢" if _ALLOWED else "🔒", layout="wide" if _ALLOWED else "centered",
                   initial_sidebar_state="collapsed")
if not _ALLOWED:
    st.markdown(LOCKED_MESSAGE)
    st.stop()

import pf_auth  # noqa: E402
import pf_ui as U  # noqa: E402

if not pf_auth.authenticated():
    pf_auth.login_screen(U.CSS)
    st.stop()

import pf_core as C  # noqa: E402
import pf_data  # noqa: E402
import pf_decide as DC  # noqa: E402
import pf_model as PF  # noqa: E402

st.markdown(U.CSS, unsafe_allow_html=True)
st.markdown(
    '<div class="pfnav"><b>ПОРТФЕЛЬ ЖК</b><a href="#summary">Сводка</a><a href="#priority">Приоритет</a><a href="#segments">ЖК</a>'
    '<a href="#reasons">Причины</a><a href="#forecast">Прогноз</a><a href="#decisions">Решения</a><a href="#contribution">Вклад в риск</a>'
    '<a href="#dynamics">Динамика</a><a href="#matrix">Матрица</a><a href="#drill">Разбор ЖК</a><a href="#money">Деньги</a>'
    '<a href="#notes">Допущения</a></div>', unsafe_allow_html=True)


@st.cache_data(show_spinner="Загрузка…")
def _load_projects(schema: str = "v6"):   # schema — часть ключа кэша: при смене формата данных старый кэш не подхватывается
    return pf_data.load(True)


try:
    DA = _load_projects()
except pf_data.LockedError:
    st.error("Данные недоступны: проверьте ключ данных в настройках приложения.")
    st.stop()
with st.sidebar:
    if st.button("Выйти", key="pf_exit"):
        st.session_state.clear()
        st.rerun()
    st.markdown("**Допущения расчёта**")
    pr_in = {}
    for k_, nm_ in pf_data.PROJECTS:
        pr_in[k_] = st.number_input(f"Цена квартиры по ДДУ, млн ₽: {nm_}", min_value=1.0, max_value=60.0, value=PF.DEFAULT_PRICES[k_], step=0.1, key=f"pf_price_{k_}")
    st.caption("Цен и площадей по ДДУ в данных нет — цена по каждому ЖК принята допущением, риск пересчитывается пропорционально. "
               "Машиноместа и кладовые — по расчётным ценам, коммерция не считается.")
    with st.expander("Лесенка риска: коэффициенты"):
        k_claim = st.slider("Доля неустойки, по которой предъявляют претензии и иски, %", 5, 100, int(DC.DEFAULT_K["claim"] * 100), 5, key="pf_k_claim")
        k_cut = st.slider("Снижение неустойки судом по ст. 333 ГК, %", 0, 90, int(DC.DEFAULT_K["cut"] * 100), 5, key="pf_k_cut")
        k_paid = st.slider("Доля ожидаемых выплат, уже выплаченная, %", 0, 100, int(DC.DEFAULT_K["paid"] * 100), 5, key="pf_k_paid")
P = dict(price=PF.DEFAULT_PRICES["bunino"] * 1e6, prices={k_: v_ * 1e6 for k_, v_ in pr_in.items()}, price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE)
K = dict(claim=k_claim / 100, cut=k_cut / 100, paid=k_paid / 100)
f, fm = C.fmt_int, C.fmt_money
pl = lambda n: C.plural(n, "квартира", "квартиры", "квартир")
fr = lambda x: C.fmt_pct(x, 1)

import pf_detail as DT  # noqa: E402

st.markdown('<div class="rh"><div class="kick">Отчёт для генерального директора · закрытая версия</div><div class="ttl">Портфель ЖК</div></div>',
            unsafe_allow_html=True)


@st.cache_data(show_spinner="Расчёт…")
def _build(prices: tuple, coefs: tuple, schema: str = "v6"):
    return PF.build(DA, dict(price=prices[0][1], prices=dict(prices), price_mm=C.MM_PRICE, price_nhp=C.NHP_PRICE),
                    dict(zip(("claim", "cut", "paid"), coefs)))


B = _build(tuple(sorted(P["prices"].items())), (K["claim"], K["cut"], K["paid"]))
projects, tot = B["projects"], B["totals"]
names = [p["name"] for p in projects]
sg = lambda v: ("+" if v > 0 else "−" if v < 0 else "") + f(abs(v))
tr_, to_ = max(tot["risk_day"], 1), max(tot["overdue_kv"], 1)
COLORS = {names[0]: U.NAVY, names[1]: U.GOLD, names[2]: U.SILVER}

# ---------------------------------------------------------------- 1. Верхняя сводка
slice_d = max(d_["calc_date"] for d_ in DA.values())
act_d = min(p_["act_date"] for p_ in projects)
dd = lambda t: t.strftime("%d.%m.%Y")
has = [p_ for p_ in projects if p_.get("has_risk", True)]
d_over = tot["overdue_delta"]
n_cov = len(has)
rk_d, rk_t = tot["risk_delta"], tot["risk_target"]
sgm = lambda x: ("+" if x > 0 else "−" if x < 0 else "") + C.fmt_k(x)
RS = f"color:{U.RISK};font-weight:600"
LD = tot["ladder"]
U.section("Сводка по портфелю", "", anchor="summary", num="1.")
U.kpi_cards([
    dict(label="Просрочено по ДДУ", value=f(tot["overdue_kv"]), risk=True, delta=(f"{sg(d_over)} кв. за неделю", "bad" if d_over > 0 else "good" if d_over < 0 else "flat"),
         foot=f"квартир · {fr(tot['overdue_kv'] / max(tot['units_kv'], 1))} от всех квартир ДДУ портфеля"),
    dict(label="Из них готовы к передаче", value=f(tot["ready"]), delta=("", "flat"),
         foot=f"{fr(tot['ready'] / to_)} просрочки · не переданы, готовность подтверждена, открытых замечаний нет"),
    dict(label="Расчётный финансовый риск", value=fm(tot["risk_day"]), risk=True,
         delta=(f"{sgm(rk_d)} за неделю (ориентир {sgm(rk_t)})", "bad" if rk_d > rk_t else "good"),
         foot=f"₽ в сутки · накопленная неустойка до {fm(LD['upper'])} (верхняя граница)"),
], big=True)
st.markdown(f'<div class="slice">Дата среза: <b>{dd(slice_d)}</b> · динамика — за неделю по {dd(act_d)} (последние загруженные акты приёма), сопоставимо по всем ЖК</div>', unsafe_allow_html=True)
st.markdown('<div class="note">Риск считается по действующей методике: ключевая ставка / 300 × 2 × цена квартиры за каждый день просрочки по ДДУ '
            f'(ч. 2 ст. 6 214-ФЗ; цены по ЖК — допущение, см. «Допущения»). Оценка есть по {n_cov} из {len(projects)} ЖК. '
            '«Готовы» — частный случай просрочки: квартира не передана, готовность подтверждена и открытых замечаний нет.</div>', unsafe_allow_html=True)
_mat, _txt = PF.risk_change(tot, projects)
st.markdown(f'<div class="dev"><span class="k">{"Существенное отклонение" if _mat else "Изменение за неделю"}</span> {html.escape(_txt)}</div>', unsafe_allow_html=True)

# расчётный и реальный риск: лесенка
st.markdown('<div class="cmph">Расчётный и реальный риск: от верхней границы к ожидаемым выплатам</div>', unsafe_allow_html=True)
sh = lambda v: fr(v / LD["upper"]) if LD["upper"] else "—"
st.markdown(
    '<div class="ladder">'
    f'<div class="st top"><div class="l">Расчётная неустойка, верхняя граница</div><div class="v">{fm(LD["upper"])}</div><div class="s">накоплено за весь период просрочки; нижняя оценка {fm(LD["lower"])}</div></div>'
    '<div class="ar">›</div>'
    f'<div class="st"><div class="l">Предъявлено претензий и исков</div><div class="v">{fm(LD["claimed"])}</div><div class="s">{sh(LD["claimed"])} верхней границы · допущение: предъявляют {C.fmt_pct(K["claim"])}</div></div>'
    '<div class="ar">›</div>'
    f'<div class="st"><div class="l">Ожидаемые выплаты</div><div class="v">{fm(LD["expected"])}</div><div class="s">{sh(LD["expected"])} верхней границы · суд снижает по ст. 333 ГК на {C.fmt_pct(K["cut"])}</div></div>'
    '<div class="ar">›</div>'
    f'<div class="st"><div class="l">Уже выплачено</div><div class="v">{fm(LD["paid"])}</div><div class="s">{sh(LD["paid"])} верхней границы · {C.fmt_pct(K["paid"])} ожидаемых выплат</div></div></div>',
    unsafe_allow_html=True)
st.markdown('<div class="note">9 с лишним миллиардов — верхняя граница, а не прогноз платежей: мораторий уже исключён из дней просрочки, в данных нет предъявленных требований и выплат, '
            'поэтому три нижние ступени — оценка по коэффициентам (боковая панель).</div>'.replace("9 с лишним миллиардов", fm(LD["upper"])), unsafe_allow_html=True)
with st.expander("Лесенка по ЖК и проблемная часть портфеля"):
    U.fin_table(["ЖК", "Верхняя граница", "Нижняя оценка", "Предъявлено", "Ожидаемые выплаты", "Уже выплачено", "Ожидаемые выплаты, % верхней границы"],
                [[p_["name"], fm(p_["ladder"]["upper"]), fm(p_["ladder"]["lower"]), fm(p_["ladder"]["claimed"]), fm(p_["ladder"]["expected"]), fm(p_["ladder"]["paid"]),
                  fr(p_["ladder"]["expected"] / p_["ladder"]["upper"] if p_["ladder"]["upper"] else 0)] for p_ in projects]
                + [["Итого по портфелю", fm(LD["upper"]), fm(LD["lower"]), fm(LD["claimed"]), fm(LD["expected"]), fm(LD["paid"]), fr(LD["expected"] / LD["upper"] if LD["upper"] else 0)]],
                right=range(1, 7), total_last=True)
    comp = PF.composition(projects)
    mx_ = max(max(c["now"], c["prev"]) for c in comp) * 1.15 or 1
    cb = []
    for c in comp:
        w_ = lambda v: f"{100 * v / mx_:.1f}%"
        cb.append(f'<div class="cmp{" tot" if c["total"] else ""}"><div class="nm">{html.escape(c["name"])}</div>'
                  f'<div class="trk"><div class="rdy" style="width:{w_(c["ready"])}"></div><div class="now" style="width:{w_(c["now"])}"></div>'
                  f'<div class="prv" style="left:{w_(c["prev"])}"></div></div>'
                  f'<div class="vl">{fr(c["now"])} <span>(неделю назад {fr(c["prev"])}; из них готовы {fr(c["ready"])})</span></div></div>')
    st.markdown('<div class="cmph">Проблемная часть портфеля: доля квартир по ДДУ, просроченных сейчас, и её положение неделю назад (метка)</div>' + "".join(cb),
                unsafe_allow_html=True)

# ---------------------------------------------------------------- 2. Приоритет руководителя
pri = PF.priority(projects)
U.section("Приоритет руководителя", "ЖК с наибольшим расчётным риском", anchor="priority", num="2.")
if pri:
    drv = "".join(f"<li>{html.escape(x)}</li>" for x in pri["drivers"])
    decs = "".join(
        f'<div class="dc"><div class="dt">{html.escape(d_["title"])}</div>'
        f'<div class="de">−{fm(d_["effect"])} расчётного риска за 4 недели</div>'
        f'<div class="dr">{html.escape(d_["kind"])} · {html.escape(", ".join(d_["roles"]))}</div></div>' for d_ in pri["decisions"])
    st.markdown(
        f'<div class="prio"><div class="ph"><div class="pn">{html.escape(pri["name"])}</div>'
        f'<div class="pm"><b>{fm(pri["risk_day"])}</b> в сутки <span>· {fr(pri["share"])} общего расчётного риска портфеля</span></div></div>'
        f'<div class="pc"><div class="pl">Подтверждённая причина</div><div class="pt">{html.escape(pri["cause"])}</div><ul>{drv}</ul></div>'
        f'<div class="pc"><div class="pl">Требуемые решения и их эффект</div>{decs}</div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. Таблица по ЖК
U.section("Портфель по ЖК", "По убыванию расчётного риска; ЖК без оценки риска — внизу", anchor="segments", num="3.")
trs = PF.table_rows(projects, RS)
tot_dec = max((d_ for p_ in projects for d_ in p_["decisions"]), key=lambda d_: d_["effect"], default=None)
tot_row = ["Итого по портфелю", f(tot["overdue_kv"]), f(tot["ready"]), (f(round(tot["risk_day"])), RS), f(round(tot["risk_day"] / max(tot["overdue_kv"], 1))), "100,0%",
           f"{sgm(rk_d)} при ориентире {sgm(rk_t)}: {'лучше' if rk_d < rk_t else 'хуже' if rk_d > rk_t else 'по ориентиру'}",
           f"{f(tot['week_fact'])} / {f(tot['week_plan'])} ({sg(tot['week_fact'] - tot['week_plan'])})", ""]
U.fin_table(["ЖК", "Просрочено по ДДУ", "Из них готовы", "Риск, ₽ в сутки", "Риск на просроченную квартиру, ₽ в сутки", "Доля в общем риске",
             "Изменение за неделю к ориентиру", "Передано за неделю: факт / план (откл.)", "Главное решение и эффект"],
            trs + [tot_row], right=range(1, 6), total_last=True, cls="pt3")
st.markdown('<div class="note">Изменение — риск в сутки за неделю по последним актам приёма против ориентира: средняя динамика четырёх предыдущих недель × 1,10. '
            'План передачи за неделю — средний факт четырёх предыдущих полных недель × 1,10. Эффект решения — снижение расчётного риска за 4 недели; подробности — в разделе «Решения».</div>', unsafe_allow_html=True)


def _go(nm):
    st.session_state["pf_sel"] = nm
    st.session_state["_pf_scroll"] = True


bc = st.columns(len(trs))
for i_, r in enumerate(trs):
    bc[i_].button(f"Открыть разбор: {r[0]}", key=f"pf_go_{i_}", on_click=_go, args=(r[0],), width="stretch")

# ---------------------------------------------------------------- 4. Почему готовые не переданы
RSN = tot["reasons"]
U.section("Почему готовые не переданы", f"{f(tot['ready'])} готовых квартир по взаимоисключающим причинам; каждая квартира — в одной причине", anchor="reasons", num="4.")
RCOL = {"booked": "#8FA6C4", "queue": "#5B7BA6", "refused": "#1F3A5F", "called": "#C9B27A", "expired": "#8A7440", "silent": "#14213D"}
fr_ = go.Figure()
cats = [p_["name"] for p_ in projects] + ["Портфель"]
for k_, lab_ in DC.REASONS:
    vals = [p_["reasons"][k_]["n"] for p_ in projects] + [RSN[k_]["n"]]
    fr_.add_bar(y=cats, x=vals, orientation="h", name=lab_, marker_color=RCOL[k_], text=[f(v_) if v_ else "" for v_ in vals], textposition="inside",
                insidetextanchor="middle", textfont=dict(color="#FFFFFF" if k_ not in ("booked", "called") else "#14213D", size=11))
fr_.update_layout(barmode="stack", barnorm="percent", title="Готовые к передаче квартиры по причинам непередачи, доля ЖК (подписи — квартиры)", margin=dict(l=8, r=8, t=34, b=8),
                  legend=dict(orientation="h", y=-0.12, font=dict(size=11)), bargap=.35)
fr_.update_yaxes(autorange="reversed")
fr_.update_xaxes(showticklabels=False)
U.chart(fr_, key="pf_reasons", height=330)
big_r = max(DC.REASONS, key=lambda kv: RSN[kv[0]]["n"])
need = tot["ready"] / DC.MONTH_W
st.markdown(f'<div class="dev"><span class="k">Вывод</span> Главная причина — «{html.escape(big_r[1].lower())}»: {f(RSN[big_r[0]]["n"])} из {f(tot["ready"])} квартир '
            f'(≈{fm(RSN[big_r[0]]["risk"])} риска в сутки). Слоты приёмки: за последнюю полную неделю передано {f(tot["week_fact"])} квартир, максимум за 8 недель — {f(tot["capacity"])} в неделю; '
            f'чтобы передать всех готовых за 4 недели, нужно {f(round(need))} в неделю.</div>', unsafe_allow_html=True)
with st.expander("Причины по ЖК, риск и пропускная способность"):
    rows_r = []
    for k_, lab_ in DC.REASONS:
        rows_r.append([lab_] + [f"{f(p_['reasons'][k_]['n'])} · {fm(p_['reasons'][k_]['risk'])}" for p_ in projects] + [f"{f(RSN[k_]['n'])} · {fm(RSN[k_]['risk'])}"])
    U.fin_table(["Причина (квартир · риск в сутки)"] + [p_["name"] for p_ in projects] + ["Портфель"], rows_r, right=range(1, len(projects) + 2))
    U.fin_table(["Пропускная способность", "Факт за последнюю неделю", "Максимум за 8 недель", "Нужно для передачи за 4 недели", "Не хватает в неделю"],
                [[p_["name"], f(p_["week_fact"]), f(p_["capacity"]), f(round(p_["ready"] / DC.MONTH_W)), f(max(0, round(p_["ready"] / DC.MONTH_W) - p_["capacity"]))] for p_ in projects]
                + [["Портфель", f(tot["week_fact"]), f(tot["capacity"]), f(round(need)), f(max(0, round(need) - tot["capacity"]))]],
                right=range(1, 5), total_last=True)
    st.markdown('<div class="note">Причины определены по статусу и дате записи собственника и по реестру официальных вызовов (почтой). Порядок отнесения: приёмка была, акт не подписан → '
                'запись на ближайшие 7 дней → запись позже 7 дней (очередь на слоты приёмщиков) → официальный вызов не старше 30 дней → срок вызова истёк → нет ни записи, ни вызова. '
                'Границы 7 и 30 дней — допущение. Слоты приёмщиков оценены по фактической передаче.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 5. Прогноз и ориентир
U.section("Прогноз и ориентир", "При текущем чистом темпе (передано минус приток новых просрочек) и по ориентиру; сценарий передачи всех готовых", anchor="forecast", num="5.")
rw = st.radio("Передать все готовые за, недель", [2, 4, 8], index=1, horizontal=True, key="pf_ready_w")
PFC = DC.portfolio_forecast(projects, rw)
wk_ = lambda w: (f"{w:.0f}" if w is not None else f"более {DC.HORIZON_W}")
frows = []
for p_ in projects:
    fc_ = DC.forecast(p_, rw)
    frows.append([p_["name"], f(p_["overdue_kv"]), f"{f(p_['gross_left'])} − {f(p_['inflow'])} = {f(p_['burn_pace'])}", wk_(fc_["base"]["weeks"]), wk_(fc_["target"]["weeks"]),
                  (fm(fc_["base"]["accrued"]), RS), wk_(fc_["scn"]["weeks"]), fm(fc_["saving"])])
frows.append(["Портфель", f(tot["overdue_kv"]), f"{f(tot['gross_left'])} − {f(tot['inflow'])} = {f(tot['burn_pace'])}", wk_(PFC["base"]["weeks"]), wk_(PFC["target"]["weeks"]),
              (fm(PFC["base"]["accrued"]), RS), wk_(PFC["scn"]["weeks"]), fm(PFC["saving"])])
U.fin_table(["ЖК", "Просрочено сейчас", "Темп в неделю: передано − приток = чистый", "Закроется через, нед. (текущий темп)", "по ориентиру, нед.",
             "Риск накопится до закрытия", f"Закроется, если все готовые за {rw} нед.", "Экономия риска"], frows, right=range(1, 8), total_last=True)
cut_ = min(max(len(PFC["base"]["path"]), len(PFC["scn"]["path"]), len(PFC["target"]["path"])), 60)
fg = go.Figure()
for key_, lab_, col_, dash_ in (("base", "Текущий темп", U.RISK, "solid"), ("target", "Ориентир", U.GOLD, "dash"), ("scn", f"Все готовые за {rw} нед.", U.NAVY, "solid")):
    pth = PFC[key_]["path"][:cut_]
    fg.add_scatter(x=[x_[0] for x_ in pth], y=[x_[2] / 1e9 for x_ in pth], mode="lines", name=lab_, line=dict(color=col_, width=2.5, dash=dash_))
fg.update_layout(title="Накопленный расчётный риск портфеля по неделям, млрд ₽", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.18), hovermode="x unified")
fg.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
fg.update_xaxes(title_text="недель от даты среза")
with st.expander("График накопленного риска"):
    U.chart(fg, key="pf_fc_chart", height=320)
st.markdown(f'<div class="note">Если передать всех готовых за {rw} нед., портфель закроется на {wk_(PFC["base"]["weeks"] - PFC["scn"]["weeks"]) if PFC["base"]["weeks"] and PFC["scn"]["weeks"] else "—"} нед. раньше '
            f'и сэкономит ≈{fm(PFC["saving"])} расчётного риска (за первые 4 недели — {fm(PFC["saving_4w"])}). Чистый темп — среднее за 4 последние недели по датам актов приёма; '
            'ориентир — тот же темп × 1,10. Приток новых просрочек уже вычтен из темпа.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 6. Решения для генерального директора
U.section("Решения для генерального директора", "Деньги, люди, полномочия, давление на подрядчика — с эффектом в ₽ расчётного риска за 4 недели", anchor="decisions", num="6.")
alld = sorted([dict(d_, zhk=p_["name"]) for p_ in projects for d_ in p_["decisions"]], key=lambda d_: -d_["effect"])
drow = lambda d_: [d_["zhk"], d_["kind"], d_["title"], ", ".join(d_["roles"]), (f"−{fm(d_['effect'])}", RS), d_["basis"]]
U.fin_table(["ЖК", "Тип", "Решение", "Кого подключить", "Эффект за 4 недели", "Основание"], [drow(d_) for d_ in alld[:6]], right=(4,), cls="pt3")
if len(alld) > 6:
    with st.expander(f"Остальные решения ({len(alld) - 6})"):
        U.fin_table(["ЖК", "Тип", "Решение", "Кого подключить", "Эффект за 4 недели", "Основание"], [drow(d_) for d_ in alld[6:]], right=(4,), cls="pt3")
cl_ = [(p_["name"], p_["contractor_risk"][0]) for p_ in projects if p_["contractor_risk"]]
if cl_:
    with st.expander("Подрядчики: доля расчётного риска и потенциал удержаний"):
        U.fin_table(["ЖК", "Подрядчик", "Квартир с замечаниями", "Доля риска ЖК", "Риск в сутки", "Потенциал удержаний"],
                    [[p_["name"], c_["name"], f(c_["units"]), fr(c_["share"]), fm(c_["risk"]), fm(c_["claim"])] for p_ in projects for c_ in p_["contractor_risk"]],
                    right=range(2, 6))
st.markdown('<div class="note">Эффект — на сколько снизится расчётный риск за ближайшие 4 недели по сравнению с текущим темпом. Допущения: допбригады дают +25% к фактической передаче; '
            f'после официального вызова приходит {C.fmt_pct(DC.CALL_RESPONSE)} собственников; односторонние акты оформляются по {C.fmt_pct(DC.UNILATERAL_SHARE)} истёкших вызовов; '
            f'выездная группа закрывает {C.fmt_pct(DC.REFUSAL_RESOLVED)} приёмок без подписи; удержания снимают {C.fmt_pct(DC.PRESSURE_SHARE)} риска, приходящегося на подрядчика. Исполнители — роли, сроки не задаются.</div>',
            unsafe_allow_html=True)

# ---------------------------------------------------------------- 3. Вклад сегментов в риск
U.section("Вклад сегментов в риск", "Из чего складывается суточный риск портфеля", anchor="contribution", num="7.")
srt = sorted(projects, key=lambda p: -p["risk_day"])
cum, rows_h = 0.0, []
for p in srt:
    cum += p["risk_day"] / tr_
    rows_h.append([p["name"], f(p["overdue_kv"]), fr(p["overdue_kv"] / to_), f(round(p["risk_day"])), fr(p["risk_day"] / tr_), fr(cum), fm(p["accrued_up"])])
rows_h.append(["Итого", f(tot["overdue_kv"]), "100,0%", f(round(tot["risk_day"])), "100,0%", "", fm(tot["accrued_up"])])
c1, c2 = st.columns([1, 1.4], gap="large")
with c1:
    mln = lambda x: x / 1e6
    fig = go.Figure(go.Waterfall(
        x=[p["name"] for p in srt] + ["Портфель"], measure=["relative"] * len(srt) + ["total"], y=[mln(p["risk_day"]) for p in srt] + [0],
        text=[f"{mln(p['risk_day']):.1f}".replace(".", ",") for p in srt] + [f"{mln(tot['risk_day']):.1f}".replace(".", ",")],
        textposition="outside", connector=dict(line=dict(color=U.LINE, width=1)),
        increasing=dict(marker=dict(color=U.NAVY)), totals=dict(marker=dict(color=U.RISK))))
    fig.update_layout(title="Риск в сутки, млн ₽: вклад ЖК в итог", margin=dict(l=8, r=8, t=34, b=8))
    fig.update_yaxes(showticklabels=False, range=[0, mln(tot["risk_day"]) * 1.18])
    fig.update_xaxes(tickfont=dict(size=11))
    U.chart(fig, key="pf_contrib", height=300)
with c2:
    U.fin_table(["Сегмент", "Просрочено, кв.", "Доля", "Риск, ₽/сутки", "Доля риска", "Накопл. доля", "Накоплено"], rows_h, right=range(1, 7), total_last=True)
hhi = sum((p["risk_day"] / tr_) ** 2 for p in projects) * 10000
big = srt[0]
st.markdown(f'<div class="note">Крупнейший сегмент — {fr(big["risk_day"] / tr_)} суточного риска. Индекс концентрации (HHI, 0–10 000): <b>{f(hhi)}</b> — '
            f'{"высокая концентрация" if hhi > 2500 else "умеренная концентрация"}.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 4. Динамика
U.section("Динамика за неделю", "Изменение просрочки и темп передачи к прошлой неделе", anchor="dynamics", num="8.")
v1, v2 = st.columns([1, 1.4], gap="large")
with v1:
    wf = go.Figure(go.Waterfall(
        x=[p["name"] for p in projects] + ["Портфель"], measure=["relative"] * len(projects) + ["total"],
        y=[p["overdue_delta"] for p in projects] + [0], text=[sg(p["overdue_delta"]) for p in projects] + [sg(d_over)],
        textposition="outside", connector=dict(line=dict(color=U.LINE, width=1)),
        increasing=dict(marker=dict(color=U.RISK)), decreasing=dict(marker=dict(color=U.NAVY)), totals=dict(marker=dict(color=U.SILVER))))
    lo_, hi_ = min(0, d_over, *[p["overdue_delta"] for p in projects]), max(0, *[p["overdue_delta"] for p in projects])
    wf.update_layout(title="Δ просрочки по ДДУ за 7 дней, кв.", margin=dict(l=8, r=8, t=34, b=8))
    wf.update_yaxes(showticklabels=False, range=[lo_ * 1.35 - 4, hi_ * 1.35 + 6], zeroline=True, zerolinecolor=U.LINE)
    wf.update_xaxes(tickfont=dict(size=11))
    U.chart(wf, key="pf_wf", height=300)
with v2:
    rv = []
    for p in projects + [dict(name="Итого по портфелю", overdue_kv=tot["overdue_kv"], overdue_delta=d_over, week_fact=tot["week_fact"],
                              week_prev=tot["week_prev"], total=True)]:
        prev_o = p["overdue_kv"] - p["overdue_delta"]
        dwk = (p["week_fact"] - p["week_prev"]) if p["week_prev"] is not None else None
        rv.append([p["name"], f(p["overdue_kv"]), f(prev_o), sg(p["overdue_delta"]),
                   fr(p["overdue_delta"] / prev_o) if prev_o else PF.DASH, f(p["week_fact"]), sg(dwk) if dwk is not None else PF.DASH])
    U.fin_table(["Сегмент", "Просрочено сейчас", "7 дн. назад", "Δ", "Δ, %", "Передано за неделю", "Δ к прошлой неделе"], rv, right=range(1, 7), total_last=True)
lf = go.Figure()
for p in projects:
    w = p["weekly"]
    lf.add_scatter(x=w["Неделя"], y=w["Просрочено на конец недели, кв."], mode="lines+markers", name=p["name"], line=dict(color=COLORS[p["name"]], width=2.5))
lf.update_layout(title="Просрочено по ДДУ на конец недели, квартир", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.18),
                 hovermode="x unified")
lf.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
U.chart(lf, key="pf_line", height=300)
st.markdown('<div class="note">Прошлая неделя восстановлена по датам приёма-передачи.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 6. Матрица рисков
U.section("Матрица рисков", "Квартиры по причинам просрочки в каждом ЖК; интенсивность — доля суточного риска портфеля", anchor="matrix", num="9.")
kinds = [k for k in PF.PROBLEMS if any(g["key"] == k for p in projects for g in p["groups"])]
mx = []
for k in kinds:
    row = [PF.PROBLEMS[k]["title"]]
    tot_n = 0
    for p in projects:
        g = next((g for g in p["groups"] if g["key"] == k), None)
        if g is None:
            row.append("—")
            continue
        a = min(.5, g["risk"] / tr_ * 1.6)
        row.append((f(g["n"]), f"background:rgba(179,38,30,{a:.2f});font-weight:600"))
        tot_n += g["n"]
    row.append(f(tot_n))
    mx.append(row)
U.fin_table(["Причина просрочки"] + names + ["Итого"], mx, right=range(1, len(projects) + 2))
st.markdown('<div class="note">Каждая квартира учтена в одной причине. Чем темнее ячейка, тем больше она в суточном риске портфеля.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 7. Разбор ЖК
U.section("Разбор ЖК", "Одинаковый набор для каждого ЖК: обзор и главные проблемы, шахматка, замечания, подрядчики, деньги, динамика", anchor="drill", num="10.")
if st.session_state.get("pf_sel") not in names:
    st.session_state["pf_sel"] = names[0]
sel = st.radio("ЖК для разбора", names, horizontal=True, key="pf_sel")
if st.session_state.pop("_pf_scroll", False):
    st.html("<script>document.getElementById('drill')?.scrollIntoView({block:'start'});</script>", unsafe_allow_javascript=True)
p = next(x for x in projects if x["name"] == sel)
d = DA[p["key"]]
A_, REM, CT = d["units"], d["remarks"], d["contractors"]
st.markdown(f'<div class="dec-h" style="font-size:20px">{html.escape(p["name"])}</div>', unsafe_allow_html=True)
tabs = st.tabs(["Обзор", "Шахматка", "Замечания", "Подрядчики", "Деньги", "Динамика"])

with tabs[0]:
    U.kpi_cards([
        dict(label="Просрочено по ДДУ, квартир", value=f(p["overdue_kv"]), risk=True, delta=C.fmt_delta(p["overdue_delta"]),
             foot=f"{fr(p['overdue_kv'] / to_)} просрочки портфеля"),
        dict(label="Из них готовы без замечаний", value=f(p["ready"]), delta=("", "flat"),
             foot=f"{fr(p['ready'] / p['overdue_kv']) if p['overdue_kv'] else '—'} просрочки ЖК · риск {fm(p['ready_risk'])}/сутки"),
        dict(label="Расчётный риск, ₽ в сутки", value=fm(p["risk_day"]), risk=True, delta=("", "flat"), foot=f"{fr(p['risk_day'] / tr_)} риска портфеля"),
        dict(label="Передано за неделю, квартир", value=f(p["week_fact"]),
             delta=C.fmt_delta(p["week_fact"] - p["week_prev"], good_when_down=False) if p["week_prev"] is not None else ("", "flat"),
             foot="Δ к прошлой неделе"),
        dict(label="Открытых замечаний", value=f(p["remarks"]), delta=("", "flat"), foot=f"критических {f(p['critical'])}"),
    ])
    st.markdown('<div class="dec-h" style="font-size:17px">Три главные проблемы</div>', unsafe_allow_html=True)
    for i, pr in enumerate(p["problems"], 1):
        roles = "".join(f'<span class="pf-role">{html.escape(r)}</span>' for r in pr["roles"])
        st.markdown(
            f'<div class="dec-h"><span class="no">{i}</span>{html.escape(pr["title"])}</div>'
            f'<div class="dec"><div><div class="k">Масштаб</div><div class="v"><span class="big">{f(pr["n"])} {pl(pr["n"])}</span>'
            f'≈{fm(pr["risk"])} в сутки · {fr(pr["share_risk"])} риска ЖК<br>Корпуса: {html.escape(pr["korpusa"])}</div></div>'
            f'<div><div class="k">Причина по данным</div><div class="v">{html.escape(pr["cause"])}</div></div>'
            f'<div><div class="k">Предлагаемое действие</div><div class="v">{html.escape(pr["action"])}<br><br>'
            f'<span class="k">Подключить</span><br>{roles}</div></div>'
            f'<div><div class="k">Проверим на следующем совещании</div><div class="v">{html.escape(pr["metric"])}<br>'
            f'<b>Сейчас: {f(pr["baseline"])}</b></div></div></div>', unsafe_allow_html=True)
    if len(p["by_korpus"]):
        bk = p["by_korpus"].head(8).iloc[::-1]
        fig = go.Figure(go.Bar(y=bk["k"], x=bk["n"], orientation="h", marker_color=U.NAVY,
                               text=[f"{f(n)} кв. · {fm(r)}/сутки" for n, r in zip(bk["n"], bk["risk"])], textposition="outside", cliponaxis=False,
                               hovertemplate="корпус %{y}: %{x} кв.<extra></extra>"))
        fig.update_layout(title="Корпуса: просрочено квартир и риск в сутки", margin=dict(l=8, r=150, t=34, b=8), bargap=.4)
        fig.update_xaxes(showticklabels=False)
        U.chart(fig, key=f"pf_korp_{p['key']}", height=max(200, 36 * len(bk) + 64))
    st.markdown('<div class="dec-h" style="font-size:17px">Корпуса</div>', unsafe_allow_html=True)
    kt = DT.korpus_table(A_, P["price"])
    st.dataframe(kt, hide_index=True, width="stretch", height=min(44 + 35 * len(kt), 420), key=f"pf_kt_{p['key']}",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in kt.columns if c not in ("Корпус", "Передано, %")}
                 | {"Передано, %": st.column_config.NumberColumn(format="%.1f")})

with tabs[1]:
    ks = DT.korpus_list(A_)
    kt2 = DT.korpus_table(A_, P["price"]).set_index("Корпус")
    dflt = int(kt2["Риск, ₽/сутки"].reset_index(drop=True).idxmax())
    kk = st.selectbox("Корпус", ks, index=dflt, key=f"pf_chess_{p['key']}", format_func=lambda k: f"Корпус {k}")
    row = kt2.loc[kk]
    st.markdown(f'<div class="note">Корпус {html.escape(kk)}: помещений {f(row["Помещений"])}, передано {fr(row["Передано, %"] / 100)}, просрочено по ДДУ {f(row["Просрочено по ДДУ"])}, '
                f'замечаний {f(row["Замечаний"])}. Строки — этажи, колонки — секции.</div>', unsafe_allow_html=True)
    ch, _ = DT.chess_html(A_, kk)
    st.markdown(ch, unsafe_allow_html=True)

with tabs[2]:
    imp = DT.remark_importance(REM)
    U.kpi_cards([
        dict(label="Открытых замечаний", value=f(p["remarks"]), delta=("", "flat"), foot=f"{f(p['remarks'] / max(p['units'], 1))} на помещение"),
        dict(label="Критических", value=f(p["critical"]), risk=True, delta=("", "flat"), foot=fr(p["critical"] / max(p["remarks"], 1)) + " от всех"),
        dict(label="Просрочено по регламенту", value=fr(p["remarks_over"] / max(p["remarks"], 1)), risk=True, delta=("", "flat"), foot=f"{f(p['remarks_over'])} замечаний"),
        dict(label="Блокируют передачу", value=f(p["blocking"]), delta=("", "flat"), foot="замечаний по помещениям без акта"),
        dict(label="Оценка стоимости устранения", value=fm(p["remarks_cost"]), delta=("", "flat"), foot="оценка по средней стоимости замечания"),
    ])
    g = DT.remark_groups(REM)
    r1, r2 = st.columns(2, gap="large")
    with r1:
        fg = go.Figure()
        fg.add_bar(y=g["Группа"][::-1], x=g["Замечаний"][::-1] - g["Просрочено более 45 дн."][::-1], orientation="h", name="В срок", marker_color=U.SILVER)
        fg.add_bar(y=g["Группа"][::-1], x=g["Просрочено более 45 дн."][::-1], orientation="h", name="Просрочено более 45 дн.", marker_color=U.RISK)
        fg.update_layout(barmode="stack", title="Замечания по категориям", margin=dict(l=8, r=8, t=34, b=8), legend=dict(orientation="h", y=-0.2))
        U.chart(fg, key=f"pf_rg_{p['key']}", height=300)
    with r2:
        ag = DT.remark_ages(REM)
        fa = go.Figure(go.Bar(x=ag["Возраст замечания"], y=ag["Замечаний"], marker_color=U.NAVY, text=[f(v) for v in ag["Замечаний"]], textposition="outside"))
        fa.update_layout(title="Возраст открытых замечаний", margin=dict(l=8, r=8, t=34, b=8))
        fa.update_yaxes(showticklabels=False)
        U.chart(fa, key=f"pf_ra_{p['key']}", height=300)
    U.fin_table(["Категория", "Замечаний", "Доля", "Критических", "Просрочено более 45 дн.", "% просрочено", "Блокируют передачу"],
                [[r["Группа"], f(r["Замечаний"]), f"{r['Доля, %']:.1f}%".replace(".", ","), f(r["Критических"]), f(r["Просрочено более 45 дн."]),
                  f"{r['% просрочено']:.1f}%".replace(".", ","), f(r["Блокируют передачу"])] for _, r in g.iterrows()]
                + [["Итого", f(g["Замечаний"].sum()), "100,0%", f(g["Критических"].sum()), f(g["Просрочено более 45 дн."].sum()),
                    C.fmt_pct(g["Просрочено более 45 дн."].sum() / max(g["Замечаний"].sum(), 1), 1), f(g["Блокируют передачу"].sum())]],
                right=range(1, 7), total_last=True)
    st.markdown(f'<div class="note">По важности: критических {f(imp["Критическое"])}, значительных {f(imp["Значительное"])}, стандартных {f(imp["Стандартное"])}.</div>',
                unsafe_allow_html=True)
    rk = DT.remark_korpus(REM)
    fk = go.Figure(go.Bar(y=rk["Корпус"][::-1], x=rk["n"][::-1], orientation="h", marker_color=U.NAVY, text=[f(v) for v in rk["n"][::-1]], textposition="outside", cliponaxis=False))
    fk.update_layout(title="Корпуса с наибольшим числом замечаний", margin=dict(l=8, r=40, t=34, b=8), bargap=.4)
    fk.update_xaxes(showticklabels=False)
    U.chart(fk, key=f"pf_rk_{p['key']}", height=max(220, 30 * len(rk) + 64))

with tabs[3]:
    cls = CT["Класс риска"].value_counts()
    U.kpi_cards([
        dict(label="Подрядчиков с замечаниями", value=f(len(CT)), delta=("", "flat"), foot="по числу открытых замечаний"),
        dict(label="Высокий риск", value=f(cls.get("высокий", 0)), risk=True, delta=("", "flat"), foot="балл риска 60 и выше"),
        dict(label="Средний риск", value=f(cls.get("средний", 0)), delta=("", "flat"), foot="балл риска 30–60"),
        dict(label="Низкий риск", value=f(cls.get("низкий", 0)), delta=("", "flat"), foot="балл риска ниже 30"),
        dict(label="Мало данных", value=f(cls.get("мало данных", 0)), delta=("", "flat"), foot="меньше 50 замечаний"),
    ])
    ct = CT.sort_values("Балл риска", ascending=False).reset_index(drop=True)
    top = ct.head(10).iloc[::-1]
    fc = go.Figure(go.Bar(y=top["Подрядчик"], x=top["Балл риска"], orientation="h",
                          marker_color=[U.RISK if c == "высокий" else U.NAVY if c == "средний" else U.SILVER for c in top["Класс риска"]],
                          text=[f"{v:.1f}".replace(".", ",") for v in top["Балл риска"]], textposition="outside", cliponaxis=False))
    fc.update_layout(title="Балл риска подрядчиков (10 крупнейших по баллу)", margin=dict(l=8, r=40, t=34, b=8), bargap=.4)
    fc.update_xaxes(showticklabels=False, range=[0, 110])
    U.chart(fc, key=f"pf_ctr_{p['key']}", height=340)
    view = pd.DataFrame({
        "Подрядчик": ct["Подрядчик"], "Группа": ct["Группа"], "Замечаний": ct["Замечаний"], "Квартир": ct["Квартир"], "Просрочено": ct["Просрочено"],
        "% просрочено": (100 * ct["% просрочено"]).round(1), "Критических": ct["Критических"], "Блокирует квартир": ct["Блок. квартир"].astype(int),
        "Балл риска": ct["Балл риска"], "Класс риска": ct["Класс риска"], "Стоимость устранения, ₽": ct["Оценка стоимости открытых, ₽"].round().astype(int)})
    st.dataframe(view, hide_index=True, width="stretch", height=min(44 + 35 * len(view), 460), key=f"pf_ctt_{p['key']}",
                 column_config={c: st.column_config.NumberColumn(format="localized") for c in ("Замечаний", "Квартир", "Просрочено", "Критических", "Блокирует квартир", "Стоимость устранения, ₽")}
                 | {"% просрочено": st.column_config.NumberColumn(format="%.1f"), "Балл риска": st.column_config.NumberColumn(format="%.1f")})
    st.markdown('<div class="note">Балл риска (0–100) собран из доли просроченных и критических замечаний, средней просрочки, числа блокируемых квартир и объёма замечаний. '
                'Названия подрядчиков даны без реквизитов.</div>', unsafe_allow_html=True)

with tabs[4]:
    pen = p["penalty"]
    U.kpi_cards([
        dict(label="Расчётный риск, ₽ в сутки", value=fm(p["risk_day"]), risk=True, delta=("", "flat"), foot=f"из них готовые квартиры: {fm(p['ready_risk'])}"),
        dict(label="Накоплено, верхняя оценка", value=fm(p["accrued_up"]), risk=True, delta=("", "flat"), foot=f"нижняя оценка {fm(p['accrued_lo'])}"),
        dict(label="Стоимость устранения замечаний", value=fm(p["remarks_cost"]), delta=("", "flat"), foot=f"{f(p['remarks'])} замечаний"),
        dict(label="Потенциал претензий к подрядчикам", value=fm(p["claim_potential"]), delta=("", "flat"), foot="по просроченным замечаниям, оценка"),
    ])
    bk_ = pen["by_korpus"].head(10)
    U.fin_table(["Корпус", "Квартир с неустойкой", "из них не переданы", "Накоплено, верхняя оценка", "Накоплено, нижняя оценка"],
                [[r["Корпус"], f(r["kv"]), f(r["nt"]), fm(r["up"]), fm(r["lo"])] for _, r in bk_.iterrows()], right=range(1, 5))
    st.markdown('<div class="note">Риск и стоимость устранения замечаний — разные показатели, суммировать их нельзя. Показаны 10 корпусов с наибольшей накопленной суммой.</div>',
                unsafe_allow_html=True)

with tabs[5]:
    w = p["weekly"]
    z1, z2 = st.columns(2, gap="large")
    with z1:
        fw = go.Figure(go.Bar(x=w["Неделя"], y=w["Передано, квартир"], marker_color=U.NAVY, text=w["Передано, квартир"], textposition="outside"))
        fw.update_layout(title="Передано квартир по неделям", margin=dict(l=8, r=8, t=34, b=8))
        fw.update_yaxes(showticklabels=False)
        fw.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        U.chart(fw, key=f"pf_wt_{p['key']}", height=300)
    with z2:
        fo = go.Figure(go.Scatter(x=w["Неделя"], y=w["Просрочено на конец недели, кв."], mode="lines+markers", line=dict(color=U.RISK, width=2.5)))
        fo.update_layout(title="Просрочено по ДДУ на конец недели, квартир", margin=dict(l=8, r=8, t=34, b=8))
        fo.update_yaxes(rangemode="tozero", gridcolor=U.LINE, showgrid=True)
        fo.update_xaxes(tickangle=-45, tickfont=dict(size=10))
        U.chart(fo, key=f"pf_wo_{p['key']}", height=300)
    U.fin_table(["Неделя", "Передано, квартир", "Передано, всего", "Просрочено на конец недели, кв."],
                [[r["Неделя"] + (" (неполная)" if r["partial"] else ""), f(r["Передано, квартир"]), f(r["Передано, всего"]), f(r["Просрочено на конец недели, кв."])]
                 for _, r in w.iterrows()], right=range(1, 4))

# ---------------------------------------------------------------- 8. Деньги по портфелю
U.section("Деньги: риск и стоимость устранения", "Разные показатели — суммировать их нельзя", anchor="money", num="11.")
U.kpi_cards([
    dict(label="Расчётный риск: накоплено (верхняя оценка)", value=fm(tot["accrued_up"]), risk=True, delta=("", "flat"),
         foot=f"нижняя оценка {fm(tot['accrued_lo'])} · в сутки ≈{fm(tot['risk_day'])}"),
    dict(label="Стоимость устранения замечаний", value=fm(tot["remarks_cost"]), delta=("", "flat"), foot=f"{f(tot['remarks'])} замечаний"),
])
U.fin_table(["ЖК", "Риск, ₽/сутки", "Накоплено, верхняя", "Накоплено, нижняя", "Стоимость устранения замечаний", "Потенциал претензий"],
            [[x["name"], f(round(x["risk_day"])), fm(x["accrued_up"]), fm(x["accrued_lo"]), fm(x["remarks_cost"]), fm(x["claim_potential"])]
             for x in projects] + [["Итого", f(round(tot["risk_day"])), fm(tot["accrued_up"]), fm(tot["accrued_lo"]), fm(tot["remarks_cost"]), fm(tot["claim_potential"])]], right=range(1, 6), total_last=True)

# ---------------------------------------------------------------- 9. Поручения
U.section("Контроль поручений", "Что поручено, кого подключить и какой показатель проверим на следующем совещании", anchor="orders", num="12.")
ro = [[str(i), p_["name"], pr["action"], ", ".join(pr["roles"]), pr["metric"], f(pr["baseline"])]
      for i, (p_, pr) in enumerate(((p_, pr) for p_ in projects for pr in p_["problems"]), 1)]
U.fin_table(["№", "ЖК", "Поручение", "Кого подключить", "Показатель на следующем совещании", "Сейчас"], ro, right=(5,))
st.markdown('<div class="note">Исполнители указаны ролями, сроки не задаются: на следующем совещании сравниваем «Сейчас» с новым значением.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- 10. Допущения
U.section("Допущения модели", "", anchor="notes", num="13.")
U.sources(
    "Расчётный риск в сутки = ключевая ставка / 300 × 2 (участник — гражданин, ч. 2 ст. 6 214-ФЗ) × цена квартиры. Цен и площадей по ДДУ в данных нет, цены по ЖК приняты допущением: "
    + ", ".join(f"{nm_} — {pr_in[k_]:.1f} млн ₽".replace(".", ",") for k_, nm_ in pf_data.PROJECTS)
    + " (меняются в боковой панели, риск пересчитывается пропорционально). Коммерческие помещения не считаются; машиноместа и кладовые — отдельно по расчётным ценам. "
    "«Накоплено» — верхняя граница неустойки за весь период просрочки (дни моратория исключены), а не прогноз платежей. "
    f"Лесенка: предъявляется {C.fmt_pct(K['claim'])} верхней границы, суд снижает неустойку по ст. 333 ГК на {C.fmt_pct(K['cut'])}, {C.fmt_pct(K['paid'])} ожидаемых выплат уже выплачено — в данных претензий, исков и выплат нет, коэффициенты задаются в боковой панели. "
    "«Готовы» — просрочены по ДДУ, не переданы, готовность подтверждена (есть дата готовности, нет отмены готовности и мотивированного отказа), открытых замечаний нет; их риск — часть общего. "
    "Причины непередачи готовых — по статусу и дате записи собственника и по реестру официальных вызовов; границы 7 и 30 дней — допущение. "
    "Чистый темп — среднее за 4 последние недели по датам актов приёма (передано из просрочки минус приток новых просрочек); ориентир — тот же показатель предыдущих четырёх недель × 1,10; "
    "план передачи за неделю — средний факт четырёх предыдущих полных недель × 1,10. Прогноз линейный: темп и приток не меняются, ставка не меняется. "
    "Эффект решений — снижение расчётного риска за 4 недели против текущего темпа, по допущениям в разделе «Решения». Доля подрядчика в риске — риск просроченных квартир с открытыми замечаниями, "
    "распределённый пропорционально числу квартир с замечаниями подрядчика. Стоимость устранения и потенциал претензий — оценка по средней стоимости замечания; потенциал — трёхкратная стоимость просроченных замечаний. "
    "Персональные данные в отчёт не входят.")
