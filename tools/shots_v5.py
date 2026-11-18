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
    p.screenshot(path=OUT + f"01_first_screen_{tag}_1440.png")
    p.evaluate("window.scrollTo(0,0)")
    f.evaluate("()=>{const e=document.querySelector('#priority'); e.scrollIntoView({block:'start'}); window.scrollBy(0,-50)}"); time.sleep(1.5)
    p.screenshot(path=OUT + f"02_priority_table_{tag}_1440.png")
    # jump button
    f.get_by_role("button", name="Открыть разбор: Прокшино").click(); time.sleep(4)
    y = f.evaluate("()=>document.querySelector('#drill').getBoundingClientRect().top")
    print("drill top after jump:", y, "radio:", f.locator("body").inner_text().count("Прокшино"))
    p.screenshot(path=OUT + f"03_jump_proksh_{tag}_1440.png")
    f.get_by_role("button", name="Открыть разбор: Бунинские кварталы").click(); time.sleep(4)
    f.evaluate("()=>{const e=document.querySelector('#drill'); e.scrollIntoView({block:'start'})}"); time.sleep(1)
    p.screenshot(path=OUT + f"04_detail_bunino_overview_{tag}_1440.png")
    f.get_by_role("tab", name="Шахматка").click(); time.sleep(4)
    f.evaluate("()=>{const e=document.querySelector('#drill'); e.scrollIntoView({block:'start'})}"); time.sleep(1)
    p.screenshot(path=OUT + f"05_chess_bunino_{tag}_1440.png")
    f.get_by_role("tab", name="Замечания").click(); time.sleep(4)
    p.screenshot(path=OUT + f"06_remarks_bunino_{tag}_1440.png")
    f.get_by_role("tab", name="Подрядчики").click(); time.sleep(4)
    print("contractors:", "ИНТЕРСТРОЙ" in f.locator("body").inner_text())
    p.screenshot(path=OUT + f"07_contractors_bunino_{tag}_1440.png")
    b.close()
