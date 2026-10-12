"""Build three original, editable diagrams for section 2.2 style review."""

from pathlib import Path
from html import escape
import json
import math

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parent
W, H, SCALE = 1800, 1280, 2
INK = "#183440"
TEAL = "#197C86"
MUTED = "#607681"
LINE = "#CBD9DE"
PALE = "#EAF3F3"
MID = "#CCE3E4"
LIGHT = "#F3F6F7"
WHITE = "#FFFFFF"
BODY_FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
HEADING_FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


class Figure:
    def __init__(self, slug, title, description):
        self.slug, self.title, self.description = slug, title, description
        self.im = Image.new("RGB", (W * SCALE, H * SCALE), WHITE)
        self.draw = ImageDraw.Draw(self.im)
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title description">',
            f'<title id="title">{escape(title)}</title>',
            f'<desc id="description">{escape(description)}</desc>',
            f'<rect width="{W}" height="{H}" fill="{WHITE}"/>',
        ]
        self.texts = []

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

    def text(self, x, y, content, size=30, color=INK, anchor="start", heading=False):
        assert "?" not in content and "？" not in content, content
        path = HEADING_FONT if heading else BODY_FONT
        font = ImageFont.truetype(path, size * SCALE)
        pil_anchor = {"start": "ls", "middle": "ms", "end": "rs"}[anchor]
        bbox = self.draw.textbbox((x * SCALE, y * SCALE), content, font=font, anchor=pil_anchor)
        assert bbox[0] >= 0 and bbox[1] >= 0 and bbox[2] <= W * SCALE and bbox[3] <= H * SCALE, (content, bbox)
        self.draw.text((x * SCALE, y * SCALE), content, font=font, fill=color, anchor=pil_anchor)
        family = "STHeiti" if heading else "Hiragino Sans GB"
        self.parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="{family}, PingFang SC, Microsoft YaHei, sans-serif" font-size="{size}" text-anchor="{anchor}">{escape(content)}</text>')
        self.texts.append(content)

    def header(self, number, subtitle):
        self.rect(104, 76, 44, 5, TEAL)
        self.text(165, 88, f"图 2.2-{number}  /  业务分析", 25, TEAL)
        self.text(1696, 88, "一芥智能研究院", 24, MUTED, "end")
        self.text(104, 177, self.title, 58, heading=True)
        self.text(104, 237, subtitle, 29, MUTED)

    def footer(self, note):
        self.line([(104, 1152), (1696, 1152)], LINE, 2)
        self.text(104, 1202, note, 24, MUTED)
        self.text(104, 1243, "《企业数智化转型研究报告》 · 2.2 配图样稿 · v1", 21, MUTED)

    def save(self):
        self.parts.append("</svg>")
        (OUT / f"{self.slug}.svg").write_text("\n".join(self.parts), encoding="utf-8")
        self.im.resize((W, H), Image.Resampling.LANCZOS).save(OUT / f"{self.slug}.png", optimize=True)
        return {"slug": self.slug, "title": self.title, "description": self.description, "visible_text": self.texts}


def funnel():
    f = Figure("01-sales-funnel", "销售漏斗与六项业务改进目标", "目标1扩大有效线索基数，目标2改善线索转商机，目标3至6共同支持商机转合同。")
    f.header(1, "有效线索基数与阶段转化率共同影响签约合同数量。")

    f.text(510, 326, "潜在线索", 32, MUTED, "middle")
    f.arrow([(510, 346), (510, 394)], MUTED, 2)
    f.text(548, 379, "初筛与核实", 24, MUTED)

    f.polygon([(190, 410), (830, 410), (770, 552), (250, 552)], PALE)
    f.text(510, 473, "有效线索", 47, anchor="middle", heading=True)
    f.text(510, 521, "符合目标客群与可跟进标准", 26, MUTED, "middle")
    f.arrow([(510, 566), (510, 636)], TEAL, 3)
    f.rect(362, 584, 296, 43, WHITE)
    f.text(510, 615, "线索转商机率", 31, TEAL, "middle")

    f.polygon([(260, 654), (760, 654), (710, 798), (310, 798)], MID)
    f.text(510, 721, "商机", 47, anchor="middle", heading=True)
    f.text(510, 767, "需求与推进条件经过验证", 26, MUTED, "middle")
    f.arrow([(510, 813), (510, 915)], TEAL, 3)
    f.rect(362, 842, 296, 43, WHITE)
    f.text(510, 874, "商机转合同率", 31, TEAL, "middle")

    f.polygon([(320, 933), (700, 933), (662, 1064), (358, 1064)], TEAL)
    f.text(510, 1009, "签约合同", 44, WHITE, "middle", True)

    f.line([(847, 479), (955, 479)], TEAL, 2)
    f.circle(847, 479, 4, TEAL)
    f.text(1010, 439, "目标 1", 27, TEAL)
    f.text(1010, 491, "持续增加有效线索", 40, heading=True)
    f.text(1010, 534, "线索开发与筛选持续扩大有效基数。", 27, MUTED)

    f.line([(701, 603), (955, 603)], TEAL, 2)
    f.circle(701, 603, 4, TEAL)
    f.text(1010, 590, "目标 2", 27, TEAL)
    f.text(1010, 642, "提高线索转为商机的比例", 40, heading=True)
    f.text(1010, 685, "客户了解与机会验证支持阶段转化。", 27, MUTED)

    f.line([(701, 862), (955, 862)], TEAL, 2)
    f.circle(701, 862, 4, TEAL)
    f.line([(981, 785), (965, 785), (965, 1076), (981, 1076)], TEAL, 2)
    f.text(1010, 785, "目标 3—6", 27, TEAL)
    f.text(1010, 837, "共同支持商机转合同", 40, heading=True)
    for y, num, text in [
        (898, "03", "准确确认需求与沟通输出"),
        (952, "04", "完善方案与商务准备"),
        (1006, "05", "落实会后执行与验收"),
        (1060, "06", "推进客户决策与签约"),
    ]:
        f.text(1010, y, num, 26, TEAL)
        f.text(1067, y, text, 31)
    f.footer("漏斗宽度仅作示意。六项改进的效果需结合企业基线与持续记录验证。")
    return f.save()


def diagnosis():
    f = Figure("02-business-diagnosis", "业务差距经核实后形成改进目标", "诊断从待核实差距出发，经访谈、记录与真实任务核实工作问题，再选定目标、明确观察安排并跟踪结果。")
    f.header(2, "业务负责人从表现差距出发，核实工作问题并持续跟踪改进。")
    steps = [
        ("识别表现差距", ["检查有效线索基数", "比较阶段转化情况", "定位流失与停滞"]),
        ("核实工作问题", ["访谈业务人员", "核对记录与真实任务", "确认具体工作问题"]),
        ("选定重点目标", ["选择本轮改进重点", "明确期望业务表现", "对应六项改进目标"]),
        ("明确观察安排", ["登记当前值与目标值", "固定观察期与口径", "指定记录责任人"]),
        ("跟踪业务结果", ["持续记录线索与转化", "核对丢单或延迟原因", "复核本轮改进表现"]),
    ]
    for i, (title, lines) in enumerate(steps):
        x = 104 + i * 330
        f.text(x, 382, f"0{i + 1}", 56, TEAL, heading=True)
        f.line([(x, 412), (x + 252, 412)], TEAL if i == 1 else LINE, 3)
        f.text(x, 474, title, 39, heading=True)
        for j, line in enumerate(lines):
            f.text(x, 546 + j * 51, line, 27, MUTED)
        if i < 4:
            f.arrow([(x + 274, 451), (x + 307, 451)], TEAL, 2, 9)

    f.line([(1543, 704), (1543, 751), (230, 751), (230, 706)], LINE, 2)
    f.arrow([(230, 730), (230, 706)], MUTED, 2, 9)
    f.rect(661, 727, 488, 46, WHITE)
    f.text(905, 759, "跟踪结果用于复核与调整改进重点。", 27, MUTED, "middle")

    f.rect(104, 847, 1592, 227, LIGHT, radius=12)
    f.text(145, 902, "过程变化需要继续接受业务结果检验", 33, heading=True)
    f.text(145, 970, "整理工时 · 记录质量 · 方案返工", 30)
    f.text(145, 1021, "用于解释工作过程的变化。", 27, MUTED)
    f.arrow([(776, 984), (990, 984)], TEAL, 2)
    f.text(883, 956, "继续检验", 25, TEAL, "middle")
    f.text(1040, 970, "有效线索 · 阶段转化 · 签约合同", 30)
    f.text(1040, 1021, "用于判断业务表现的改善。", 27, MUTED)
    f.footer("差距需通过访谈、记录与真实任务核实。过程指标的改善仍需通过业务结果检验。")
    return f.save()


def cohort():
    f = Figure("03-conversion-cohort", "阶段转化率按同一批入段对象计算", "固定同一批进入本段的对象，跟踪至约定截止日。已经推进的本批对象构成分子，全部本批入段对象构成分母。")
    f.header(3, "进入本段的全部对象构成分母，截止日前推进的本批对象构成分子。")

    f.line([(198, 361), (1602, 361)], LINE, 3)
    f.circle(198, 361, 7, TEAL)
    f.circle(1602, 361, 7, TEAL)
    f.text(198, 332, "按约定入段时间窗口选取", 28, MUTED)
    f.text(1602, 332, "跟踪至约定截止日", 28, MUTED, "end")

    f.rect(104, 526, 548, 249, PALE, radius=12)
    f.text(145, 578, "固定入段批次", 27, TEAL)
    f.text(145, 639, "同一批进入本段的对象", 39, heading=True)
    f.text(145, 695, "本批全部对象始终构成分母。", 29, MUTED)
    f.text(145, 741, "线索与商机分别明确统计口径。", 26, MUTED)

    f.line([(652, 650), (811, 650)], TEAL, 2)
    f.line([(811, 507), (811, 831)], TEAL, 2)
    f.circle(811, 650, 5, TEAL)
    for y in (507, 669, 831):
        f.arrow([(811, y), (937, y)], TEAL, 2)

    states = [
        (438, "已进入下一段", "计入分子，同时保留在分母。", True),
        (600, "未进入下一段，仍在本段", "保留在分母，继续跟踪后续进展。", False),
        (762, "未进入下一段，已经退出", "保留在分母，记录退出原因。", False),
    ]
    for y, title, sub, active in states:
        f.rect(957, y, 739, 138, PALE if active else LIGHT, radius=10)
        f.rect(957, y, 5, 138, TEAL if active else LINE)
        f.text(990, y + 51, title, 35, heading=True)
        f.text(990, y + 100, sub, 28, MUTED)

    f.text(104, 1048, "阶段转化率", 37, heading=True)
    f.text(347, 1048, "=", 37, TEAL)
    f.text(952, 1008, "该批截至截止日已进入下一段的对象数", 31, anchor="middle")
    f.line([(487, 1030), (1417, 1030)], INK, 2)
    f.text(952, 1075, "该批进入本段的对象总数", 31, anchor="middle")
    f.text(1470, 1048, "× 100%", 35, TEAL)
    f.footer("未推进和退出对象均保留在分母中。仍停留的对象尚不能判定为最终失败。")
    return f.save()


def main():
    manifest = [funnel(), diagnosis(), cohort()]
    (OUT / "manifest.json").write_text(json.dumps({"version": 1, "dimensions": [W, H], "figures": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    thumbs = [Image.open(OUT / f"{f['slug']}.png").resize((900, 640), Image.Resampling.LANCZOS) for f in manifest]
    sheet = Image.new("RGB", (940, 2000), "#E6ECEE")
    for i, thumb in enumerate(thumbs):
        sheet.paste(thumb, (20, 20 + i * 660))
    sheet.save(OUT / "style-overview.png", optimize=True)
    print(json.dumps({"output": str(OUT), "figures": [f["slug"] for f in manifest], "all_text_declarative": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
