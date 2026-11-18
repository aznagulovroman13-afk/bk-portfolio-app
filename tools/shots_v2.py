import sys, time, tomllib
from pathlib import Path
from playwright.sync_api import sync_playwright
PORT, OUT = sys.argv[1], sys.argv[2]
PWD = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
BASE = f"http://127.0.0.1:{PORT}/"
def ready(p):
    p.wait_for_load_state("networkidle")
    try:
        b = p.locator("input[type=password]"); b.wait_for(timeout=4000); b.fill(PWD); p.keyboard.press("Enter")
    except Exception: pass
    for _ in range(80):
        n = p.evaluate("(()=>{const m=document.querySelector('[data-testid=stMainBlockContainer]');return m?m.innerText.length:0})()")
        if n > 800 and not p.evaluate("/Running\\.\\.\\./.test(document.body.innerText)"): break
        time.sleep(.3)
    time.sleep(3)
def go(p, sel, off=0):
    p.evaluate("(s)=>{const e=document.querySelector(s); if(e) e.scrollIntoView({block:'start'})}", sel)
    if off: p.evaluate(f"window.scrollBy(0,{off})")
    time.sleep(1.5)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p = b.new_page(viewport={"width": 1440, "height": 900})
    p.goto(BASE); ready(p)
    print("scrollW", p.evaluate("document.documentElement.scrollWidth"))
    p.screenshot(path=OUT + "1_first_screen_1440.png")
    for i, (sel, name) in enumerate((("#segments", "2_segments"), ("#contribution", "3_contribution"), ("#dynamics", "4_dynamics"),
                                      ("#outlook", "5_outlook_matrix"), ("#drill", "6_drill"), ("#money", "8_money_orders"), ("#notes", "9_notes"))):
        go(p, sel); p.screenshot(path=OUT + f"{name}_1440.png")
    go(p, "#drill", 600); p.screenshot(path=OUT + "6b_drill_problems_1440.png")
    p.goto(BASE + "?mode=fact"); ready(p); p.screenshot(path=OUT + "7_fact_only_1440.png")
    go(p, "#segments"); p.screenshot(path=OUT + "7b_fact_only_segments_1440.png")
    p.goto(BASE + "?jk=%D0%9F%D1%80%D0%BE%D0%BA%D1%88%D0%B8%D0%BD%D0%BE"); ready(p); go(p, "#drill"); p.screenshot(path=OUT + "6c_drill_demo_1440.png")
    b.close()
