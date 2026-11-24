"""«Версия 2» отчёта по заселению: светлый минималистичный интерфейс поверх тех же данных и расчётов.

Только оформление и порядок показа: все цифры приходят из app.py (projects, totals, main_rows) без пересчёта.
Подключается только при view=portfolio2 / ver=2; версии 1 и 3 этот модуль не используют.
"""
from html import escape

UX2_SCHEMA = "l2"

CSS = '''<style>
:root{--navy:#1D1D1F;--ink:#1D1D1F;--ink2:#515154;--ink3:#6E6E73;--line:#E3E3E8;--paper:#fff;--bg:#F5F5F7;--gold:#1D1D1F;--risk:#B42318;
  --sh1:none;--hov:#F5F5F7;--row:#EDEDF0;color-scheme:light}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:#F5F5F7!important;color:#1D1D1F!important}
html,body,.stApp,button,input,textarea,select{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Inter","Segoe UI",Roboto,Helvetica,Arial,sans-serif!important}
.stMainBlockContainer,.block-container{max-width:1280px!important;margin:0 auto!important;padding-top:24px!important}
/* верхняя полоса — светлая, полупрозрачная */
.pfnav{background:rgba(251,251,253,.86)!important;-webkit-backdrop-filter:saturate(180%) blur(20px);backdrop-filter:saturate(180%) blur(20px);
  border-bottom:1px solid #E3E3E8}
.pfnav b{color:#1D1D1F!important}
.pfnav a[data-pf-route]{color:#424245!important}
.pfnav a[data-pf-route]:hover,.pfnav a[aria-current="page"][data-pf-route]{color:#1D1D1F!important}
.pfnav .pf-ver a[aria-current="page"][data-pf-route]{color:#fff!important}
.pfnav a,.pfnav summary{color:#424245!important;border-radius:8px!important}
.pfnav a:hover,.pfnav summary:hover,.pfnav [aria-current="page"],.pfnav .more:has([aria-current="page"])>summary{color:#1D1D1F!important;background:#E8E8ED!important}
.pfnav :focus-visible{outline:2px solid #0066CC!important}
.pfnav .more-links{background:#fff!important;border:1px solid #E3E3E8;box-shadow:0 12px 32px rgba(0,0,0,.12)!important;border-radius:12px!important}
.pf-ver{border:1px solid #D2D2D7!important;border-radius:9px!important;background:#fff}
.pfnav .pf-ver a{color:#424245!important;border-radius:0!important}
.pfnav .pf-ver a[aria-current="page"]{background:#1D1D1F!important;color:#fff!important}
header [data-testid="stExpandSidebarButton"]{color:#424245!important}
/* шапка */
.rh.exec-header{background:transparent!important;border:0!important;box-shadow:none!important;border-radius:0!important;padding:8px 0 4px!important;margin:0 0 8px!important}
.rh.exec-header .ttl{font-size:clamp(28px,3.4vw,44px)!important;font-weight:700;color:#1D1D1F!important;letter-spacing:-.035em;margin:2px 0 0!important}
.rh.exec-header .kick{color:#6E6E73!important;text-transform:none!important;letter-spacing:0!important;font-size:14px!important;font-weight:500}
.rh:not(.exec-header){background:#fff!important;color:#1D1D1F!important;border:1px solid #E3E3E8!important;border-bottom:1px solid #E3E3E8!important;box-shadow:none!important}
.rh:not(.exec-header) .ttl,.rh:not(.exec-header) .meta b{color:#1D1D1F!important}
.rh:not(.exec-header) .kick,.rh:not(.exec-header) .meta{color:#6E6E73!important}
/* общие поверхности остальных разделов */
.kcard,.exec-project,.exec-metric,.card,.concl,.dev,.dec,.cell-panel,.gantt-l1,.tw,.prio,.mt-total{border-radius:16px!important;box-shadow:none!important}
.mt-total{border-left:1px solid #E3E3E8!important}
.fin{border-radius:12px;overflow:hidden;border-color:#E3E3E8!important}
.fin th{background:#FAFAFC!important;color:#6E6E73!important;border-bottom:1px solid #E3E3E8!important;text-transform:none!important;letter-spacing:0!important;font-size:12px!important}
.fin tr.tot td{background:#FAFAFC!important;border-top:1px solid #D2D2D7!important}
.pf-links a{border-radius:980px!important;border-color:#D2D2D7!important;background:#fff!important;color:#1D1D1F!important}
.pf-links a[aria-current="page"]{background:#1D1D1F!important;border-color:#1D1D1F!important;color:#fff!important}
.pf-role{border-radius:980px!important;background:#F5F5F7!important;border-color:#E3E3E8!important;color:#1D1D1F!important}
div[data-testid="stPlotlyChart"],div[data-testid="stDataFrame"]{border-radius:16px!important;border-color:#E3E3E8!important}
[data-testid="stExpander"] details{border-radius:16px!important;background:#fff!important;border:1px solid #E3E3E8!important}
[data-testid="stExpander"] summary{padding-top:14px;padding-bottom:14px}
[data-testid="stExpander"] summary p{font-weight:600;color:#1D1D1F}
/* обзор версии 2 */
.v2-overview{display:grid;gap:16px;margin:0 0 22px;color:#1D1D1F}
.v2-overview *{box-sizing:border-box}
.v2-label{display:block;color:#6E6E73;font-size:13px;font-weight:500;line-height:1.4}
.v2-eyebrow{display:block;color:#B42318;font-size:13px;font-weight:600;letter-spacing:.01em}
.v2-hero,.v2-kpi,.v2-risklist{background:#fff;border:1px solid #E3E3E8;border-radius:20px}
.v2-hero{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:32px;padding:28px 32px}
.v2-hero h2{font-size:clamp(22px,2.2vw,28px)!important;font-weight:700!important;letter-spacing:-.025em;margin:6px 0 2px!important;padding:0!important;color:#1D1D1F!important;line-height:1.2!important}
.v2-number{display:block;font-size:clamp(34px,4.6vw,56px);font-weight:700;letter-spacing:-.045em;line-height:1.05;color:#B42318;font-variant-numeric:tabular-nums;margin:10px 0 6px}
.v2-number small{font-size:.42em;font-weight:600;letter-spacing:-.01em;color:#6E6E73;margin-left:4px}
.v2-hero p{color:#515154;font-size:14px;line-height:1.5;margin:4px 0!important}
.v2-action{border-left:1px solid #E3E3E8;padding-left:32px;display:grid;gap:12px;align-content:start}
.v2-action .v2-what{display:block;font-size:19px;font-weight:650;line-height:1.3;letter-spacing:-.015em;color:#1D1D1F}
.v2-facts{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px}
.v2-fact b{display:block;font-size:15px;font-weight:600;color:#1D1D1F;margin-top:3px;line-height:1.35}
.v2-fact .v2-effect{font-size:24px;font-weight:700;color:#24753B;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.v2-fact span.v2-sub{display:block;font-size:12px;color:#6E6E73;margin-top:2px}
.v2-cta{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:12px}
.v2-overview a{color:#0066CC!important;text-decoration:none!important}
.v2-overview a:hover{text-decoration:underline!important;text-underline-offset:3px}
.v2-overview a:focus-visible{outline:2px solid #0066CC;outline-offset:3px;border-radius:4px}
.v2-cta a{font-size:15px;font-weight:500}
.v2-cta a::after,.v2-go::after{content:" ›"}
.v2-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.v2-kpi{min-width:0;padding:18px 20px}
.v2-kpi strong{display:block;font-size:clamp(26px,2.6vw,36px);font-weight:700;letter-spacing:-.035em;line-height:1.15;font-variant-numeric:tabular-nums;margin:8px 0 2px}
.v2-kpi strong small{font-size:.5em;font-weight:600;color:#6E6E73;margin-left:3px;letter-spacing:0}
.v2-kpi a{color:#1D1D1F!important}
.v2-kpi.v2-critical strong,.v2-kpi.v2-critical strong a{color:#B42318!important}
.v2-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-top:10px}
.v2-title{font-size:22px!important;font-weight:700!important;letter-spacing:-.02em;margin:0!important;padding:0!important;color:#1D1D1F!important}
.v2-path{display:flex;flex-wrap:wrap;gap:4px 6px;font-size:12px;color:#6E6E73;list-style:none;margin:0;padding:0}
.v2-path li+li::before{content:"›";margin-right:6px;color:#AEAEB2}
.v2-path li:first-child{color:#1D1D1F;font-weight:600}
.v2-risklist{padding:4px 24px}
.v2-row{display:grid;grid-template-columns:28px minmax(0,1.3fr) minmax(0,1fr) minmax(120px,.6fr);align-items:center;gap:16px;padding:14px 0;border-bottom:1px solid #EDEDF0}
.v2-row:last-child{border-bottom:0}
.v2-rank{font-size:13px;font-weight:600;color:#AEAEB2;font-variant-numeric:tabular-nums}
.v2-name a{font-weight:600;font-size:16px;color:#1D1D1F!important;overflow-wrap:anywhere}
.v2-detail,.v2-share{font-size:12px;color:#6E6E73;display:block;margin-top:3px}
.v2-detail a.v2-go{color:#0066CC!important;font-size:12px;font-weight:500}
.v2-track{height:6px;background:#EDEDF0;border-radius:6px;overflow:hidden}
.v2-fill{display:block;height:6px;background:#8E8E93;border-radius:6px}
.v2-row.v2-top .v2-fill{background:#B42318}
.v2-amount{font-size:17px;font-weight:650;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.v2-row.v2-top .v2-amount{color:#B42318}
.v2-foot{font-size:12px;color:#6E6E73;line-height:1.5}
@media(max-width:900px){.v2-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}.v2-hero{grid-template-columns:1fr;gap:18px;padding:22px}
  .v2-action{border-left:0;border-top:1px solid #E3E3E8;padding:18px 0 0}}
@media(max-width:640px){.stMainBlockContainer,.block-container{padding-left:14px!important;padding-right:14px!important;padding-top:16px!important}
  .v2-row{grid-template-columns:22px minmax(0,1fr) auto;gap:6px 10px;padding:12px 0}
  .v2-bar{grid-row:2;grid-column:2 / -1}.v2-row .v2-amount{grid-row:1;grid-column:3;font-size:15px}
  .v2-kpi{padding:14px}.v2-kpi strong{font-size:24px}.v2-risklist{padding:2px 14px}.v2-facts{grid-template-columns:1fr}
  .v2-hero{padding:18px;border-radius:18px}.v2-path{display:none}
  .pfnav{background:rgba(251,251,253,.94)!important}}
</style>'''


def _pct(v):
    return f"{v:.1f}".replace(".", ",") + "%"


def render(projects, totals, main_rows, slice_text, link, fmt, mln):
    """Первый экран версии 2: главная проблема → решение → ключевые показатели → ЖК по финансовому риску."""
    ranked = sorted(projects, key=lambda p: (-p['risk_day'], -p['overdue_kv'], p['name']))
    by_key = {r['key']: r for r in main_rows}
    total_risk = totals['risk_day']
    if ranked and ranked[0]['risk_day'] > 0:
        lead = ranked[0]
        row = by_key[lead['key']]
        decision = row['dec']
        share = 100 * lead['risk_day'] / total_risk if total_risk > 0 else 0
        if decision:
            day = (f'<span class="v2-sub">−{fmt(round(decision["effect_day"]))} ₽ в день к концу 4-й недели</span>'
                   if decision.get("effect_day") else '')
            action = (f'<span class="v2-label">Управленческое решение</span><span class="v2-what">{escape(decision["short"])}</span>'
                      f'<div class="v2-facts"><div class="v2-fact"><span class="v2-label">Ответственный</span><b>{escape(decision["role"])}</b></div>'
                      f'<div class="v2-fact"><span class="v2-label">Финансовый эффект за 4 недели</span>'
                      f'<b class="v2-effect">−{mln(decision["effect"])} млн ₽</b>{day}</div></div>'
                      f'<div class="v2-foot">Расчёт модели, до затрат на меру.</div>'
                      f'<div class="v2-cta">' + link('Открыть решение', card=lead['key'], cell='decide') + '</div>')
        else:
            action = '<span class="v2-label">Управленческое решение</span><p>Оценённое решение отсутствует.</p>'
        hero = (f'<div class="v2-hero"><div><span class="v2-eyebrow">Главная проблема портфеля</span>'
                f'<h2>{escape(lead["name"])}: наибольшая неустойка в день</h2>'
                f'<span class="v2-number">{fmt(round(lead["risk_day"]))} ₽<small>в день</small></span>'
                f'<p>{_pct(share)} дневной неустойки портфеля · {fmt(row["overdue"])} кв. с нарушенным сроком передачи</p>'
                f'<div class="v2-cta">' + link('Открыть ЖК', card=lead['key']) + '</div></div>'
                f'<div class="v2-action">{action}</div></div>')
    else:
        hero = '<div class="v2-hero"><div><span class="v2-label">Неустойка в день</span><h2>Положительный дневной риск не выявлен</h2></div></div>'

    def metric(label, value, unit, cell=None, critical=False, detail=''):
        shown = f'{value}<small>{unit}</small>' if unit else value
        value_html = link(value + (" " + unit if unit else ""), content=shown, card='total', cell=cell) if cell else shown
        cls = 'v2-kpi v2-critical' if critical else 'v2-kpi'
        return f'<div class="{cls}"><span class="v2-label">{label}</span><strong>{value_html}</strong><span class="v2-label">{detail}</span></div>'

    kpis = (metric('Нарушен срок передачи, кв.', fmt(totals["overdue_kv"]), '', 'overdue', True, 'по всем ЖК')
            + metric('Неустойка в день, ₽', fmt(round(total_risk)), '', critical=True, detail='оценка за +1 день просрочки')
            + metric('Передано в 2026, кв.', fmt(sum(r["t2026"] for r in main_rows)), '', 't2026', detail='с начала года')
            + metric('Остаток 2026, кв.', fmt(sum(r["left2026"] for r in main_rows)), '', 'left2026', detail='срок по ДДУ в 2026'))
    rows = []
    for i, p in enumerate(ranked, 1):
        share = max(0, min(100, 100 * p['risk_day'] / total_risk)) if total_risk > 0 else 0
        r = by_key.get(p['key'], {})
        chess = link('Корпуса и квартиры', css='v2-go', jk=p['key'], tab='chess')
        rows.append(f'<div class="v2-row{" v2-top" if i == 1 and p["risk_day"] > 0 else ""}"><span class="v2-rank">{i}</span>'
                    f'<div class="v2-name">{link(p["name"], card=p["key"])}'
                    f'<span class="v2-detail">{fmt(p["overdue_kv"])} кв. с нарушенным сроком'
                    + (f' · {fmt(r["remarks"])} замечаний' if "remarks" in r else '') + f' · {chess}</span></div>'
                    f'<div class="v2-bar"><div class="v2-track"><span class="v2-fill" style="width:{share:.3f}%"></span></div>'
                    f'<span class="v2-share">{_pct(share)} неустойки портфеля</span></div>'
                    f'<div class="v2-amount">{fmt(round(p["risk_day"]))} ₽<span class="v2-detail">в день</span></div></div>')
    path = ('<ol class="v2-path" aria-label="Уровни раскрытия"><li>Портфель</li><li>ЖК</li><li>Корпус</li>'
            '<li>Квартира</li><li>Замечание</li></ol>')
    return (f'<section class="v2-overview" id="summary"><div class="v2-foot">Срез {escape(slice_text)} · {len(ranked)} ЖК · '
            'суммы неустойки и эффект мер — расчёт модели, не фактические выплаты.</div>' + hero + '<div class="v2-kpis">' + kpis + '</div>'
            '<div class="v2-head"><h2 class="v2-title">ЖК по финансовому риску</h2>' + path + '</div>'
            '<div class="v2-risklist">' + ''.join(rows) + '</div>'
            '<div class="v2-foot">Ранжирование по неустойке в день. Название ЖК раскрывает карточку ниже; '
            '«Корпуса и квартиры» ведёт к шахматке, квартире и её замечаниям.</div></section>')
