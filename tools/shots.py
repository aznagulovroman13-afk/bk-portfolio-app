import sys, time, tomllib
from pathlib import Path
from playwright.sync_api import sync_playwright
PORT = sys.argv[1] if len(sys.argv) > 1 else "8511"
OUT = sys.argv[2] if len(sys.argv) > 2 else "./screens/"
PWD = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
BASE = f"http://127.0.0.1:{PORT}/"
def ready(p):
    p.wait_for_load_state("networkidle")
    box = p.locator("input[type=password]")
    try:
        box.wait_for(timeout=4000)
        if OUT_LOGIN and not p.__dict__.get("_shot"):
            p.screenshot(path=OUT_LOGIN)
        box.fill(PWD); p.keyboard.press("Enter")
    except Exception:
        pass
    for _ in range(80):
        n = p.evaluate("(()=>{const m=document.querySelector('[data-testid=stMainBlockContainer]');return m?m.innerText.length:0})()")
        if n > 800 and not p.evaluate("/Running\\.\\.\\./.test(document.body.innerText)"): break
        time.sleep(.3)
    time.sleep(3)
OUT_LOGIN = None


def go(p, sel, off=0):
    p.evaluate("(s)=>{const e=document.querySelector(s); if(e) e.scrollIntoView({block:'start'})}", sel)
    if off: p.evaluate(f"window.scrollBy(0,{off})")
    time.sleep(1.5)
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    for w, h in ((1440, 900), (1920, 1080)):
        p = b.new_page(viewport={"width": w, "height": h})
        OUT_LOGIN = OUT + f"0_login_{w}.png"
        p.goto(BASE); ready(p); OUT_LOGIN = None
        print(w, "scrollW", p.evaluate("document.documentElement.scrollWidth"))
        p.screenshot(path=OUT + f"1_first_screen_{w}.png")
        go(p, "#portfolio"); p.screenshot(path=OUT + f"2_table_{w}.png")
        go(p, "#concentration"); p.screenshot(path=OUT + f"3_concentration_{w}.png")
        go(p, "#variance"); p.screenshot(path=OUT + f"4_variance_{w}.png")
        go(p, "#drill"); p.screenshot(path=OUT + f"5_drill_real_{w}.png")
        go(p, "#drill", 650); p.screenshot(path=OUT + f"5b_drill_problems_{w}.png")
        go(p, "#money"); p.screenshot(path=OUT + f"7_money_{w}.png")
        go(p, "#recon"); p.screenshot(path=OUT + f"8_recon_notes_{w}.png")
        p.goto(BASE + "?mode=fact"); ready(p)
        p.screenshot(path=OUT + f"6_fact_only_{w}.png")
        go(p, "#portfolio"); p.screenshot(path=OUT + f"6b_fact_only_table_{w}.png")
        p.goto(BASE + "?jk=%D0%9F%D1%80%D0%BE%D0%BA%D1%88%D0%B8%D0%BD%D0%BE"); ready(p)
        go(p, "#drill"); p.screenshot(path=OUT + f"5c_drill_demo_{w}.png")
        p.close()
    b.close()
