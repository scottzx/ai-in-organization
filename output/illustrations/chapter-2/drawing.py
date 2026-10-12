"""Shared drawing and compact export for chapter two's editable diagrams."""

from pathlib import Path
from html import escape
from collections import Counter
from functools import lru_cache
import json
import math

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps


OUT = Path(__file__).resolve().parent
W, H, SCALE = 1800, 1280, 2
OUTER_MARGIN = 16
INK = "#17365D"
TEAL = "#1D4ED8"
MUTED = "#53657F"
LINE = "#B8C9E6"
PALE = "#EAF1FF"
MID = "#C8D8FF"
LIGHT = "#F3F6FC"
WHITE = "#FFFFFF"
BODY_FONT = "/System/Library/Fonts/STHeiti Light.ttc"
HEADING_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_INDEX = 1  # Heiti SC; collection index 0 is Heiti TC.
FONT_FAMILY = "Heiti SC"
TEXT_STYLES = {
    "title": {"size_px": 58, "weight": 500},
    "subtitle": {"size_px": 30, "weight": 300},
    "heading": {"size_px": 36, "weight": 500},
    "subheading": {"size_px": 32, "weight": 500},
    "narrow_heading": {"size_px": 28, "weight": 500},
    "body": {"size_px": 28, "weight": 300},
    "dense_body": {"size_px": 26, "weight": 300},
    "label": {"size_px": 24, "weight": 300},
    "step": {"size_px": 40, "weight": 500},
    "display": {"size_px": 48, "weight": 500},
}
TYPOGRAPHY = {
    "font_family": FONT_FAMILY,
    "font_index": FONT_INDEX,
    "fonts": {"body": BODY_FONT, "heading": HEADING_FONT},
    "styles": TEXT_STYLES,
}


@lru_cache(maxsize=None)
def text_font(style, scale=SCALE):
    spec = TEXT_STYLES[style]
    path = HEADING_FONT if spec["weight"] == 500 else BODY_FONT
    return ImageFont.truetype(path, spec["size_px"] * scale, index=FONT_INDEX)


class Figure:
    def __init__(self, slug, title, description):
        self.slug, self.title, self.description = slug, title, description
        self.im = Image.new("RGB", (W * SCALE, H * SCALE), WHITE)
        self.draw = ImageDraw.Draw(self.im)
        self.parts = []
        self.texts = []
        self.text_style_counts = Counter()

    def rect(self, x, y, w, h, fill, stroke=None, radius=0, width=2):
        attrs = f'x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}"'
        if stroke:
            attrs += f' stroke="{stroke}" stroke-width="{width}"'
        self.parts.append(f'<rect {attrs}/>')
        box = tuple(v * SCALE for v in (x, y, x + w, y + h))
        self.draw.rounded_rectangle(box, radius=radius * SCALE, fill=fill, outline=stroke, width=width * SCALE)

    def polygon(self, points, fill):
        encoded = " ".join(f"{x},{y}" for x, y in points)
        self.parts.append(f'<polygon points="{encoded}" fill="{fill}"/>')
        self.draw.polygon([(x * SCALE, y * SCALE) for x, y in points], fill=fill)

    def line(self, points, color=LINE, width=2, dash=False):
        encoded = " ".join(f"{x},{y}" for x, y in points)
        dash_attr = ' stroke-dasharray="8 8"' if dash else ""
        self.parts.append(f'<polyline points="{encoded}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{dash_attr}/>')
        for (x1, y1), (x2, y2) in zip(points, points[1:]):
            if dash:
                length = math.hypot(x2 - x1, y2 - y1)
                for start in range(0, math.ceil(length), 16):
                    t1, t2 = start / length, min(start + 8, length) / length
                    self.draw.line(((x1 + (x2 - x1) * t1) * SCALE, (y1 + (y2 - y1) * t1) * SCALE,
                                    (x1 + (x2 - x1) * t2) * SCALE, (y1 + (y2 - y1) * t2) * SCALE), fill=color, width=width * SCALE)
            else:
                self.draw.line((x1 * SCALE, y1 * SCALE, x2 * SCALE, y2 * SCALE), fill=color, width=width * SCALE)

    def arrow(self, points, color=TEAL, width=3, head=11):
        self.line(points, color, width)
        x, y = points[-1]
        px, py = points[-2]
        angle = math.atan2(y - py, x - px)
        self.polygon([(x, y), (x - head * math.cos(angle) + head * .55 * math.sin(angle), y - head * math.sin(angle) - head * .55 * math.cos(angle)),
                      (x - head * math.cos(angle) - head * .55 * math.sin(angle), y - head * math.sin(angle) + head * .55 * math.cos(angle))], color)

    def circle(self, x, y, r, fill):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>')
        self.draw.ellipse(((x - r) * SCALE, (y - r) * SCALE, (x + r) * SCALE, (y + r) * SCALE), fill=fill)

    def text(self, x, y, content, *, style, color=INK, anchor="start"):
        assert "?" not in content and "？" not in content, content
        spec = TEXT_STYLES[style]
        font = text_font(style)
        pil_anchor = {"start": "ls", "middle": "ms", "end": "rs"}[anchor]
        bbox = self.draw.textbbox((x * SCALE, y * SCALE), content, font=font, anchor=pil_anchor)
        assert bbox[0] >= 0 and bbox[1] >= 0 and bbox[2] <= W * SCALE and bbox[3] <= H * SCALE, (content, bbox)
        self.draw.text((x * SCALE, y * SCALE), content, font=font, fill=color, anchor=pil_anchor)
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="{FONT_FAMILY}, PingFang SC, Microsoft YaHei, sans-serif" font-size="{spec["size_px"]}" font-weight="{spec["weight"]}" data-text-style="{style}" text-anchor="{anchor}">{escape(content)}</text>')
        self.texts.append(content)
        self.text_style_counts[style] += 1

    def header(self, number, subtitle, section="业务分析"):
        self.rect(104, 76, 44, 5, TEAL)
        self.text(165, 88, f"图 2-{int(number):02d}  /  {section}", style="label", color=TEAL)
        self.text(1696, 88, "一芥智能研究院", style="label", color=MUTED, anchor="end")
        self.text(104, 177, self.title, style="title")
        self.text(104, 237, subtitle, style="subtitle", color=MUTED)

    def footer(self, note):
        self.line([(104, 1152), (1696, 1152)], LINE, 2)
        self.text(104, 1202, note, style="label", color=MUTED)
        self.text(104, 1243, "《企业数智化转型研究报告》 · 第二章 · 一芥智能研究院", style="label", color=MUTED)

    def save(self):
        # Measure after downsampling so antialiased edges also retain the margin.
        bitmap = self.im.resize((W, H), Image.Resampling.LANCZOS)
        bounds = ImageChops.difference(bitmap, Image.new("RGB", bitmap.size, WHITE)).getbbox()
        if bounds is None:
            raise ValueError(f"Cannot export an empty figure: {self.slug}")
        bitmap = ImageOps.expand(bitmap.crop(bounds), border=OUTER_MARGIN, fill=WHITE)
        width, height = bitmap.size
        x, y = bounds[0] - OUTER_MARGIN, bounds[1] - OUTER_MARGIN
        # Keep original coordinates: the PDF renderer supports viewBox origins.
        # Its background must match the viewport to stay inside the image area.
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="{x} {y} {width} {height}" role="img" aria-labelledby="title description">',
            f'<title id="title">{escape(self.title)}</title>',
            f'<desc id="description">{escape(self.description)}</desc>',
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{WHITE}"/>',
            *self.parts,
            "</svg>",
        ]
        (OUT / f"{self.slug}.svg").write_text("\n".join(parts), encoding="utf-8")
        bitmap.save(OUT / f"{self.slug}.png", optimize=True)
        metadata = {"slug": self.slug, "title": self.title, "description": self.description,
                    "dimensions": [width, height], "outer_margin_px": OUTER_MARGIN,
                    "typography": TYPOGRAPHY, "text_style_counts": dict(self.text_style_counts),
                    "visible_text": self.texts}
        (OUT / f"{self.slug}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return metadata
