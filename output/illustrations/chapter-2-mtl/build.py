"""Rebuild and validate all 16 editable MTL diagrams without touching old figures."""
from collections import Counter
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET

from fontTools.ttLib import TTFont
from PIL import Image, ImageChops, ImageDraw, ImageOps

import figures
import supplemental_figures
from drawing import (OUT, OUTER_MARGIN, TEXT_STYLES, TYPOGRAPHY, WHITE, W, H,
                     INK, BODY_FONT, HEADING_FONT, FONT_INDEX, HEADING_FONT_INDEX,
                     FONT_FAMILY, HEADING_FONT_FAMILY, text_font)


def main():
    all_figures = figures.build() + supplemental_figures.build()
    all_figures.sort(key=lambda figure: figure["slug"])
    assert len(all_figures) == 16
    assert [int(figure["slug"].split("-", 1)[0]) for figure in all_figures] == list(range(1, 17))
    fonts = {}
    for path, index in [(BODY_FONT, FONT_INDEX), (HEADING_FONT, HEADING_FONT_INDEX)]:
        with TTFont(path, fontNumber=index) as face:
            fonts[(path, index)] = set(face.getBestCmap())
    missing_glyphs, overlaps = [], []
    for figure in all_figures:
        root = ET.parse(OUT / (figure["slug"] + ".svg")).getroot()
        with Image.open(OUT / (figure["slug"] + ".png")) as source:
            bitmap = source.convert("RGB")
        bounds = ImageChops.difference(bitmap, Image.new("RGB", bitmap.size, WHITE)).getbbox()
        assert bounds is not None, figure["slug"]
        margins = (bounds[0], bounds[1], bitmap.width - bounds[2], bitmap.height - bounds[3])
        assert margins == (OUTER_MARGIN,) * 4, (figure["slug"], margins)
        assert list(bitmap.size) == figure["dimensions"]
        assert [int(root.get("width")), int(root.get("height"))] == figure["dimensions"]
        counts, svg_text = Counter(), []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] != "text":
                continue
            style = node.get("data-text-style")
            assert style in TEXT_STYLES, (figure["slug"], style)
            spec = TEXT_STYLES[style]
            assert int(node.get("font-size")) == spec["size_px"]
            assert int(node.get("font-weight")) == spec["weight"]
            heading = spec["weight"] == 500
            assert node.get("font-family").split(",", 1)[0] == (HEADING_FONT_FAMILY if heading else FONT_FAMILY)
            content = "".join(node.itertext())
            cmap = fonts[(HEADING_FONT, HEADING_FONT_INDEX) if heading else (BODY_FONT, FONT_INDEX)]
            missing = {char for char in content if ord(char) not in cmap}
            if missing:
                missing_glyphs.append((figure["slug"], content, sorted(missing)))
            counts[style] += 1
            svg_text.append(content)
        assert svg_text == figure["visible_text"]
        assert dict(counts) == figure["text_style_counts"]
        assert figure["typography"] == TYPOGRAPHY
        assert len(svg_text) == len(figure["text_bounds"])
        for i, first in enumerate(figure["text_bounds"]):
            for j in range(i + 1, len(figure["text_bounds"])):
                second = figure["text_bounds"][j]
                intersection = (min(first[2], second[2]) - max(first[0], second[0]),
                                min(first[3], second[3]) - max(first[1], second[1]))
                if intersection[0] > 1 and intersection[1] > 1:
                    overlaps.append((figure["slug"], svg_text[i], svg_text[j], intersection))
        assert not any("?" in content or "？" in content for content in svg_text)
    assert not missing_glyphs, missing_glyphs
    assert not overlaps, overlaps
    data = {"chapter": "第二章 最小执行单位：从人到任务", "workflow": "MTL：从市场到线索",
            "date": "2026-10-13", "layout_dimensions": [W, H], "outer_margin_px": OUTER_MARGIN,
            "typography": TYPOGRAPHY, "figure_count": len(all_figures),
            "source": "本报告整理；图示不代表华为官方流程阶段或定义", "figures": all_figures}
    (OUT / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    thumb_w, gap, label_h = 600, 24, 78
    thumb_h = max(round(thumb_w * figure["dimensions"][1] / figure["dimensions"][0]) for figure in all_figures)
    cols, rows = 3, math.ceil(len(all_figures) / 3)
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap,
                             rows * (thumb_h + label_h) + (rows + 1) * gap), "#E7EDF8")
    draw = ImageDraw.Draw(sheet)
    font = text_font("label", scale=1)
    for i, figure in enumerate(all_figures):
        row, col = divmod(i, cols)
        x, y = gap + col * (thumb_w + gap), gap + row * (thumb_h + label_h + gap)
        with Image.open(OUT / (figure["slug"] + ".png")) as source:
            thumbnail = ImageOps.contain(source, (thumb_w, thumb_h), Image.Resampling.LANCZOS)
        sheet.paste(thumbnail, (x + (thumb_w - thumbnail.width) // 2, y))
        label = f"图2-{i + 1:02d}  {figure['title']}"
        first_line = ""
        for char in label:
            if draw.textlength(first_line + char, font=font) > thumb_w - 8:
                break
            first_line += char
        draw.text((x + 4, y + thumb_h + 10), first_line, fill=INK, font=font)
        if len(first_line) < len(label):
            draw.text((x + 4, y + thumb_h + 41), label[len(first_line):], fill=INK, font=font)
    sheet.save(OUT / "chapter-2-overview.png", optimize=True)
    print(json.dumps({"figure_count": len(all_figures), "svg_parsed": len(all_figures),
                      "png_verified": len(all_figures), "outer_margin_px": OUTER_MARGIN,
                      "typography_consistent": True, "missing_glyphs": 0,
                      "text_overlaps": 0, "searchable_svg_text": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
