"""Снимки отчёта: python tools/shots.py <адрес> <каталог/> <метка>. Пароль берётся из .streamlit/secrets.toml (APP_PASSWORD), в вывод не попадает."""
import sys, time, tomllib
from pathlib import Path
from playwright.sync_api import expect, sync_playwright
BASE, OUT, tag = sys.argv[1], sys.argv[2], sys.argv[3]
PWD = tomllib.loads(Path(__file__).resolve().parents[1].joinpath(".streamlit", "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
READY = "Сводка по портфелю"
Path(OUT).mkdir(parents=True, exist_ok=True)


def app_frame(page, marker, tries=240):
    """Кадр с приложением (на Streamlit Cloud приложение открыто во вложенном кадре), в котором есть метка marker: текст или поле пароля."""
    for _ in range(tries):
        time.sleep(0.5)
        for x in page.frames:
            try:
                if (marker == "password" and x.locator("input[type=password]").count()) or (marker != "password" and marker in x.locator("body").inner_text()):
                    return x
            except Exception:
                continue
    return None


def login(page, name=None):
    """Открывает адрес, снимает экран входа (если name задан), вводит пароль и ждёт первый экран. Возвращает кадр и время входа."""
    page.goto(BASE); page.wait_for_load_state("networkidle")
    gate = app_frame(page, "password", 120)
    assert gate, "экран входа не открылся"
    assert READY not in gate.locator("body").inner_text(), "отчёт открыт без пароля"
    time.sleep(1)
    if name:
        page.screenshot(path=OUT + name)
    started = time.time()
    gate.locator("input[type=password]").fill(PWD); page.keyboard.press("Enter")
    fr = app_frame(page, READY)
    assert fr, "первый экран не открылся после ввода пароля"
    return fr, round(time.time() - started, 1)


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p = b.new_page(viewport={"width": 1440, "height": 900})
    f, secs = login(p, f"00_login_screen_{tag}_1440.png")
    print("отчёт без пароля не открывается; первый экран после ввода пароля, с:", secs)
    time.sleep(3)

    def shot(name):
        p.screenshot(path=OUT + name + f"_{tag}_1440.png")

    def open_section(label, anchor):
        nav = f.get_by_role("navigation", name="Разделы портфеля")
        link = nav.get_by_role("link", name=label, exact=True)
        if not link.is_visible():
            nav.get_by_text("Ещё", exact=True).click()
        link.click()
        f.locator(f"#{anchor}").wait_for(state="visible")

    p.set_viewport_size({"width": 1440, "height": 1000})
    shot("01_first_screen")
    # уровень 1: главная таблица (строки свёрнуты)
    mt = f.locator("#main-portfolio")
    mt.scroll_into_view_if_needed(); mt.screenshot(path=OUT + f"01a_main_table_{tag}_1440.png")
    # уровень 2: клик по ЖК → карточка с диаграммой Ганта
    mt.get_by_role("link", name="Деснаречье", exact=True).click()
    exp = f.locator("[data-testid=stExpander]", has_text="Деснаречье · в просрочке").first
    exp.locator(".js-plotly-plot").first.wait_for(state="visible", timeout=60000); time.sleep(2)
    exp.scroll_into_view_if_needed(); shot("01b_card_desn_gantt")
    p.set_viewport_size({"width": 1440, "height": 2200}); time.sleep(1)
    exp.screenshot(path=OUT + f"01c_card_desn_level2_{tag}_1440.png")
    # уровень 3: причины, передачи, неустойка по годам, основания, решения
    for lab in ("Причины", "Передачи по годам", "Неустойка по годам", "Основания", "Решения"):
        exp.locator("details.mx-l3 > summary", has_text=lab).first.click(); time.sleep(0.4)
    p.set_viewport_size({"width": 1440, "height": 3200}); time.sleep(1)
    exp.screenshot(path=OUT + f"01d_card_desn_level3_{tag}_1440.png")
    p.set_viewport_size({"width": 1440, "height": 1000}); time.sleep(1)
    tot = f.locator("[data-testid=stExpander]", has_text="Итого портфель ·").first
    tot.locator("summary").first.click(); time.sleep(2)
    tot.scroll_into_view_if_needed(); shot("01e_total_gantt")
    for section, anchor, name in (
        ("ЖК", "segments", "02_portfolio_table"),
        ("Причины непередачи", "reasons", "04_reasons"),
        ("Прогноз", "forecast", "05_forecast"),
        ("Решения", "weekly-decisions", "06_decisions"),
        ("Реестр замечаний", "remarks", "07_remarks_portfolio"),
        ("Финансы", "money", "08_money"),
        ("Поручения", "orders", "08b_orders"),
    ):
        open_section(section, anchor)
        shot(name)
    open_section("ЖК", "segments")
    f.locator(".pt3").get_by_role("link", name="Деснаречье", exact=True).click()
    f.locator("#drill").wait_for(state="visible")
    shot("09_project_desn")
    pen = f.locator("details.mx-l2").first
    pen.scroll_into_view_if_needed(); shot("09b_project_desn_penalty_collapsed")
    pen.locator("summary").first.click(); time.sleep(0.5)
    pen.locator("details.mx-l3 > summary").first.click(); time.sleep(0.5)
    pen.scroll_into_view_if_needed(); shot("09c_project_desn_penalty_expanded")
    f.locator("[data-testid=stExpander] summary", has_text="Гант").first.click(); time.sleep(2)
    f.locator(".js-plotly-plot").first.scroll_into_view_if_needed(); time.sleep(1); shot("09d_project_desn_gantt")
    f.locator("details.mx-l3 > summary", has_text="Причины").last.click(); time.sleep(0.5)
    f.locator(".gantt-cause").scroll_into_view_if_needed(); shot("09e_project_desn_gantt_causes")
    menu = f.get_by_role("navigation", name="Разделы ЖК")
    for tab, name in (("Шахматка", "10_chess_desn"), ("Замечания", "11_remarks_desn"), ("Подрядчики", "12_contractors_desn")):
        link = menu.get_by_role("link", name=tab, exact=True)
        link.click()
        expect(link).to_have_attribute("aria-current", "page")
        shot(name)

    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    fm, _ = login(m)
    m.screenshot(path=OUT + f"13_mobile_first_{tag}_390.png")
    fm.locator("#main-portfolio").scroll_into_view_if_needed(); time.sleep(0.5)
    m.screenshot(path=OUT + f"14_mobile_table_{tag}_390.png")
    print("ширина прокрутки на мобильном:", fm.evaluate("()=>document.documentElement.scrollWidth"), "из 390")
    b.close()
