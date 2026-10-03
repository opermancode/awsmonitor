"""Generate the AWS Monitor leaf logo (assets/leaf.png + assets/leaf.ico).

Re-run with:  python assets/make_logo.py   (needs pillow, build-time only)
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256
OUT = Path(__file__).resolve().parent


def _bez(p0, p1, p2, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t**2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t**2 * p2[1]
        pts.append((x, y))
    return pts


def make():
    # rounded-square background with vertical green gradient
    r = 56
    grad = Image.new("RGBA", (SIZE, SIZE))
    gd = ImageDraw.Draw(grad)
    for y in range(SIZE):
        t = y / SIZE
        g = (67 - int(24 * t), 160 - int(66 * t), 71 - int(39 * t))
        gd.line([(0, y), (SIZE, y)], fill=g + (255,))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=r, fill=255)
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=r, outline=(200, 230, 201, 90), width=3)

    # leaf body: base (bottom centre) -> tip (top), curved edges
    base, tip = (128, 214), (128, 42)
    left = _bez(base, (34, 150), tip)
    right = _bez(tip, (222, 150), base)
    d.polygon(left + right, fill=(200, 230, 201, 255))

    # leaf vein + side veins
    d.line([(128, 206), (128, 54)], fill=(27, 94, 32, 255), width=7)
    for y in (90, 120, 150, 178):
        spread = int(44 * (1 - abs(y - 134) / 130))
        d.line([(128, y), (128 - spread, y + 16)], fill=(27, 94, 32, 255), width=5)
        d.line([(128, y), (128 + spread, y + 16)], fill=(27, 94, 32, 255), width=5)

    # small stem
    d.line([(128, 214), (128, 232)], fill=(165, 214, 167, 255), width=9)

    img.save(OUT / "leaf.png")
    img.save(OUT / "leaf.ico", sizes=[(16, 16), (24, 24), (32, 32),
                                      (48, 48), (64, 64), (128, 128), (256, 256)])

    # Installer wizard images (BMP on white — Inno Setup requirement)
    thumb = img.resize((140, 140), Image.LANCZOS)
    wiz = Image.new("RGB", (164, 314), "white")
    wiz.paste(thumb, (12, 30), thumb)
    ImageDraw.Draw(wiz).rectangle([0, 300, 164, 314], fill=(27, 94, 32))
    wiz.save(OUT / "wizard.bmp")
    lf = img.resize((44, 44), Image.LANCZOS)
    small = Image.new("RGB", (55, 58), "white")
    small.paste(lf, (5, 7), lf)
    small.save(OUT / "wizard_small.bmp")
    print("wrote leaf.png + leaf.ico + wizard.bmp + wizard_small.bmp")


if __name__ == "__main__":
    make()
