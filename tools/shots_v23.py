"""Снимки v23: python tools/shots_v23.py <адрес> <каталог/>. Пароль — из .streamlit/secrets.toml, в вывод не попадает."""
import sys, time, tomllib
from pathlib import Path
from playwright.sync_api import sync_playwright
PWD = tomllib.loads(Path(__file__).resolve().parents[1].joinpath(".streamlit", "secrets.toml").read_text())["APP_PASSWORD"]
base, out = sys.argv[1].rstrip("/") + "/", sys.argv[2]


def open_(b, q, sel, w=1440, h=900):
    p = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2 if w < 800 else 1)
    p.goto(base + q)
    g = []
    for _ in range(300):
        time.sleep(0.5)
        g = [x for x in p.frames if x.locator("input[type=password]").count()]
        if g: break
    g[0].locator("input[type=password]").fill(PWD); g[0].locator("input[type=password]").press("Enter")
    f = None
    for _ in range(300):
        time.sleep(0.5)
        for x in p.frames:
            try:
                if x.locator(sel).count(): f = x
            except Exception: pass
        if f: break
    assert f, sel
    time.sleep(4)
    return p, f


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p, f = open_(b, "", "#gd-strip")
    f.locator("#gd-strip").scroll_into_view_if_needed(); time.sleep(0.5)
    p.screenshot(path=out + "01_main_strip_column.png")
    f.locator("#main-portfolio").scroll_into_view_if_needed(); time.sleep(0.5)
    p.screenshot(path=out + "01b_main_table.png")
    p.close()
    p, f = open_(b, "?card=bunino&cell=decide", "#decide-bunino")
    f.locator("#decide-bunino").scroll_into_view_if_needed(); time.sleep(0.5)
    f.locator("#decide-bunino details summary").first.click(); time.sleep(0.5)
    p.screenshot(path=out + "02_bunino_card_top.png")
    p.close()
    p, f = open_(b, "?card=total&cell=decide", "#cell-total-decide")
    f.locator("#cell-total-decide").scroll_into_view_if_needed(); time.sleep(0.5)
    p.screenshot(path=out + "03_total_decide.png"); p.close()
    for v, n in (("decisions", "04_decisions"), ("orders", "05_orders")):
        p, f = open_(b, f"?view={v}", "#orders" if v == "orders" else "#priority")
        p.screenshot(path=out + n + ".png")
        p.mouse.wheel(0, 800); time.sleep(1); p.screenshot(path=out + n + "_b.png"); p.close()
    p, f = open_(b, "", "#gd-strip", 390, 844)
    f.locator("#gd-strip").scroll_into_view_if_needed(); time.sleep(0.5)
    p.screenshot(path=out + "06_mobile_strip.png")
    f.locator("#main-portfolio").scroll_into_view_if_needed(); time.sleep(0.5)
    p.screenshot(path=out + "06b_mobile_table.png")
    print("scrollWidth", f.evaluate("()=>document.documentElement.scrollWidth"))
    p.close()
    p, f = open_(b, "?card=bunino&cell=decide", "#decide-bunino", 390, 844)
    f.locator("#decide-bunino").scroll_into_view_if_needed(); time.sleep(0.5)
    p.screenshot(path=out + "07_mobile_card.png"); p.close()
    b.close()
