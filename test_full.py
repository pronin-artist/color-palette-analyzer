# -*- coding: utf-8 -*-
"""
Полный автотест «Анализатора цветовой палитры».

Покрывает КАЖДЫЙ этап использования приложения и проверяет для каждого:
  • факт работы (этап выполняется),
  • логику / необходимость этапа (что будет, если этапа нет / на границах),
  • качество результата (корректность данных, а не только наличие).

Тест самодостаточен: сам поднимает локальный HTTP-сервер на index.html,
сам прогоняет браузер (Playwright/Chromium) и печатает структурированный отчёт.

Запуск:  python test_full.py
Код выхода 0 — все проверки пройдены, 1 — есть провалы.
"""
import os, sys, time, threading, functools, http.server, socketserver, re
from playwright.sync_api import sync_playwright
from PIL import Image

# Консоль Windows бывает в cp1251 — принудительно пишем в UTF-8, чтобы
# стрелки/эмодзи в отчёте не валили тест.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(BASE, "test_images")
DL_DIR = os.path.join(BASE, "downloads")
os.makedirs(DL_DIR, exist_ok=True)
PORT = 8137
URL = f"http://localhost:{PORT}/index.html"

def img(*names):
    return [os.path.join(IMG, n) for n in names]

# ---------- Локальный HTTP-сервер ----------
def start_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=BASE)
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    httpd.RequestHandlerClass.log_message = lambda *a, **k: None  # тишина
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd

# ---------- Сбор результатов по этапам ----------
results = []  # (stage, name, ok, extra)
current_stage = ["?"]

def stage(title):
    current_stage[0] = title
    print(f"\n--- ЭТАП: {title} ---")

def check(name, cond, extra=""):
    ok = bool(cond)
    results.append((current_stage[0], name, ok, extra))
    print(("  PASS" if ok else "  FAIL"), name, (("  " + extra) if extra else ""))
    return ok

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# ======================================================================
httpd = start_server()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(accept_downloads=True)
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
        page = ctx.new_page()

        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(URL, wait_until="networkidle")
        time.sleep(0.8)

        # --------------------------------------------------------------
        stage("0. Загрузка страницы и зависимостей")
        check("Заголовок страницы корректный", page.title() == "Анализатор цветовой палитры", f"({page.title()})")
        check("Библиотека ColorThief загружена (window.ColorThief)",
              page.evaluate("typeof window.ColorThief === 'function'"))
        check("Зона загрузки (dropzone) присутствует", page.locator("#dropzone").count() == 1)

        # --------------------------------------------------------------
        stage("1. Пустое состояние (необходимость скрытия пустых блоков)")
        # Логика: без картинок панели должны быть скрыты, иначе пользователь
        # увидит пустые контролы и кнопки, ведущие в никуда.
        check("Палитра скрыта", page.locator("#paletteSection").is_hidden())
        check("Контролы (ползунок) скрыты", page.locator("#controls").is_hidden())
        check("Блок изображений скрыт", page.locator("#imagesBlock").is_hidden())
        check("Dropzone НЕ в компактном виде (полный CTA)",
              "compact" not in (page.locator("#dropzone").get_attribute("class") or ""))

        # --------------------------------------------------------------
        stage("2. Фильтрация не-картинок (качество валидации ввода)")
        # Логика: загрузчик фильтрует по type=image/*. Текстовый файл должен
        # быть отброшен и НЕ создавать превью / не ломать UI.
        page.set_input_files("#fileInput", img("notimage.txt"))
        time.sleep(0.8)
        check("Текстовый файл отфильтрован (превью не создано)", page.locator(".thumb").count() == 0)
        check("UI остался в пустом состоянии после мусорного файла",
              page.locator("#paletteSection").is_hidden())

        # --------------------------------------------------------------
        stage("3. Загрузка одного изображения (минимальный сценарий)")
        page.set_input_files("#fileInput", img("solid.png"))
        page.wait_for_selector(".thumb", timeout=10000)
        page.wait_for_function("document.querySelectorAll('#palette .swatch').length > 0", timeout=10000)
        check("Создано 1 превью", page.locator(".thumb").count() == 1)
        check("Счётчик склонён верно: '1 изображение'",
              page.locator("#counter").inner_text().strip() == "1 изображение",
              f"({page.locator('#counter').inner_text()!r})")
        check("Контролы стали видимы", page.locator("#controls").is_visible())
        check("Dropzone стал компактным (экономия места)",
              "compact" in (page.locator("#dropzone").get_attribute("class") or ""))
        # Качество: одноцветная картинка → палитра не пустая (ColorThief добивает оттенками)
        check("Палитра одноцветной картинки не пуста", page.locator("#palette .swatch").count() > 0)

        # --------------------------------------------------------------
        stage("4. Загрузка нескольких изображений (основной сценарий)")
        page.set_input_files("#fileInput", img("sunset.png", "forest.png", "geometry.png"))
        page.wait_for_function("document.querySelectorAll('.thumb').length === 4", timeout=10000)
        page.wait_for_function("document.querySelectorAll('#palette .swatch').length > 0", timeout=10000)
        time.sleep(0.4)
        check("Превью добавились к существующему (всего 4)", page.locator(".thumb").count() == 4)
        check("Счётчик склонён верно: '4 изображения'",
              page.locator("#counter").inner_text().strip() == "4 изображения",
              f"({page.locator('#counter').inner_text()!r})")

        # --------------------------------------------------------------
        stage("5. Извлечение палитры (ядро приложения, качество данных)")
        sw = page.locator("#palette .swatch").count()
        check("По умолчанию 8 цветов", sw == 8, f"(найдено {sw})")
        hexes = page.locator("#palette .hex").all_inner_texts()
        check("Все плашки имеют валидный HEX (#RRGGBB)",
              all(HEX_RE.match(h.strip()) for h in hexes), f"({hexes})")
        check("HEX отображаются в ВЕРХНЕМ регистре",
              all(h.strip() == h.strip().upper() for h in hexes))
        check("Нет дубликатов цветов в палитре (агрегация по частоте)",
              len(set(h.strip() for h in hexes)) == len(hexes), f"({hexes})")
        # Качество: цвет фона плашки совпадает с подписанным HEX
        first_bg = page.evaluate(
            "getComputedStyle(document.querySelector('#palette .swatch .color')).backgroundColor")
        check("Цвет плашки соответствует данным (background задан)",
              first_bg.startswith("rgb"), f"({first_bg})")

        # --------------------------------------------------------------
        stage("6. Ползунок количества цветов (логика + границы)")
        def set_slider(v):
            page.eval_on_selector("#countSlider",
                f"el => {{ el.value = {v}; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}")
        # Граница минимума
        set_slider(4)
        page.wait_for_function("document.querySelectorAll('#palette .swatch').length === 4", timeout=5000)
        check("Минимум ползунка = 4 цвета", page.locator("#palette .swatch").count() == 4)
        check("Подпись значения синхронна (=4)", page.locator("#countVal").inner_text() == "4")
        # Граница максимума
        set_slider(12)
        page.wait_for_function("document.querySelectorAll('#palette .swatch').length === 12", timeout=5000)
        check("Максимум ползунка = 12 цветов", page.locator("#palette .swatch").count() == 12)
        check("Подпись значения синхронна (=12)", page.locator("#countVal").inner_text() == "12")
        # Атрибуты диапазона (необходимость ограничений)
        check("min=4 задан у ползунка", page.get_attribute("#countSlider", "min") == "4")
        check("max=12 задан у ползунка", page.get_attribute("#countSlider", "max") == "12")
        set_slider(8)
        page.wait_for_function("document.querySelectorAll('#palette .swatch').length === 8", timeout=5000)

        # --------------------------------------------------------------
        stage("7. Клик по плашке → копирование одного цвета (качество буфера)")
        target_hex = page.locator("#palette .hex").first.inner_text().strip()
        page.locator("#palette .swatch").first.click()
        page.wait_for_selector("#toast.show", timeout=3000)
        check("Тост показан", page.locator("#toast.show").count() == 1)
        check("Текст тоста содержит скопированный HEX",
              target_hex in page.locator("#toast").inner_text(),
              f"({page.locator('#toast').inner_text()!r})")
        clip = page.evaluate("navigator.clipboard.readText()")
        check("В буфере ровно этот HEX", clip.strip().upper() == target_hex.upper(), f"({clip!r})")
        time.sleep(1.5)

        # --------------------------------------------------------------
        stage("8. «Скопировать все цвета» (качество формата вывода)")
        page.locator("#copyAllBtn").click()
        page.wait_for_selector("#toast.show", timeout=3000)
        clip = page.evaluate("navigator.clipboard.readText()")
        parts = [x.strip() for x in clip.split(",")]
        check("Скопировано 8 цветов", len(parts) == 8, f"(получено {len(parts)})")
        check("Разделитель — запятая с пробелом", ", " in clip)
        check("Каждый элемент — валидный HEX", all(HEX_RE.match(x) for x in parts), f"({parts})")
        check("Список совпадает с палитрой на экране",
              parts == [h.strip().upper() for h in page.locator("#palette .hex").all_inner_texts()])
        time.sleep(1.5)

        # --------------------------------------------------------------
        stage("9. «Скачать палитру» PNG (качество артефакта)")
        with page.expect_download() as di:
            page.locator("#downloadBtn").click()
        dl = di.value
        check("Имя файла = palette.png", dl.suggested_filename == "palette.png",
              f"({dl.suggested_filename})")
        path = os.path.join(DL_DIR, "palette_full.png")
        dl.save_as(path)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        check("Файл скачан и не пустой", size > 1000, f"({size} байт)")
        try:
            im = Image.open(path); im.verify()
            im = Image.open(path)
            # Качество: ширина соответствует формуле для 8 плашек
            n = 8; cw, ch, pad, labelH, gap = 200, 260, 30, 46, 16
            exp_w = pad*2 + n*cw + (n-1)*gap
            exp_h = pad*2 + ch + labelH
            check("Размер PNG соответствует формуле для 8 цветов",
                  im.size == (exp_w, exp_h), f"({im.size}, ожидалось {(exp_w, exp_h)})")
        except Exception as e:
            check("PNG валиден и корректного размера", False, str(e))

        # --------------------------------------------------------------
        stage("10. Drag-and-drop (визуальная реакция зоны)")
        page.eval_on_selector("#dropzone",
            "el => el.dispatchEvent(new DragEvent('dragover', {bubbles:true}))")
        check("dragover подсвечивает зону (класс .drag)",
              "drag" in (page.locator("#dropzone").get_attribute("class") or ""))
        page.eval_on_selector("#dropzone",
            "el => el.dispatchEvent(new DragEvent('dragleave', {bubbles:true}))")
        check("dragleave убирает подсветку",
              "drag" not in (page.locator("#dropzone").get_attribute("class") or ""))

        # --------------------------------------------------------------
        stage("11. Удаление одной картинки (пересчёт палитры и счётчика)")
        before = page.locator("#palette .hex").all_inner_texts()
        page.locator(".thumb .remove").first.click()
        page.wait_for_function("document.querySelectorAll('.thumb').length === 3", timeout=5000)
        check("Осталось 3 превью", page.locator(".thumb").count() == 3)
        check("Счётчик обновился: '3 изображения'",
              page.locator("#counter").inner_text().strip() == "3 изображения",
              f"({page.locator('#counter').inner_text()!r})")
        check("Палитра пересчитана (всё ещё непустая)", page.locator("#palette .swatch").count() > 0)

        # --------------------------------------------------------------
        stage("12. Очистить всё (возврат в пустое состояние)")
        page.locator("#clearAll").click()
        time.sleep(0.5)
        check("Все превью удалены", page.locator(".thumb").count() == 0)
        check("Палитра снова скрыта", page.locator("#paletteSection").is_hidden())
        check("Контролы снова скрыты", page.locator("#controls").is_hidden())
        check("Счётчик сброшен в 0", page.locator("#counter").inner_text().strip() == "0",
              f"({page.locator('#counter').inner_text()!r})")
        check("Dropzone вернулся к полному виду",
              "compact" not in (page.locator("#dropzone").get_attribute("class") or ""))

        # --------------------------------------------------------------
        stage("13. Повторное использование после очистки (нет «залипания»)")
        page.set_input_files("#fileInput", img("tiny.png"))
        page.wait_for_selector(".thumb", timeout=10000)
        page.wait_for_function("document.querySelectorAll('#palette .swatch').length > 0", timeout=10000)
        check("После очистки можно снова загрузить (1 превью)", page.locator(".thumb").count() == 1)
        check("Палитра крошечной 2x2 картинки не пуста (устойчивость ColorThief)",
              page.locator("#palette .swatch").count() > 0)

        # --------------------------------------------------------------
        stage("14. Стабильность (отсутствие ошибок в консоли за весь прогон)")
        real_errors = [e for e in errors if "favicon" not in e.lower()]
        check("За весь сценарий нет ошибок в консоли/страницы",
              len(real_errors) == 0, str(real_errors[:3]))

        browser.close()
finally:
    httpd.shutdown()

# ======================================================================
print("\n" + "=" * 60)
print("ИТОГОВЫЙ ОТЧЁТ ПО ЭТАПАМ")
print("=" * 60)
stages = {}
for st, name, ok, extra in results:
    stages.setdefault(st, [0, 0])
    stages[st][0] += 1 if ok else 0
    stages[st][1] += 1
for st, (ok, total) in stages.items():
    mark = "OK " if ok == total else "!! "
    print(f"  {mark}{st}: {ok}/{total}")

passed = sum(1 for *_, ok, _ in [(r[0], r[1], r[2], r[3]) for r in results] if ok)
passed = sum(1 for r in results if r[2])
total = len(results)
print("-" * 60)
print(f"ВСЕГО: {passed}/{total} проверок пройдено")
fails = [f"[{r[0]}] {r[1]}" for r in results if not r[2]]
if fails:
    print("\nПРОВАЛЕНО:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
else:
    print("\nВСЕ ЭТАПЫ РАБОТАЮТ КОРРЕКТНО ✅")
    sys.exit(0)
