"""Рисует иконку: две боксёрские перчатки на тёмно-синем фоне."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "mma_secretary" / "web" / "static"
NAVY = (22, 50, 79, 255)
RED = (192, 18, 42, 255)
BLUE = (21, 87, 192, 255)
CUFF = (244, 247, 251, 255)


def _shade(color: tuple[int, int, int, int], delta: int) -> tuple[int, int, int, int]:
    return tuple(max(0, min(255, c + delta)) for c in color[:3]) + (color[3],)


def _glove(color: tuple[int, int, int, int], size: int = 800) -> Image.Image:
    """Перчатка смотрит вправо-вверх, большой палец слева."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = size
    dark = _shade(color, -38)
    # манжета уже кулака
    d.rounded_rectangle((s * 0.38, s * 0.52, s * 0.70, s * 0.96), radius=s * 0.07, fill=dark)
    d.rounded_rectangle((s * 0.38, s * 0.74, s * 0.70, s * 0.96), radius=s * 0.06, fill=CUFF)
    d.rectangle((s * 0.38, s * 0.74, s * 0.70, s * 0.84), fill=color)
    # кулак
    d.ellipse((s * 0.24, s * 0.06, s * 0.96, s * 0.64), fill=color)
    # большой палец отдельно, чтобы силуэт читался
    d.ellipse((s * 0.02, s * 0.30, s * 0.38, s * 0.62), fill=color)
    return im


def _outline(glove: Image.Image, width: int = 18) -> Image.Image:
    alpha = glove.getchannel("A")
    dilated = alpha.filter(ImageFilter.MaxFilter(width if width % 2 else width + 1))
    plate = Image.new("RGBA", glove.size, (255, 255, 255, 255))
    plate.putalpha(dilated)
    plate.alpha_composite(glove)
    return plate


def _background(size: int) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=NAVY)
    return im


def compose(size: int = 1024) -> Image.Image:
    bg = _background(size)
    glove = int(size * 0.62)
    blue = _outline(_glove(BLUE).resize((glove, glove), Image.Resampling.LANCZOS), 15)
    red = _outline(_glove(RED).resize((glove, glove), Image.Resampling.LANCZOS), 15)
    blue = blue.rotate(18, resample=Image.Resampling.BICUBIC, expand=True)
    red = red.rotate(-18, resample=Image.Resampling.BICUBIC, expand=True)
    bg.alpha_composite(blue, (int(size * -0.04), int(size * 0.20)))
    bg.alpha_composite(red, (int(size * 0.36), int(size * 0.14)))
    return bg


def main() -> None:
    STATIC.mkdir(parents=True, exist_ok=True)
    image = compose()
    png = image.resize((256, 256), Image.Resampling.LANCZOS)
    png.save(STATIC / "icon.png", format="PNG")
    png.save(
        STATIC / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
