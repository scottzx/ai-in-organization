"""Task allocation and complete-input cost figures for chapter two."""
from drawing import *


def allocation():
    f = Figure("05-task-allocation", "业务举措落实为可分工与可验收的任务", "业务目标经具体举措落实为任务；人、AI与程序按能力、业务要求和权限分别承担工作，验收与结果责任由人落实。")
    f.header(5, "先明确业务做法，再安排人、AI与程序承担具体工作。", "业务举措")
    top = [
        ("明确业务目标", "改善线索、转化或交付表现。"),
        ("展开业务举措", "明确业务上应完成的具体工作。"),
        ("写清任务约定", "落实输入、产物、执行与验收。"),
    ]
    for i, (title, body) in enumerate(top):
        x = 104 + i * 556
        f.rect(x, 338, 480, 150, PALE, radius=10)
        f.text(x + 28, 398, title, style='heading')
        f.text(x + 28, 450, body, style='body', color=MUTED)
        if i < 2:
            f.arrow([(x + 498, 411), (x + 537, 411)], TEAL, 2)
    f.arrow([(900, 506), (900, 559)], TEAL, 2)
    roles = [
        ("人承担判断与责任", ["确定目标与判断标准。", "核实事实与业务承诺。", "验收产物并处理异常。"]),
        ("AI辅助开放性处理", ["检索与整理有效资料。", "起草方案与任务草稿。", "提示缺项与前后矛盾。"]),
        ("程序执行明确规则", ["按固定规则计算与比对。", "保存字段、版本与状态。", "落实授权内的登记与提醒。"]),
    ]
    for i, (title, lines) in enumerate(roles):
        x = 104 + i * 556
        f.line([(x, 610), (x + 480, 610)], TEAL, 3)
        f.text(x, 678, title, style='heading')
        for j, line in enumerate(lines):
            f.text(x, 760 + j * 66, line, style='body', color=MUTED)
    f.rect(104, 997, 1592, 92, LIGHT, radius=10)
    f.text(900, 1055, "资料、权限与验收条件支撑任务分工，结果责任由相应负责人承担。", style='body', anchor="middle")
    f.footer("分工需结合真实任务与当前可用能力验证，并按企业授权安排执行。")
    return f.save()


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


def build():
    return [allocation(), costs()]


if __name__ == "__main__":
    build()
