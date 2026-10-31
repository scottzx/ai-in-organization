"""中册 9 幅"重绘"示意图（redraw-*.png）。按全书配图规范经 figlib 绘制：
成图宽 14.504cm、300dpi（1713px），图内文字不小于 9pt，黑白灰加强调色 #1F6F8B，Noto Sans CJK SC，图题不入图。
用法：python3 scripts/redraw-middle-figures.py（结尾打印"无残留溢出"才算通过）。"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'figures'))
import figlib
from figlib import Fig, FILL2, ACCENT, LW
OUT = os.path.join(HERE, '..', '中册-行业解决方案', 'assets') + '/'


def done(f, name):
    f.fit(name); f.save(OUT + name); print(name)


def layers(name, rows, side=None):
    """rows 自上而下 (层名, [条目])；side=(标题, [条目]) 为右侧贯穿栏。"""
    n = len(rows); rh, g, m = 1.3, 0.45, 0.1
    h = 0.2 + n * rh + (n - 1) * g + 0.2
    f = Fig(h)
    right = (LW - m - 3.0 - 0.3) if side else (LW - m)
    lab_w = 3.0; x0 = m + lab_w + 0.2; avail = right - x0
    for i, (lab, items) in enumerate(rows):
        y = h - 0.2 - rh - i * (rh + g)
        f.box(m, y, lab_w, rh, lab, fill=FILL2, bold=True, fs=10)
        k = len(items); w = (avail - 0.2 * (k - 1)) / k
        for j, it in enumerate(items):
            f.box(x0 + j * (w + 0.2), y + 0.08, w, rh - 0.16, it, fs=10)
        if i < n - 1:
            xa = x0 + avail / 2
            f.arrow((xa, y - g + 0.06), (xa, y - 0.06))
    if side:
        lab, items = side; sx = LW - m - 3.0; top = h - 0.2; bot = 0.2
        f.box(sx, bot, 3.0, top - bot, '', accent=True)
        f.text(sx + 1.5, top - 0.4, lab, color=ACCENT, bold=True, fs=10)
        k = len(items); ih = 0.62; gap = (top - bot - 0.8 - k * ih) / (k + 1)
        for j, it in enumerate(items):
            f.box(sx + 0.25, top - 0.8 - (j + 1) * gap - (j + 1) * ih, 2.5, ih, it, accent=True, fill='white', fs=9.5)
    done(f, name)


layers("redraw-数字金融体系示意.png", [("服务", ["渠道与客户服务", "业务流程", "运营支持"]), ("能力", ["数据治理", "专业模型与业务规则", "研发运维"]), ("数字基础", ["网络与存储", "数据库", "身份与接口"])], side=("治理", ["安全", "合规", "风险管理", "数据生命周期"]))
layers("redraw-智慧农业三层框架示意.png", [("应用层", ["生产管理", "产销与流通", "溯源与社会化服务"]), ("运算层", ["数据", "农业知识", "算法与专业模型"]), ("感知与执行层", ["环境与遥感感知", "农机与执行器", "市场信息"])])
layers("redraw-数字乡村框架示意.png", [("建设领域", ["智慧农业", "乡村产业", "乡村治理", "公共服务"]), ("两大基础", ["数字基础设施", "数据资源"])])
layers("redraw-智能云服务分层示意.png", [("AISaaS", ["面向具体应用"]), ("MaaS", ["模型能力服务化"]), ("AIPaaS", ["数据", "模型开发", "部署流程"]), ("AIIaaS", ["算力", "网络", "存储"])])
layers("redraw-实时互动技术构成示意.png", [("共生技术", ["终端呈现", "课件与白板", "交互操作"]), ("专业组件", ["音视频处理", "信令", "数据处理"]), ("专有基础设施", ["实时网络", "边缘计算"])])
layers("redraw-数字政府一体化框架示意.png", [("驱动与牵引", ["体制机制驱动", "履职场景牵引"]), ("业务应用", ["一网通办", "一网统管", "一网协同"]), ("两大支撑", ["政务数据", "政务平台"])], side=("两大保障", ["运维运营", "安全防护"]))

# 电信变革路径
f = Fig(5.0)
f.text(5.4, 4.6, "现状", fs=10, bold=True); f.text(12.3, 4.6, "智能化方向", fs=10, bold=True, color=ACCENT)
for i, (lab, a, b) in enumerate([("基础设施", "网络与资源", "自感知、自调度"), ("技术", "平台与运维", "数据与模型驱动"), ("服务", "客户服务", "按需、主动服务")]):
    y = 3.2 - i * 1.4
    f.box(0.1, y, 2.6, 1.0, lab, fill=FILL2, bold=True, fs=10)
    f.box(3.2, y, 4.4, 1.0, a, fs=10)
    f.box(9.6, y, 5.3, 1.0, b, fs=10, accent=True)
    f.arrow((7.6, y + 0.5), (9.6, y + 0.5), accent=True)
done(f, "redraw-电信业智能化路径示意.png")

# 餐饮产业链
f = Fig(4.6)
for j, (t, s) in enumerate([("数字供应", "采购·运输·库存"), ("数字加工", "备餐·供餐"), ("数字销售", "堂食·外卖·其他渠道")]):
    f.box(0.1 + j * 5.1, 2.4, 4.2, 1.9, t + "\n" + s, fs=10, wrapw=False)
    if j < 2: f.arrow((4.3 + j * 5.1, 3.35), (5.2 + j * 5.1, 3.35))
f.box(0.1, 0.2, 14.4, 1.1, "数字管理：人员、财务、设备、食材", fill=FILL2, fs=10, accent=False)
for j in range(3): f.arrow((2.2 + j * 5.1, 1.3), (2.2 + j * 5.1, 2.4), accent=True)
done(f, "redraw-餐饮产业链示意.png")

# 餐饮矩阵
rows = [("数字供应", "采购、运输、库存", "供应商与食材记录"), ("数字加工", "备餐、供餐", "工序与出品记录"), ("数字管理", "人、财、设备、食材", "经营与资源记录"), ("数字销售", "堂食、外卖、其他渠道", "订单与顾客记录")]
f = Fig(6.0); cw = (LW - 0.2 - 0.3) / 3
for j, hd in enumerate(["环节", "主要对象", "数字化内容"]): f.box(0.1 + j * (cw + 0.15), 4.9, cw, 0.9, hd, fill=FILL2, bold=True, fs=10)
for i, r in enumerate(rows):
    for j, c in enumerate(r): f.box(0.1 + j * (cw + 0.15), 3.8 - i * 1.15, cw, 0.95, c, fs=10, fill=None if j == 0 else 'white')
done(f, "redraw-餐饮数字化环节矩阵示意.png")

print('\n'.join(figlib.ISSUES) or '无残留溢出')
