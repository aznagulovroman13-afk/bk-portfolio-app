"""Снимки отчёта: python tools/shots.py <адрес> <каталог/> <метка>. Вход без пароля."""
import sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE, OUT, tag = sys.argv[1], sys.argv[2], sys.argv[3]
READY = "Сводка по портфелю"
BAD = ("Требует уточнения", "Нет данных", "нет данных", "демо", "ДЕМО", "DEMO", "вымышл", "условн", "модельн", "Power BI", "А101", "ориентир", "war room", "one-stop")
Path(OUT).mkdir(parents=True, exist_ok=True)


def login(page):
    """Открывает отчёт; пароля нет. Возвращает кадр страницы и время до появления первого экрана."""
    started = time.time()
    page.goto(BASE); page.wait_for_load_state("networkidle")
    fr = page.main_frame
    for _ in range(240):
        time.sleep(0.5)
        if READY in fr.locator("body").inner_text():
            break
    assert not fr.locator("input[type=password]").count(), "на странице есть поле пароля"
    return fr, round(time.time() - started, 1)


def optional(step, *args):
    try:
        step(*args)
    except Exception as exc:                  # необязательный шаг: отчёт о пропуске, съёмка продолжается
        print("пропущено:", getattr(step, "__name__", step), str(exc).splitlines()[0][:100])


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/usr/bin/google-chrome")
    p = b.new_page(viewport={"width": 1440, "height": 900})
    f, secs = login(p)
    print("первый экран открыт без пароля, с:", secs)
    time.sleep(3)

    def shot(name, sel=None, off=0):
        if sel:
            f.evaluate("(a)=>{const e=document.querySelector(a[0]); e.scrollIntoView({block:'start'}); window.scrollBy(0,a[1])}", [sel, off]); time.sleep(1.5)
        p.screenshot(path=OUT + name + f"_{tag}_1440.png")

    def open_text(label):
        f.get_by_text(label).first.click(); time.sleep(1)

    p.set_viewport_size({"width": 1440, "height": 1000})
    shot("01_first_screen")
    shot("02_portfolio_table", "#segments", -60)
    optional(open_text, "Расширенные показатели по ЖК: неустойка, темп и сроки"); shot("03_table_expander", "#segments", 200)
    shot("04_reasons", "#reasons", -50)
    shot("05_forecast", "#forecast", -50)
    shot("06_decisions", "#decisions", -50)
    optional(open_text, "Дополнительные решения по ЖК"); shot("06b_decisions_extra", "#decisions", 330)
    shot("07_remarks_portfolio", "#remarks", -50)
    shot("08_money", "#money", -50)
    shot("08b_orders", "#orders", -50)
    sb = f.locator("[data-testid=stSelectbox]").filter(has_text="Перейти к детализации ЖК")
    sb.click(); time.sleep(1); p.keyboard.type("Деснар"); time.sleep(.5); p.keyboard.press("Enter"); time.sleep(5)
    print("верх блока детализации после перехода:", f.evaluate("()=>document.querySelector('#drill').getBoundingClientRect().top"))
    shot("09_jump_desn")
    optional(lambda: (f.evaluate("()=>{const e=[...document.querySelectorAll('.dec-h')].find(x=>x.innerText.includes('Решения по ЖК')); e.scrollIntoView({block:'start'}); window.scrollBy(0,-70)}"), time.sleep(1.5), p.screenshot(path=OUT + f"09b_detail_decisions_desn_{tag}_1440.png")))
    for tab, name in (("Шахматка", "10_chess_desn"), ("Замечания", "11_remarks_desn"), ("Подрядчики", "12_contractors_desn")):
        optional(lambda t=tab, n=name: (f.get_by_role("tab", name=t).click(), time.sleep(3), shot(n, "#drill")))
    text = f.locator("body").inner_text()
    print("запрещённые слова на экране:", [w for w in BAD if w in text])
    m = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    fm, _ = login(m)
    time.sleep(3)
    m.screenshot(path=OUT + f"13_mobile_first_{tag}_390.png")
    fm.evaluate("()=>{const e=document.querySelector('#segments'); e.scrollIntoView({block:'start'}); window.scrollBy(0,-20)}"); time.sleep(1.5)
    m.screenshot(path=OUT + f"14_mobile_table_{tag}_390.png")
    print("ширина прокрутки на мобильном:", fm.evaluate("()=>document.documentElement.scrollWidth"), "из 390")
    b.close()
