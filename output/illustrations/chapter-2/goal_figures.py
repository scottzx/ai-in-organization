"""Six chapter 2.3 diagrams in the approved chapter illustration style."""

from pathlib import Path
import json

from PIL import Image, ImageOps

from drawing import Figure, OUT, INK, TEAL, MUTED, LINE, PALE, MID, LIGHT, WHITE


def lines(f, x, y, content, style="body", color=MUTED, step=45):
    for i, text in enumerate(content):
        f.text(x, y + i * step, text, style=style, color=color)


def measure(f, x, y, w, h, num, title, content, output, emphasized=False):
    f.rect(x, y, w, h, PALE if emphasized else LIGHT, radius=12)
    f.text(x + 32, y + 49, f"举措 {num}", style='label', color=TEAL)
    f.text(x + 32, y + 110, title, style='heading')
    lines(f, x + 32, y + 176, content)
    f.line([(x + 32, y + h - 121), (x + w - 32, y + h - 121)], LINE, 2)
    f.text(x + 32, y + h - 78, "本步交付", style='label', color=TEAL)
    f.text(x + 32, y + h - 32, output, style='body')


def role_strip(f, y, roles, h=178):
    f.rect(104, y, 1592, h, WHITE, stroke=LINE, radius=12)
    for i, (title, texts) in enumerate(roles):
        x = 137 + i * 523
        if i:
            f.line([(x - 23, y + 28), (x - 23, y + h - 28)], LINE, 2)
        f.text(x, y + 47, title, style='subheading', color=TEAL)
        lines(f, x, y + 94, texts, style="dense_body", step=41)


def goal_1():
    f = Figure(
        "06-goal-1-leads",
        "目标1：持续增加可以跟进的有效线索",
        "目标客群与有效标准、线索来源复核、核实去重与跟进承接共同扩大有效线索基数。AI辅助整理与检索，程序记录与去重，销售确认有效性并落实联系。",
    )
    f.header(6, "客群标准、来源复核与跟进承接共同扩大有效线索基数。", section="业务举措")
    specs = [
        ("1.1", "明确客群与有效标准", ["结合产品能力与历史成交", "核实客户需求与筛选依据", "负责人决定本轮资源取舍"], "目标客群与有效线索标准"),
        ("1.2", "拓展并复核线索来源", ["经营渠道、转介绍与活动", "复核候选客户及来源依据", "观察后续跟进与推进情况"], "带来源依据的候选清单"),
        ("1.3", "核实、去重并分配跟进", ["核实客户与联系人可用性", "去重后明确责任人与下一步", "确认接手、联系并记录回应"], "可跟进的有效线索记录"),
    ]
    for i, spec in enumerate(specs):
        measure(f, 104 + i * 546, 334, 500, 479, *spec, emphasized=i == 2)
        if i < 2:
            f.arrow([(614 + i * 546, 571), (640 + i * 546, 571)], width=2, head=9)

    f.text(104, 873, "候选名单经核实并落实承接后，才能形成可以跟进的有效线索。", style='subheading')
    role_strip(f, 919, [
        ("AI辅助整理与检索", ["归纳历史客户、检索候选资料", "整理核实问题与跟进建议"]),
        ("程序保留记录与状态", ["按客户标识去重并记录分配", "按可靠规则发起或周期检查"]),
        ("销售承担有效性与跟进责任", ["核实客户、确认接手并联系", "接管异常，调整标准与来源"]),
    ])
    f.footer("候选名单数量不直接计为有效线索。更新频率需与核实和跟进能力匹配。")
    return f.save()


def goal_2():
    f = Figure(
        "07-goal-2-opportunities",
        "目标2：提高线索转为商机的比例",
        "查清客户现状与历史、验证需求及推进条件，再由负责人决定推进、培育或退出。AI整理依据和信息缺口，评分与标签不能直接判定商机成立。",
    )
    f.header(7, "客户背景与推进条件经过验证后，负责人决定线索的后续投入。", section="业务举措")

    cards = [
        ("2.1", "查清客户现状与历史", ["整理业务、联系人与历史承诺", "AI形成带来源与时间的简报", "销售补背景并核实资料可信度"]),
        ("2.2", "验证需求与推进条件", ["确认需求、角色与采购安排", "AI准备问题并提示信息缺口", "销售向客户核实真实意愿"]),
        ("2.3", "决定推进、培育与退出", ["保留事实、判断与待确认项", "评分与建议供业务人员参考", "负责人决定状态与资源投入"]),
    ]
    for i, (num, title, content) in enumerate(cards):
        x = 104 + i * 546
        f.rect(x, 334, 500, 298, PALE if i == 2 else LIGHT, radius=12)
        f.text(x + 32, 383, f"举措 {num}", style='label', color=TEAL)
        f.text(x + 32, 444, title, style='heading')
        lines(f, x + 32, 504, content, style="body", step=45)
        if i < 2:
            f.arrow([(x + 510, 482), (x + 536, 482)], width=2, head=9)

    f.text(104, 696, "验证结果进入三类处置，并保留判断依据与后续安排。", style='subheading')
    outcomes = [
        ("推进为商机", ["需求与推进条件达到商机标准", "记录验证依据与下一步安排"], True),
        ("继续培育", ["写明尚未满足的条件", "记录复查理由与日期"], False),
        ("退出跟进", ["记录停止投入的依据", "重要客户例外由负责人说明"], False),
    ]
    for i, (title, content, active) in enumerate(outcomes):
        x = 104 + i * 546
        f.rect(x, 739, 500, 194, PALE if active else LIGHT, radius=12)
        f.rect(x, 739, 5, 194, TEAL if active else LINE)
        f.text(x + 32, 794, title, style='heading')
        lines(f, x + 32, 849, content, style="body", step=44)

    f.rect(104, 983, 1592, 115, WHITE, stroke=LINE, radius=12)
    f.text(137, 1030, "记录维护支持持续复核", style='subheading', color=TEAL)
    f.text(137, 1073, "程序按日期提醒复查；关键条件变化后，再提出重新验证的任务。", style='body', color=MUTED)
    f.footer("意向标签与自动评分供销售继续验证。商机成立与资源投入仍由业务负责人判断。")
    return f.save()


def goal_3():
    f = Figure(
        "08-goal-3-requirements",
        "目标3：形成可以交接的沟通输出",
        "沟通前明确目的与待确认事项，沟通后保留事实、需求、分歧和承诺，再核对结论并确认接收者。AI形成整理稿，双方核对后才形成可交接的输出。",
    )
    f.header(8, "原始记录经过核对与确认后，进入方案准备和会后执行。", section="业务举措")
    specs = [
        ("3.1", "确定本轮沟通重点", ["结合客户背景与上次结论", "明确待确认事项与沟通目的", "安排议程、人员与会前材料"], "议程与会前资料"),
        ("3.2", "保留沟通依据", ["分类保存事实、需求与分歧", "保留承诺并关联原始记录", "区分客户原话与内部判断"], "可回到原始依据的整理稿"),
        ("3.3", "核对结论与输出", ["客户及内部人员核对原意", "区分已达成一致与待确认", "保留更正版本与接收关系"], "经确认的输出与接收者"),
    ]
    for i, spec in enumerate(specs):
        measure(f, 104 + i * 546, 334, 500, 434, *spec, emphasized=i == 2)
        if i < 2:
            f.arrow([(614 + i * 546, 550), (640 + i * 546, 550)], width=2, head=9)

    f.rect(104, 817, 722, 281, WHITE, stroke=LINE, radius=12)
    f.text(137, 869, "AI辅助准备、分类与查漏", style='subheading', color=TEAL)
    lines(f, 137, 928, ["从已有资料准备简报与待确认项", "对照议程与原始记录整理输出", "标出更正影响的材料与使用者"], style="body", step=48)
    f.arrow([(849, 955), (887, 955)], width=2, head=10)

    f.rect(909, 817, 787, 281, PALE, radius=12)
    f.text(942, 869, "确认结果进入下一位使用者", style='subheading')
    handoffs = [("已确认需求", "方案人员"), ("待确认事项", "指定责任人"), ("后续动作", "执行与验收人")]
    for i, (left, right) in enumerate(handoffs):
        y = 930 + i * 48
        f.text(942, y, left, style='body')
        f.arrow([(1155, y - 10), (1225, y - 10)], width=2, head=9)
        f.text(1264, y, right, style='body')
    f.footer("重要结论仍须双方核对。录音需经授权，录音、逐字稿和确认后的输出各有用途。")
    return f.save()


def goal_4():
    f = Figure(
        "09-goal-4-proposals",
        "目标4：提高方案与商务准备质量",
        "从已确认需求展开可比较方案，核实能力、报价、交期与承诺，再准备回应客户待决事项的汇报。AI辅助找依据和起草，程序完成计算与字段比对，有权限的人批准对外承诺。",
    )
    f.header(9, "已确认需求展开为可比较方案，商务承诺经批准后进入对外材料。", section="业务举措")
    specs = [
        ("4.1", "展开可比较的解决思路", ["写清范围、假设与可选做法", "核实产品适配与实现可行性", "共同复核收益假设和取舍"], "带依据的备选方案"),
        ("4.2", "审核能力与商务承诺", ["核实能力、价格依据与交期", "技术、商务及授权人员审核", "保存可追溯的批准记录"], "经批准的报价与承诺"),
        ("4.3", "回应客户的决策事项", ["从已审核方案提炼汇报重点", "准备证据、演示与答问清单", "根据客户反馈更新相关部分"], "支持客户决策的汇报材料"),
    ]
    for i, spec in enumerate(specs):
        measure(f, 104 + i * 546, 334, 500, 468, *spec, emphasized=i == 1)
        if i < 2:
            f.arrow([(614 + i * 546, 566), (640 + i * 546, 566)], width=2, head=9)

    f.text(104, 869, "计算、整理与专业审核形成分工，审核依据和批准责任持续可追溯。", style='subheading')
    role_strip(f, 919, [
        ("AI查依据与起草材料", ["整理备选思路与材料缺项", "复用经验证的方法与模板"]),
        ("程序计算与字段比对", ["按固定公式计算并核对字段", "检查产品、价格与版本有效性"]),
        ("专业人员审核并批准承诺", ["判断适配、可行性与收益假设", "授权人员批准报价、交期与承诺"]),
    ])
    f.footer("需求或商务条件变化后，受影响内容需复核或重审，并撤回过期版本。")
    return f.save()


def goal_5():
    f = Figure(
        "10-goal-5-execution",
        "目标5：让会后任务完成并通过验收",
        "把已确认决定落实为有输入、产物、执行者、期限和验收人的任务。执行者确认接手，完成并提交产物，验收通过后再关闭和交接，阻塞与退回分别进入协调和修改。",
    )
    f.header(10, "任务从已确认决定出发，经过实际执行与验收后进入下一步。", section="业务举措")

    f.rect(104, 327, 1592, 190, LIGHT, radius=12)
    f.text(137, 376, "任务交接先写清五项约定", style='subheading')
    fields = [("输入依据", "使用已确认记录"), ("交付产物", "写明可检查的输出"), ("执行者", "确认接手与资源"), ("完成期限", "约定合理时间"), ("验收人", "依据标准判断可用")]
    for i, (title, detail) in enumerate(fields):
        x = 137 + i * 312
        if i:
            f.line([(x - 22, 402), (x - 22, 489)], LINE, 2)
        f.text(x, 434, title, style='subheading', color=TEAL)
        f.text(x, 480, detail, style='dense_body', color=MUTED)

    specs = [
        ("5.1", "将决定落实为任务", ["AI从确认记录提炼任务草稿", "相关人员补齐约定并接手", "表格或任务模块登记与去重"], "已承接的任务记录"),
        ("5.2", "执行任务并处理阻塞", ["执行者完成工作并提交产物", "AI在验证范围内参与执行", "缺资料、决策与资源及时协调"], "产物与阻塞处理记录"),
        ("5.3", "验收产物并更新状态", ["验收人按标准判断可用性", "AI按清单辅助检查并留意见", "通过后关闭并交给下游"], "通过验收的产物与交接"),
    ]
    for i, spec in enumerate(specs):
        measure(f, 104 + i * 546, 555, 500, 420, *spec, emphasized=i == 2)
        if i < 2:
            f.arrow([(614 + i * 546, 753), (640 + i * 546, 753)], width=2, head=9)

    f.line([(1446, 990), (1446, 1038), (900, 1038)], MUTED, 2)
    f.arrow([(900, 1038), (900, 990)], MUTED, width=2, head=9)
    f.rect(1008, 1014, 344, 45, WHITE)
    f.text(1180, 1045, "退回意见进入修改", style='label', color=MUTED, anchor="middle")
    f.text(104, 1104, "完成状态以实际产物与验收为依据；负责人协调逾期、阻塞与长期未验收事项。", style='subheading')
    f.footer("自动执行需先验证真实任务，明确授权、失败记录、停止条件与人工接管。")
    return f.save()


def goal_6():
    f = Figure(
        "11-goal-6-contracts",
        "目标6：围绕决策障碍推进至签约",
        "从客户反馈确认真实决策障碍，由销售主导沟通与谈判，再确认签约条件并完成履约交接。AI辅助汇集依据、准备选项与核对版本，承诺和签署按授权办理。",
    )
    f.header(11, "客户反馈用于核实决策障碍，销售主导协商并落实签约与交接。", section="业务举措")
    specs = [
        ("6.1", "识别当前决策障碍", ["查明角色、证据与采购步骤", "区分事实、推测与待核实项", "AI汇集记录，销售向客户确认"], "有依据的待决事项"),
        ("6.2", "沟通与谈判解决障碍", ["选择合适对象、时机与选项", "AI辅助准备草稿与谈判材料", "销售协商利益并争取决定"], "客户决定与后续行动"),
        ("6.3", "确认条件并完成签约", ["比对条款、批准版本与未决项", "授权人员批准承诺并签署", "工具提示事项并准备交接清单"], "签约合同与履约交接安排"),
    ]
    for i, spec in enumerate(specs):
        measure(f, 104 + i * 546, 334, 500, 467, *spec, emphasized=i == 2)
        if i < 2:
            f.arrow([(614 + i * 546, 565), (640 + i * 546, 565)], width=2, head=9)

    f.rect(104, 852, 1592, 246, PALE, radius=12)
    f.text(137, 905, "签约后，销售与交付团队共同确认履约交接", style='subheading')
    f.text(137, 969, "客户需求", style='body')
    f.text(388, 969, "合同承诺", style='body')
    f.text(639, 969, "履约条件", style='body')
    f.text(890, 969, "付款条件", style='body')
    f.arrow([(1104, 958), (1225, 958)], width=2, head=10)
    f.text(1271, 969, "交付团队确认接收", style='body', color=TEAL)
    f.line([(137, 1005), (1663, 1005)], LINE, 2)
    f.text(137, 1056, "可靠的审批与签署状态支持发起交接，接收确认后进入实际履约。", style='body', color=MUTED)
    f.footer("对外发送、预约、谈判、承诺与签署按企业授权办理，生成材料和提醒不代替授权。")
    return f.save()


def build():
    metadata = [goal_1(), goal_2(), goal_3(), goal_4(), goal_5(), goal_6()]
    (OUT / "goals-manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    thumb_w, gap, cols = 900, 20, 2
    thumb_h = max(round(thumb_w * f["dimensions"][1] / f["dimensions"][0]) for f in metadata)
    rows = (len(metadata) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap,
                              rows * thumb_h + (rows + 1) * gap), "#E7EDF8")
    for i, item in enumerate(metadata):
        with Image.open(OUT / f"{item['slug']}.png") as source:
            thumb = ImageOps.contain(source, (thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = gap + (i % cols) * (thumb_w + gap)
        y = gap + (i // cols) * (thumb_h + gap)
        sheet.paste(thumb, (x + (thumb_w - thumb.width) // 2, y))
    sheet.save(OUT / "goals-overview.png", optimize=True)
    print(json.dumps({"figures": [f["slug"] for f in metadata], "overview": str(OUT / "goals-overview.png")}, ensure_ascii=False))
    return metadata


if __name__ == "__main__":
    build()
