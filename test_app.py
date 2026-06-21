# -*- coding: utf-8 -*-
import os, sys, time
from playwright.sync_api import sync_playwright
from PIL import Image

BASE = os.path.dirname(__file__)
IMG = os.path.join(BASE, "test_images")
URL = "http://localhost:8000/index.html"
DL_DIR = os.path.join(BASE, "downloads")
os.makedirs(DL_DIR, exist_ok=True)

imgs = [os.path.join(IMG, n) for n in ("sunset.png", "forest.png", "geometry.png")]

results = []
def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS" if cond else "FAIL"), "-", name, extra)

with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context()
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    page = ctx.new_page()

    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))

    page.goto(URL, wait_until="networkidle")
    time.sleep(1)

    # 9) Пустое состояние
    check("Пустое состояние: палитра скрыта", page.locator("#paletteSection").is_hidden())
    check("Пустое состояние: контролы скрыты", page.locator("#controls").is_hidden())
    check("Пустое состояние: блок картинок скрыт", page.locator("#imagesBlock").is_hidden())

    # 2) Загрузка нескольких (через input = клик)
    page.set_input_files("#fileInput", imgs)
    page.wait_for_selector(".thumb", timeout=10000)
    page.wait_for_function("document.querySelectorAll('#palette .swatch').length > 0", timeout=10000)
    time.sleep(0.5)
    thumbs = page.locator(".thumb").count()
    check("Загружено 3 превью", thumbs == 3, f"(найдено {thumbs})")
    check("Счётчик показывает 3", "3" in page.locator("#counter").inner_text())

    # 3) Палитра извлечена (по умолчанию 8)
    sw = page.locator("#palette .swatch").count()
    check("Палитра по умолчанию = 8 плашек", sw == 8, f"(найдено {sw})")
    first_hex = page.locator("#palette .hex").first.inner_text()
    check("У плашки есть hex-код", first_hex.startswith("#") and len(first_hex) == 7, f"({first_hex})")

    # 4) Ползунок -> 5 цветов
    page.eval_on_selector("#countSlider", "el => { el.value = 5; el.dispatchEvent(new Event('input', {bubbles:true})); }")
    page.wait_for_function("document.querySelectorAll('#palette .swatch').length === 5", timeout=5000)
    check("Ползунок: 5 цветов", page.locator("#palette .swatch").count() == 5)
    check("Ползунок: подпись значения = 5", page.locator("#countVal").inner_text() == "5")
    # вернём на 8
    page.eval_on_selector("#countSlider", "el => { el.value = 8; el.dispatchEvent(new Event('input', {bubbles:true})); }")
    page.wait_for_function("document.querySelectorAll('#palette .swatch').length === 8", timeout=5000)

    # 5) Клик по плашке -> тост
    page.locator("#palette .swatch").first.click()
    page.wait_for_selector("#toast.show", timeout=3000)
    check("Клик по плашке: тост виден", page.locator("#toast.show").count() == 1)
    try:
        clip = page.evaluate("navigator.clipboard.readText()")
        check("Клик по плашке: hex в буфере", clip.startswith("#") and len(clip) == 7, f"({clip})")
    except Exception as e:
        check("Клик по плашке: hex в буфере", False, f"(ошибка чтения буфера: {e})")
    time.sleep(1.6)

    # 6) Скопировать все
    page.locator("#copyAllBtn").click()
    page.wait_for_selector("#toast.show", timeout=3000)
    try:
        clip = page.evaluate("navigator.clipboard.readText()")
        ok = clip.count("#") == 8 and "," in clip
        check("Скопировать все: 8 цветов через запятую", ok, f"({clip})")
    except Exception as e:
        check("Скопировать все: буфер", False, str(e))
    time.sleep(1.6)

    # 7) Скачать PNG
    with page.expect_download() as di:
        page.locator("#downloadBtn").click()
    dl = di.value
    path = os.path.join(DL_DIR, "palette.png")
    dl.save_as(path)
    ok_png = os.path.exists(path) and os.path.getsize(path) > 1000
    check("PNG скачан и не пустой", ok_png, f"({os.path.getsize(path)} байт)" if os.path.exists(path) else "(нет файла)")
    if ok_png:
        try:
            im = Image.open(path); im.verify()
            check("PNG валиден (открывается)", True, f"({im.size[0]}x{im.size[1]})")
        except Exception as e:
            check("PNG валиден (открывается)", False, str(e))

    # Drag-and-drop: проверим визуальную реакцию зоны
    page.eval_on_selector("#dropzone", "el => el.dispatchEvent(new DragEvent('dragover', {bubbles:true}))")
    check("Drag-over подсвечивает зону", "drag" in (page.locator("#dropzone").get_attribute("class") or ""))

    # 5b) Удаление картинки -> пересчёт
    page.locator(".thumb .remove").first.click()
    time.sleep(0.6)
    thumbs2 = page.locator(".thumb").count()
    check("После удаления осталось 2 превью", thumbs2 == 2, f"(найдено {thumbs2})")
    check("После удаления палитра ещё есть", page.locator("#palette .swatch").count() > 0)

    # 8) Очистить всё -> пустое состояние
    page.locator("#clearAll").click()
    time.sleep(0.5)
    check("Очистка: палитра снова скрыта", page.locator("#paletteSection").is_hidden())
    check("Очистка: превью пусто", page.locator(".thumb").count() == 0)

    # 1) Ошибки в консоли
    real_errors = [e for e in errors if "favicon" not in e.lower()]
    check("Нет ошибок в консоли", len(real_errors) == 0, str(real_errors[:3]))

    browser.close()

print("\n===== ИТОГ =====")
passed = sum(1 for _, ok, _ in results if ok)
print(f"{passed}/{len(results)} проверок пройдено")
fails = [n for n, ok, _ in results if not ok]
if fails:
    print("Провалено:", fails)
    sys.exit(1)
else:
    print("ВСЁ РАБОТАЕТ")
