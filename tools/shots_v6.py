import sys, time, tomllib
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE, OUT, tag = sys.argv[1], sys.argv[2], sys.argv[3]
PWD = tomllib.loads(Path(__file__).resolve().parents[1].joinpath(".streamlit", "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
Path(OUT).mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p = b.new_page(viewport={"width": 1440, "height": 900})
    p.goto(BASE); p.wait_for_load_state("networkidle"); time.sleep(6)
    f = next((fr for fr in p.frames if fr.locator("input[type=password]").count()), p.main_frame)
    if f.locator("input[type=password]").count():
        f.locator("input[type=password]").fill(PWD); p.keyboard.press("Enter")
    for _ in range(120):
        time.sleep(1)
        if "Приоритет руководителя" in f.locator("body").inner_text(): break
    time.sleep(4)
    t = f.locator("body").inner_text()
    print("first screen ok:", "Приоритет руководителя" in t, "Требует уточнения" in t, "Нет данных" in t, "ДЕМО" in t.upper() and "ДЕМО" or "")
    def shot(name, sel=None, off=0, h=None):
        if sel:
            f.evaluate("(a)=>{const e=document.querySelector(a[0]); e.scrollIntoView({block:'start'}); window.scrollBy(0,a[1])}", [sel, off]); time.sleep(1.5)
        p.screenshot(path=OUT + name + f"_{tag}_1440.png")
    p.set_viewport_size({"width": 1440, "height": 1000})
    shot("01_first_screen")
    f.get_by_text("Лесенка по ЖК и проблемная часть портфеля").click(); time.sleep(1)
    shot("02_ladder_expander", "#summary", 330)
    shot("03_priority_table", "#priority", -50)
    shot("04_reasons", "#reasons", -50)
    shot("05_forecast", "#forecast", -50)
    shot("06_decisions", "#decisions", -50)
    f.get_by_role("button", name="Открыть разбор: Прокшино").click(); time.sleep(4)
    print("drill top after jump:", f.evaluate("()=>document.querySelector('#drill').getBoundingClientRect().top"))
    shot("07_jump_proksh")
    f.get_by_role("button", name="Открыть разбор: Бунинские кварталы").click(); time.sleep(4)
    shot("08_detail_bunino_overview", "#drill")
    f.get_by_role("tab", name="Шахматка").click(); time.sleep(4)
    shot("09_chess_bunino", "#drill")
    f.get_by_role("tab", name="Замечания").click(); time.sleep(3)
    shot("10_remarks_bunino", "#drill")
    f.get_by_role("tab", name="Подрядчики").click(); time.sleep(3)
    print("contractors:", "ИНТЕРСТРОЙ" in f.locator("body").inner_text())
    shot("11_contractors_bunino", "#drill")
    t = f.locator("body").inner_text()
    print("bad words:", [w for w in ("Требует уточнения", "Нет данных", "демо", "ДЕМО", "модельн") if w in t])
    b.close()
