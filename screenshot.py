# -*- coding: utf-8 -*-
import os, time
from playwright.sync_api import sync_playwright

BASE = os.path.dirname(__file__)
IMG = os.path.join(BASE, "test_images")
imgs = [os.path.join(IMG, n) for n in ("sunset.png", "forest.png", "geometry.png")]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1100, "height": 1000})
    pg.goto("http://localhost:8000/index.html", wait_until="networkidle")
    pg.screenshot(path=os.path.join(BASE, "shot_empty.png"))
    pg.set_input_files("#fileInput", imgs)
    pg.wait_for_function("document.querySelectorAll('#palette .swatch').length>0", timeout=10000)
    time.sleep(1)
    pg.screenshot(path=os.path.join(BASE, "shot_full.png"), full_page=True)
    b.close()
print("screenshots done")
