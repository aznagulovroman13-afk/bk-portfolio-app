"""Ссылки отчёта и переходы внутри одной сессии Streamlit."""
from __future__ import annotations

import html
from urllib.parse import urlencode

import streamlit as st

REPORT_VIEWS = {
    "summary": "Сводка",
    "segments": "Жилые комплексы",
    "reasons": "Причины непередачи",
    "money": "Финансы",
    "dynamics": "Динамика",
    "decisions": "Решения",
    "orders": "Поручения",
    "forecast": "Прогноз",
    "contribution": "Концентрация неустойки",
    "matrix": "Просрочка по причинам",
    "remarks": "Реестр замечаний",
    "notes": "Методология",
}
PROJECT_VIEWS = {
    "overview": "Обзор",
    "chess": "Шахматка",
    "remarks": "Замечания",
    "contractors": "Подрядчики",
    "money": "Финансы",
    "dynamics": "Динамика",
}
ROUTE_FIELDS = ("view", "jk", "tab", "corpus", "unit")


def link(label, *, content=None, css="", current=False, **route):
    query = urlencode(route)
    href = f"/?{query}" if query else "/"
    if "jk" in route:
        href += "#drill"
    attrs = f' class="{css}"' if css else ""
    if content is not None:
        attrs += f' aria-label="{html.escape(label)}"'
    if current:
        attrs += ' aria-current="page"'
    return f'<a href="{html.escape(href)}" data-pf-route{attrs}>{html.escape(label) if content is None else content}</a>'


def report_link(view, label=None, **options):
    return link(label or REPORT_VIEWS[view], **options, **({"view": view} if view != "summary" else {}))


def set_route(**route):
    params = {key: st.query_params.get_all(key) for key in st.query_params if key not in ROUTE_FIELDS}
    st.query_params.from_dict(params | route)


_clicks = st.components.v2.component(
    "portfolio_route",
    js="""
export default function ({data, setTriggerValue}) {
    const onClick = event => {
        const link = event.target.closest('a[data-pf-route]');
        if (!link || event.defaultPrevented || event.button !== 0 ||
            event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        link.closest('details')?.removeAttribute('open');
        setTriggerValue('route', Object.fromEntries(new URL(link.href).searchParams));
    };
    document.addEventListener('click', onClick);
    document.documentElement.dataset.pfRouteReady = 'true';
    if (data !== window.portfolioView) {
        if (window.parent !== window) {
            try {
                const address = new URL(window.parent.location.href);
                const route = new URLSearchParams(data);
                for (const key of ['view', 'jk', 'tab', 'corpus', 'unit']) {
                    if (route.has(key)) address.searchParams.set(key, route.get(key));
                    else address.searchParams.delete(key);
                }
                address.hash = route.has('jk') ? 'drill' : '';
                window.parent.history.replaceState(window.parent.history.state, '', address);
            } catch {
                // The embedding page owns its address when it is on another origin.
            }
        }
        window.portfolioView = data;
        requestAnimationFrame(() => {
            document.querySelector('[data-testid="stMain"]')?.scrollTo(0, 0);
            window.scrollTo(0, 0);
        });
    }
    return () => {
        document.removeEventListener('click', onClick);
        delete document.documentElement.dataset.pfRouteReady;
    };
}
""",
)


def read_route():
    current = {key: st.query_params[key] for key in ROUTE_FIELDS if key in st.query_params}
    result = _clicks(key="pf_routes", data=urlencode(current), on_route_change=lambda: None)
    if result.route is None:
        return current
    route = {key: result.route[key] for key in ROUTE_FIELDS if isinstance(result.route.get(key), str)}
    if route != current:
        set_route(**route)
        st.rerun()
    return route


def menu(view):
    primary = ("summary", "segments", "money", "decisions", "orders")
    top_links = "".join(report_link(key, "ЖК" if key == "segments" else None, current=view == key) for key in primary)
    more = "".join(report_link(key, current=view == key) for key in REPORT_VIEWS if key not in primary)
    return (
        '<nav class="pfnav" aria-label="Разделы портфеля"><b>ПОРТФЕЛЬ ЖК</b>'
        f'{top_links}<details class="more"><summary>Ещё</summary>'
        f'<div class="more-links">{more}</div></details></nav>'
    )


def project_path(name, key, tab, corpus=None, unit=None):
    steps = [report_link("summary", "Портфель"), report_link("segments", "Все ЖК")]
    if tab == "overview":
        steps.append(f'<span aria-current="page">{html.escape(name)}</span>')
    else:
        steps.append(link(name, jk=key))
        if unit is None:
            label = f"Корпус {corpus}" if corpus is not None else PROJECT_VIEWS[tab]
            steps.append(f'<span aria-current="page">{html.escape(label)}</span>')
        else:
            steps.append(link(f"Корпус {corpus}", jk=key, tab="chess", corpus=corpus))
            steps.append(f'<span aria-current="page">{html.escape(unit)}</span>')
    return '<nav class="pf-path" aria-label="Путь к текущему экрану">' + "".join(steps) + '</nav>'


def project_menu(key, tab):
    return '<nav class="pf-links" aria-label="Разделы ЖК">' + "".join(
        link(label, jk=key, **({"tab": name} if name != "overview" else {}), current=name == tab)
        for name, label in PROJECT_VIEWS.items()
    ) + '</nav>'
