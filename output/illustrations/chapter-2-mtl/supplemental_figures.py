"""Editable supplemental diagrams for chapter two's MTL workflow."""

import json

from drawing import Figure, INK, TEAL, MUTED, LINE, PALE, LIGHT



def costs():
    f = Figure("12-qualified-delivery-cost", "合格交付成本按完整投入比较", "前后比较固定交付范围、质量和合格数量，分别计入资料准备、建设、调用、核验、返工及配套投入。数量变化时比较单位合格交付成本。")
    f.header(12, "前后对照固定交付范围、质量与合格数量，数量变化时比较单位成本。", "成本与效果")
    for x, label in [(104, "原有做法"), (953, "改进做法")]:
        f.rect(x, 330, 743, 194, PALE, radius=10)
        f.text(x + 35, 396, label, style='heading')
        f.text(x + 35, 452, "计入完成同等交付的全部投入。", style='body', color=MUTED)
        f.text(x + 35, 495, "保留采用情况与实际交付记录。", style='body', color=MUTED)
    f.line([(475, 541), (475, 572), (1325, 572), (1325, 541)], LINE, 2)
    f.text(900, 631, "前后两侧均纳入适用投入", style='subheading', anchor="middle")
    labels = ["资料准备与维护", "必要建设与配套", "工具调用与运行", "人工核验与校准", "退回修改与返工", "协调与异常处置"]
    for i, label in enumerate(labels):
        row, col = divmod(i, 3)
        x, y = 104 + col * 556, 682 + row * 111
        f.rect(x, y, 480, 83, LIGHT, radius=8)
        f.text(x + 240, y + 54, label, style='subheading', anchor="middle")
    f.text(104, 1048, "单位合格交付成本", style='heading')
    f.text(439, 1048, "=", style='subheading', color=TEAL)
    f.text(1098, 1008, "前后各自的总投入", style='subheading', anchor="middle")
    f.line([(588, 1030), (1608, 1030)], INK, 2)
    f.text(1098, 1077, "对应的合格交付数量", style='subheading', anchor="middle")
    f.footer("节时、响应改善与经营结果分别记录。单次生成价格不能代表完整交付成本。")
    return f.save()



def role_card(f, x, y, title, rows):
    f.rect(x, y, 766, 380, LIGHT, radius=12)
    f.rect(x, y, 5, 380, TEAL)
    f.text(x + 32, y + 58, title, style='heading')
    f.line([(x + 32, y + 85), (x + 734, y + 85)], LINE, 2)
    for i, (label, lines) in enumerate(rows):
        baseline = y + 130 + 84 * i
        f.text(x + 32, baseline, label, style='label', color=TEAL)
        for j, line in enumerate(lines):
            f.text(x + 178, baseline + 36 * j, line, style='dense_body')



def capability_reuse():
    f = Figure(
        "13-capability-reuse",
        "个人工作方法经复用验证形成组织能力",
        "依据2.4线索交接准备的说明性例子，展示资深市场人员与智能体完成线索交接的客户简报，保留查找核实、退回与修改依据，整理为Skill、工具或任务示例，由其他市场人员提供新客户资料复用，经过检验后纳入日常使用并持续维护。三种载体按任务需要组合。",
    )
    f.header(13, "资深市场人员的客户简报经验经过提炼、他人复用和验证，形成团队可以调用的方法。", section="能力沉淀")

    steps = [
        ("完成真实任务", "资深市场人员与AI协作", ["准备线索交接简报", "修改简报直到可用"]),
        ("保留判断过程", "关键判断关联具体产物", ["查找与核实依据", "退回理由与修改示例"]),
        ("提炼复用方法", "区分共性与本次条件", ["明确输入与处理步骤", "保留判断和验收要求"]),
        ("他人复用验证", "其他市场人员复用", ["提供本次客户资料", "调用方法并核对结果"]),
        ("进入组织日常", "维护人根据反馈修订", ["记录仍需请教的问题", "经验证的方法持续使用"]),
    ]
    for i, (title, sub, lines) in enumerate(steps):
        x = 104 + 325 * i
        f.rect(x, 311, 292, 307, LIGHT, radius=10)
        f.text(x + 22, 365, f"0{i + 1}", style='step', color=TEAL)
        f.text(x + 22, 423, title, style='subheading')
        f.text(x + 22, 468, sub, style='label', color=TEAL)
        f.line([(x + 22, 493), (x + 270, 493)], LINE, 2)
        for j, line in enumerate(lines):
            f.text(x + 16, 542 + 44 * j, line, style='dense_body', color=MUTED)
        if i < 4:
            f.arrow([(x + 300, 464), (x + 317, 464)], TEAL, 2, 8)

    f.arrow([(1550, 618), (1550, 653), (900, 653), (900, 618)], TEAL, 2, 9)
    f.text(1100, 645, "反馈用于修订方法", style='label', color=TEAL)

    f.text(104, 683, "客户简报经验按复用需要整理为三种载体", style='heading')
    f.text(104, 723, "三种形式可以组合使用，分别保留任务方法、稳定操作和完整处理过程。", style='dense_body', color=MUTED)
    carriers = [
        ("Skill：查找与核实方法", ["适用任务、资料输入和简报步骤", "信息核实与交付检查要求"]),
        ("工具：稳定查询与操作", ["按任务需要封装查询或校验", "使用者提供本次客户与资料"]),
        ("任务示例：对话与修改过程", ["保存必要背景、对话和修改依据", "关联最终可用的客户简报"]),
    ]
    for i, (title, lines) in enumerate(carriers):
        x = 104 + 538 * i
        f.rect(x, 756, 516, 210, PALE, radius=10)
        f.text(x + 23, 807, title, style='subheading', color=TEAL)
        f.line([(x + 23, 830), (x + 493, 830)], LINE, 2)
        for j, line in enumerate(lines):
            f.text(x + 23, 882 + 45 * j, line, style='dense_body', color=MUTED)

    f.rect(104, 1002, 1592, 102, LIGHT, radius=10)
    f.text(132, 1044, "业务负责人确认适用范围、资料与工具条件、产物标准及人工判断事项。", style='subheading')
    f.text(132, 1081, "维护人记录使用反馈、修订方法并维护版本，让后续任务继续使用有效做法。", style='dense_body', color=MUTED)
    f.footer("示意依据本节线索交接准备例子整理；以其他人在新任务中形成的合格产物检验复用成效。")
    return f.save()



def other_roles_a():
    f = Figure(
        "14-other-roles-a",
        "技术辅助围绕岗位业务目标展开",
        "电商、客服、市场和法务分别从业务目标出发确定辅助任务，人员核实依据、完成专业判断并承担交付责任。",
    )
    f.header(14, "先确定业务目标，再明确技术辅助范围与人的责任。", section="其他岗位")
    cards = [
        ("电商运营与设计创意", [
            ("业务目标", ["合格素材及时上架，实物投入", "用于更值得经营的款式。"]),
            ("技术辅助", ["生成款式展示、商品图与视频；", "店铺工具处理已有规则的操作。"]),
            ("人的责任", ["核对商品细节与实物，决定生产；", "审核返工并确认素材可以上架。"]),
        ]),
        ("客服与私域社群", [
            ("业务目标", ["客户问题及时解决，需要继续", "跟进的人得到合适回应。"]),
            ("技术辅助", ["常见问答有明确依据时辅助接待，", "整理对话与待跟进事项。"]),
            ("人的责任", ["维护政策与知识，承接升级问题，", "处理复杂投诉、授权与例外承诺。"]),
        ]),
        ("市场与自媒体内容", [
            ("业务目标", ["内容服务明确受众与业务目的，", "减少无效制作和投放。"]),
            ("技术辅助", ["整理资料、选题和脚本初稿，", "工具辅助剪辑与投放操作。"]),
            ("人的责任", ["判断证据、审美与可拍性，", "决定创意、预算并验收交付。"]),
        ]),
        ("法务与专业服务", [
            ("业务目标", ["及时交付有依据、可复核的", "专业成果。"]),
            ("技术辅助", ["整理材料、检索依据与起草，", "计算和出图使用专业工具。"]),
            ("人的责任", ["补齐事实、核实依据及适用性，", "完成专业判断与对外交付。"]),
        ]),
    ]
    for i, (title, rows) in enumerate(cards):
        role_card(f, 104 if i % 2 == 0 else 930, 307 if i < 2 else 724, title, rows)
    f.footer("技术辅助需要可信资料、明确标准与人工承接。各岗位的采用范围仍需用真实任务验证。")
    return f.save()



def other_roles_b():
    f = Figure(
        "15-other-roles-b",
        "任务条件决定技术辅助的具体范围",
        "采购、研发、HR和经营分别确定资料、规则、环境与责任，技术辅助需要通过真实任务验证，业务结果由负责人持续检验。",
    )
    f.header(15, "资料、规则和系统条件进入任务设计，专业判断与结果责任落实到人。", section="其他岗位")
    cards = [
        ("采购、仓储与供应链", [
            ("业务目标", ["减少错买、重复采购、缺货", "和单据等待。"]),
            ("技术辅助", ["从单据或照片提取、查找信息，", "程序按确定公式计算补货。"]),
            ("人的责任", ["核实库存、字段与实际需求，", "决定采购并处理收货和结算异常。"]),
        ]),
        ("产品、研发与数据分析", [
            ("业务目标", ["更快交付可用功能或可信分析，", "接通测试、发布和后续维护。"]),
            ("技术辅助", ["辅助文档、编码、测试准备与取数，", "以可用需求、数据和环境为前提。"]),
            ("人的责任", ["审查实现与口径，验证缺陷，", "承担发布维护和结果解释。"]),
        ]),
        ("HR与培训", [
            ("业务目标", ["提高人岗匹配与上岗胜任，", "将知识、练习、反馈与考核接通。"]),
            ("技术辅助", ["整理访谈与岗位知识，", "辅助答疑、陪练与学习反馈。"]),
            ("人的责任", ["核实知识和评分尺度，", "决定录用、上岗资格并持续纠错。"]),
        ]),
        ("老板与经营", [
            ("业务目标", ["及早识别经营问题，", "让决定落实为有效行动。"]),
            ("技术辅助", ["汇集资料、追问缺项、提示异常，", "系统保存来源、任务和处理状态。"]),
            ("人的责任", ["统一经营口径，判断原因和取舍，", "协调资源、承担承诺并复盘结果。"]),
        ]),
    ]
    for i, (title, rows) in enumerate(cards):
        role_card(f, 104 if i % 2 == 0 else 930, 307 if i < 2 else 724, title, rows)
    f.footer("辅助范围由任务、资料与权限条件决定。技术产出仍需被采用，并接受业务结果检验。")
    return f.save()



def build():
    return [costs(), capability_reuse(), other_roles_a(), other_roles_b()]


if __name__ == "__main__":
    results = build()
    print(json.dumps({"figures": [r["slug"] for r in results], "all_text_declarative": True}, ensure_ascii=False))
