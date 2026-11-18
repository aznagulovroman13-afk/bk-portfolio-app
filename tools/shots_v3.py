import sys, time, tomllib, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
PORT, OUT = sys.argv[1], sys.argv[2]
PWD = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
BASE = f"http://127.0.0.1:{PORT}/" if PORT.isdigit() else PORT
NAMES = {"bunino": "Бунинские кварталы", "proksh": "Прокшино", "zen": "Дзен-кварталы"}


def ready(p):
    p.wait_for_load_state("networkidle")
    try:
        b = p.locator("input[type=password]"); b.wait_for(timeout=6000); b.fill(PWD); p.keyboard.press("Enter")
    except Exception:
        pass
    for _ in range(100):
        n = p.evaluate("(()=>{const m=document.querySelector('[data-testid=stMainBlockContainer]');return m?m.innerText.length:0})()")
        if n > 800 and not p.evaluate("/Running\\.\\.\\./.test(document.body.innerText)"):
            break
        time.sleep(.3)
    time.sleep(3)


def go(p, sel, off=0):
    p.evaluate("(s)=>{const e=document.querySelector(s); if(e) e.scrollIntoView({block:'start'})}", sel)
    if off:
        p.evaluate(f"window.scrollBy(0,{off})")
    time.sleep(1.5)


def tab(p, name):
    p.get_by_role("tab", name=name).click()
    time.sleep(2.0)


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p = b.new_page(viewport={"width": 1440, "height": 900})
    p.goto(BASE); ready(p)
    print("scrollW", p.evaluate("document.documentElement.scrollWidth"))
    p.screenshot(path=OUT + "01_first_screen_1440.png")
    for sel, name in (("#segments", "02_segments"), ("#contribution", "03_contribution"), ("#dynamics", "04_dynamics"),
                      ("#outlook", "05_outlook_matrix"), ("#money", "12_money_portfolio"), ("#orders", "13_orders"), ("#notes", "14_notes_model_line")):
        go(p, sel); p.screenshot(path=OUT + f"{name}_1440.png")
    for key, nm in NAMES.items():
        p.goto(BASE + "?jk=" + urllib.parse.quote(nm)); ready(p)
        go(p, "#drill"); p.screenshot(path=OUT + f"06_{key}_overview_1440.png")
        go(p, "#drill", 560); p.screenshot(path=OUT + f"07_{key}_problems_1440.png")
        for tname, tag in (("Шахматка", "08_chess"), ("Замечания", "09_remarks"), ("Подрядчики", "10_contractors"), ("Деньги", "11_money"), ("Динамика", "11b_dynamics")):
            go(p, "#drill"); tab(p, tname); go(p, "#drill", 120); p.screenshot(path=OUT + f"{tag}_{key}_1440.png")
            if tname == "Шахматка":
                p.evaluate("window.scrollBy(0,500)"); time.sleep(1); p.screenshot(path=OUT + f"{tag}_{key}_b_1440.png")
    b.close()
