"""Regenerate the bundled sample images in assets/ using Pillow.

The images are deliberately simple, unambiguous shapes so vision-model
descriptions are easy to eyeball for correctness.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
SIZE = 512


def red_circle_blue_square() -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 156, 240, 356), fill="#d62828", outline="#7a1010", width=6)
    draw.rectangle((280, 156, 480, 356), fill="#1d4ed8", outline="#0b2a80", width=6)
    return image


def sunset_mountains() -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(image)
    for y in range(SIZE):
        blend = y / SIZE
        draw.line(
            [(0, y), (SIZE, y)],
            fill=(int(255 - 60 * blend), int(140 + 40 * blend), int(60 + 30 * blend)),
        )
    draw.ellipse((196, 120, 316, 240), fill="#ffd166")
    draw.polygon([(0, 512), (150, 260), (300, 512)], fill="#4a3f6b")
    draw.polygon([(180, 512), (360, 220), (512, 512)], fill="#372f52")
    return image


def green_triangle_yellow_star() -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), "#111827")
    draw = ImageDraw.Draw(image)
    draw.polygon([(128, 400), (256, 128), (384, 400)], fill="#22c55e", outline="#14532d")
    star = [
        (410, 60),
        (424, 104),
        (470, 104),
        (433, 131),
        (447, 175),
        (410, 148),
        (373, 175),
        (387, 131),
        (350, 104),
        (396, 104),
    ]
    draw.polygon(star, fill="#facc15")
    return image


def main() -> None:
    ASSETS_DIR.mkdir(exist_ok=True)
    for name, build in (
        ("red_circle_blue_square", red_circle_blue_square),
        ("sunset_mountains", sunset_mountains),
        ("green_triangle_yellow_star", green_triangle_yellow_star),
    ):
        path = ASSETS_DIR / f"{name}.png"
        build().save(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
