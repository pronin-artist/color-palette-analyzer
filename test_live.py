# -*- coding: utf-8 -*-
import os, time, sys
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(__file__)
IMG = os.path.join(BASE, "test_images")
imgs = [os.path.join(IMG, n) for n in ("sunset.png", "forest.png", "geometry.png")]
URL = sys.argv[1]

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    pg = ctx.new_page()
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(URL, wait_until="networkidle")
    time.sleep(1)
    print("Заголовок страницы:", pg.title())
    pg.set_input_files("#fileInput", imgs)
    pg.wait_for_function("document.querySelectorAll('#palette .swatch').length>0", timeout=15000)
    n = pg.locator("#palette .swatch").count()
    print("Плашек в палитре:", n)
    pg.locator("#palette .swatch").first.click()
    pg.wait_for_selector("#toast.show", timeout=3000)
    print("Тост после клика: OK")
    real = [e for e in errs if "favicon" not in e.lower()]
    print("Ошибок в консоли:", len(real), real[:2])
    ok = pg.title() != "" and n == 8 and len(real) == 0
    b.close()
    print("ЖИВАЯ ССЫЛКА РАБОТАЕТ" if ok else "ПРОБЛЕМА")
    sys.exit(0 if ok else 1)
