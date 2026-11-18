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
    t0 = None
    if f.locator("input[type=password]").count():
        f.locator("input[type=password]").fill(PWD); p.keyboard.press("Enter"); t0 = time.time()
    for _ in range(240):
        time.sleep(0.5)
        if "Главный риск" in f.locator("body").inner_text(): break
    print("first load after login, s:", round(time.time() - (t0 or time.time()), 1))
    time.sleep(3)
    t = f.locator("body").inner_text()
    print("ok:", "Приоритет руководителя" in t, "Требует уточнения" in t, "Нет данных" in t, "демо" in t.lower())
    def shot(name, sel=None, off=0):
        if sel:
            f.evaluate("(a)=>{const e=document.querySelector(a[0]); e.scrollIntoView({block:'start'}); window.scrollBy(0,a[1])}", [sel, off]); time.sleep(1.5)
        p.screenshot(path=OUT + name + f"_{tag}_1440.png")
    p.set_viewport_size({"width": 1440, "height": 1000})
    shot("01_first_screen")
    shot("02_portfolio_table", "#segments", -60)
    f.get_by_text("Все показатели по ЖК: деньги, темп и сроки").click(); time.sleep(1)
    shot("03_table_expander", "#segments", 200)
    shot("04_reasons", "#reasons", -50)
    shot("05_forecast", "#forecast", -50)
    shot("06_decisions", "#decisions", -50)
    shot("07_remarks_portfolio", "#remarks", -50)
    f.get_by_text("Все показатели по замечаниям и квартирам по ЖК").click(); time.sleep(1)
    f.evaluate("()=>{const e=[...document.querySelectorAll('summary')].find(x=>x.innerText.includes('по замечаниям и квартирам')); e.scrollIntoView({block:'start'}); window.scrollBy(0,-70)}"); time.sleep(1.5); p.screenshot(path=OUT + f"08_remarks_full_tables_{tag}_1440.png")
    sb = f.locator("[data-testid=stSelectbox]").filter(has_text="Открыть разбор ЖК")
    sb.click(); time.sleep(1); p.keyboard.type("Десно"); time.sleep(.5); p.keyboard.press("Enter"); time.sleep(5)
    print("drill top after jump:", f.evaluate("()=>document.querySelector('#drill').getBoundingClientRect().top"))
    shot("09_jump_desn")
    f.get_by_role("tab", name="Шахматка").click(); time.sleep(4); shot("10_chess_desn", "#drill")
    f.get_by_role("tab", name="Замечания").click(); time.sleep(3); shot("11_remarks_desn", "#drill")
    f.get_by_role("tab", name="Подрядчики").click(); time.sleep(3); shot("12_contractors_desn", "#drill")
    t = f.locator("body").inner_text()
    print("bad words:", [w for w in ("Требует уточнения", "Нет данных", "демо", "ДЕМО", "модельн", "Power BI", "А101") if w in t])
    # mobile
    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    m.goto(BASE); m.wait_for_load_state("networkidle"); time.sleep(6)
    fm = next((fr for fr in m.frames if fr.locator("input[type=password]").count()), m.main_frame)
    if fm.locator("input[type=password]").count():
        fm.locator("input[type=password]").fill(PWD); m.keyboard.press("Enter")
    for _ in range(240):
        time.sleep(0.5)
        if "Главный риск" in fm.locator("body").inner_text(): break
    time.sleep(3)
    m.screenshot(path=OUT + f"13_mobile_first_{tag}_390.png")
    fm.evaluate("()=>{const e=document.querySelector('#segments'); e.scrollIntoView({block:'start'}); window.scrollBy(0,-20)}"); time.sleep(1.5)
    m.screenshot(path=OUT + f"14_mobile_table_{tag}_390.png")
    print("mobile hscroll:", fm.evaluate("()=>document.documentElement.scrollWidth"), "of 390")
    b.close()
