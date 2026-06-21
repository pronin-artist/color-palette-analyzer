from PIL import Image, ImageDraw
import os

out = os.path.join(os.path.dirname(__file__), "test_images")
os.makedirs(out, exist_ok=True)

def save(name, draw_fn, size=(400, 300)):
    img = Image.new("RGB", size, (0, 0, 0))
    d = ImageDraw.Draw(img)
    draw_fn(d, size)
    img.save(os.path.join(out, name))

# 1) Тёплый закат: блоки разных цветов
def sunset(d, s):
    w, h = s
    colors = [(230, 90, 60), (240, 160, 70), (250, 210, 120), (120, 60, 90)]
    bw = w // len(colors)
    for i, c in enumerate(colors):
        d.rectangle([i*bw, 0, (i+1)*bw, h], fill=c)
save("sunset.png", sunset)

# 2) Холодный лес
def forest(d, s):
    w, h = s
    colors = [(30, 70, 50), (60, 110, 80), (110, 150, 120), (200, 220, 200)]
    bh = h // len(colors)
    for i, c in enumerate(colors):
        d.rectangle([0, i*bh, w, (i+1)*bh], fill=c)
save("forest.png", forest)

# 3) Контрастная геометрия
def geo(d, s):
    w, h = s
    d.rectangle([0, 0, w, h], fill=(20, 20, 40))
    d.ellipse([40, 40, 200, 200], fill=(255, 80, 120))
    d.rectangle([220, 80, 360, 260], fill=(80, 200, 220))
    d.polygon([(180, 280), (260, 120), (340, 280)], fill=(240, 220, 60))
save("geometry.png", geo)

# --- Граничные случаи для полного автотеста ---

# 4) Одноцветная картинка (проверка вырожденной палитры)
def solid(d, s):
    w, h = s
    d.rectangle([0, 0, w, h], fill=(128, 64, 200))
save("solid.png", solid)

# 5) Крошечная картинка 2x2 (проверка устойчивости ColorThief к малому размеру)
def tiny():
    img = Image.new("RGB", (2, 2))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((1, 0), (0, 255, 0))
    img.putpixel((0, 1), (0, 0, 255))
    img.putpixel((1, 1), (255, 255, 0))
    img.save(os.path.join(out, "tiny.png"))
tiny()

# 6) Файл-«не картинка» (проверка фильтрации по MIME-типу)
with open(os.path.join(out, "notimage.txt"), "w", encoding="utf-8") as f:
    f.write("это не изображение, загрузчик должен его отфильтровать")

print("Готово:", sorted(os.listdir(out)))
