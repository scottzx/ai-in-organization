"""Rebuild chapter two's editable SVGs, PNGs, index metadata and overview."""
from pathlib import Path
from collections import Counter
import json
import math
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw, ImageOps

import analysis_figures
import foundation_figures
import goal_figures
import overview_figures
from drawing import INK, OUTER_MARGIN, TEXT_STYLES, TYPOGRAPHY, WHITE, W, H, text_font


OUT = Path(__file__).resolve().parent


def main():
    figures = analysis_figures.build() + foundation_figures.build() + goal_figures.build() + overview_figures.build()
    figures.sort(key=lambda f: f["slug"])
    assert len(figures) == 16
    assert [int(f["slug"].split("-", 1)[0]) for f in figures] == list(range(1, 17))
    for figure in figures:
        root = ET.parse(OUT / (figure["slug"] + ".svg")).getroot()
        with Image.open(OUT / (figure["slug"] + ".png")) as image:
            bitmap = image.convert("RGB")
        bounds = ImageChops.difference(bitmap, Image.new("RGB", bitmap.size, WHITE)).getbbox()
        assert bounds is not None, figure["slug"]
        margins = (bounds[0], bounds[1], bitmap.width - bounds[2], bitmap.height - bounds[3])
        assert margins == (OUTER_MARGIN,) * 4, (figure["slug"], margins)
        assert list(bitmap.size) == figure["dimensions"]
        assert [int(root.get("width")), int(root.get("height"))] == figure["dimensions"]
        text_styles = Counter()
        svg_text = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] != "text":
                continue
            style = node.get("data-text-style")
            assert style in TEXT_STYLES, (figure["slug"], style)
            spec = TEXT_STYLES[style]
            assert int(node.get("font-size")) == spec["size_px"]
            assert int(node.get("font-weight")) == spec["weight"]
            assert node.get("font-family").split(",", 1)[0] == TYPOGRAPHY["font_family"]
            text_styles[style] += 1
            svg_text.append("".join(node.itertext()))
        assert svg_text == figure["visible_text"]
        assert dict(text_styles) == figure["text_style_counts"]
        assert figure["typography"] == TYPOGRAPHY
        assert not any("?" in t or "？" in t for t in figure["visible_text"])
    data = {"chapter": "第二章 最小执行单位：从人到任务", "date": "2026-10-12",
            "layout_dimensions": [W, H], "outer_margin_px": OUTER_MARGIN,
            "typography": TYPOGRAPHY,
            "figure_count": len(figures), "figures": figures}
    sizes = {tuple(figure["dimensions"]) for figure in figures}
    if len(sizes) == 1:
        data["dimensions"] = list(next(iter(sizes)))
    (OUT / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    thumb_w, gap, label_h = 600, 24, 48
    thumb_h = max(round(thumb_w * f["dimensions"][1] / f["dimensions"][0]) for f in figures)
    cols = 3
    rows = math.ceil(len(figures) / cols)
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap, rows * (thumb_h + label_h) + (rows + 1) * gap), "#E7EDF8")
    draw = ImageDraw.Draw(sheet)
    font = text_font("label", scale=1)
    for i, figure in enumerate(figures):
        row, col = divmod(i, cols)
        x, y = gap + col * (thumb_w + gap), gap + row * (thumb_h + label_h + gap)
        with Image.open(OUT / (figure["slug"] + ".png")) as source:
            thumb = ImageOps.contain(source, (thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x + (thumb_w - thumb.width) // 2, y))
        draw.text((x + 4, y + thumb_h + 12), f"图2-{i + 1:02d}  {figure['title']}", fill=INK, font=font)
    sheet.save(OUT / "chapter-2-overview.png", optimize=True)
    print(json.dumps({"figure_count": len(figures), "svg_parsed": len(figures), "png_verified": len(figures),
                      "outer_margin_px": OUTER_MARGIN, "typography_consistent": True,
                      "declarative_labels": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
