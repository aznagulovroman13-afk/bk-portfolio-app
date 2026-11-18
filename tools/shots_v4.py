import sys, time, tomllib, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE, OUT = sys.argv[1], sys.argv[2]
PWD = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml").read_text(encoding="utf-8"))["APP_PASSWORD"]
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p = b.new_page(viewport={"width": 1440, "height": 900})
    for key, nm in (("proksh", "Прокшино"), ("zen", "Дзен-кварталы")):
        p.goto(BASE + "?jk=" + urllib.parse.quote(nm)); p.wait_for_load_state("networkidle"); time.sleep(8)
        f = next((fr for fr in p.frames if fr.locator("input[type=password]").count()), p.main_frame)
        if f.locator("input[type=password]").count():
            f.locator("input[type=password]").fill(PWD); p.keyboard.press("Enter")
        for _ in range(120):
            time.sleep(1)
            if "Три главные проблемы" in f.locator("body").inner_text(): break
        time.sleep(3)
        f.evaluate("()=>{const e=document.querySelector('#drill'); if(e) e.scrollIntoView({block:'start'})}")
        f.get_by_role("tab", name="Подрядчики").click(); time.sleep(3)
        f.evaluate("()=>{const e=document.querySelector('#drill'); if(e) e.scrollIntoView({block:'start'}); window.scrollBy(0,120)}"); time.sleep(2)
        t = f.locator("body").inner_text()
        print(key, "ГЛАВ-СТРОЙ" in t, "ИНТЕРСТРОЙ" in t, "Аквилон" in t, "ДЕМО" in t)
        p.screenshot(path=OUT + f"10_contractors_{key}_v4_1440.png")
        f.evaluate("window.scrollBy(0,520)"); time.sleep(1.5)
        p.screenshot(path=OUT + f"10b_contractors_{key}_table_v4_1440.png")
    b.close()
