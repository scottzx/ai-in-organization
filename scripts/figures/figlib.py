"""配图绘制库：黑白灰 + 强调色深青 #1F6F8B；坐标单位为厘米，版心宽 15cm，300dpi。"""
import math, textwrap
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager

FONT = 'Noto Sans CJK SC'
ACCENT = '#1F6F8B'
INK = '#262626'      # 文字与线条
EDGE = '#595959'     # 普通框线
FILL = '#F2F2F2'     # 普通框底
FILL2 = '#E0E0E0'    # 分层/底栏
ACC_FILL = '#E6F0F3' # 强调框底（灰阶下与 FILL 可区分靠线宽/线色）
FS = 9               # 正文标签 pt
W = 15.0             # 版心宽 cm
DPI = 300
CM_PER_PT = 2.54 / 72

plt.rcParams['font.family'] = FONT
plt.rcParams['axes.unicode_minus'] = False


ISSUES = []          # 渲染后仍溢出的文字，由 render.py 汇总
MIN_FS = 7.0         # 自动缩字号下限 pt
PAD = 0.08           # 文字距框边最小留白 cm


def max_chars(width_cm, fs=FS):
    """框内一行可容纳的最大字数（中文按全角字宽≈字号计，留 8% 余量）。"""
    return max(2, int(width_cm / (fs * CM_PER_PT * 1.08)))


try:
    import jieba; jieba.setLogLevel(60)
    for w in ('派车', '差异', '委托', '智力服务', '维保', '一张图', '台账', '工单', '回款', '复核', '业主单位', '立体库', '消防救援机构'): jieba.add_word(w)
    def _tokens(t): return list(jieba.cut(t))
except ImportError:                       # 无 jieba 时退回逐字
    def _tokens(t): return list(t)
NO_HEAD = '、，。：；）」』”’！？%·／'      # 不能出现在行首的字符
NO_TAIL = '（「『“‘'                       # 不能出现在行尾的字符


def wrap(text, width_cm, fs=FS):
    """按框宽折行：按词断（jieba），各行尽量等长，保留手工 \n；单词超过一行时才逐字拆。"""
    n = max_chars(width_cm, fs)
    out = []
    for part in text.split('\n'):
        if len(part) <= n: out.append(part); continue
        toks = []
        for t in _tokens(part):
            if toks and (t[0] in NO_HEAD or toks[-1][-1] in NO_TAIL): toks[-1] += t
            elif len(t) > n: toks += list(t)
            else: toks.append(t)
        k = math.ceil(len(part) / n)
        while True:
            L = math.ceil(len(part) / k); lines = ['']
            for t in toks:
                cur = lines[-1]
                if cur and (len(cur) + len(t) > n or (len(cur) >= L and len(lines) < k)): lines.append(t)
                else: lines[-1] = cur + t
            if all(len(x) <= n for x in lines) or k > len(part): break
            k += 1
        out += lines
    return '\n'.join(out)


class Fig:
    def __init__(self, h):
        self.h = h
        self.fig = plt.figure(figsize=(W / 2.54, h / 2.54), dpi=DPI)
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, W); self.ax.set_ylim(0, h); self.ax.axis('off')
        self.boxed = []

    def _ext(self, a, r):
        """文字外框（cm 坐标）。"""
        bb = a.get_window_extent(r).transformed(self.ax.transData.inverted())
        return bb.x0, bb.y0, bb.x1, bb.y1

    def fit(self, name=''):
        """碰撞检测：框内文字超出框（留 PAD）则重新折行并逐级缩字号；仍超出或越出画布则记入 ISSUES。"""
        r = self.fig.canvas.get_renderer()
        for a, (x, y, w, h), text, wrapw in self.boxed:
            def bad():
                x0, y0, x1, y1 = self._ext(a, r)
                return x0 < x + PAD or x1 > x + w - PAD or y0 < y + PAD or y1 > y + h - PAD
            fs = a.get_fontsize()
            while bad() and fs > MIN_FS:
                fs = max(MIN_FS, fs - 0.5); a.set_fontsize(fs)
                if wrapw: a.set_text(wrap(text, w - 0.25, fs))
            if bad(): ISSUES.append(f'{name}: 框内文字放不下（已缩到 {fs}pt）：{text}')
        for a in self.ax.texts:
            x0, y0, x1, y1 = self._ext(a, r)
            if x0 < 0 or y0 < 0 or x1 > W or y1 > self.h:
                ISSUES.append(f'{name}: 文字越出画布：{a.get_text()!r}')

    def box(self, x, y, w, h, text, accent=False, fill=None, fs=FS, bold=False, wrapw=True, align='center'):
        """(x, y) 为左下角。"""
        p = FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0,rounding_size=0.15',
                           lw=1.0 if accent else 0.75, ec=ACCENT if accent else EDGE,
                           fc=fill or (ACC_FILL if accent else FILL), zorder=2)
        self.ax.add_patch(p)
        t = wrap(text, w - 0.25, fs) if wrapw else text
        a = self.ax.text(x + w / 2 if align == 'center' else x + 0.15, y + h / 2, t, ha=align, va='center',
                     fontsize=fs, color=ACCENT if accent else INK, linespacing=1.3,
                     fontweight='bold' if bold else 'normal', zorder=3)
        if text: self.boxed.append((a, (x, y, w, h), text, wrapw))
        return (x, y, w, h)

    def text(self, x, y, s, fs=FS, color=INK, ha='center', va='center', bold=False, **kw):
        self.ax.text(x, y, s, fontsize=fs, color=color, ha=ha, va=va, linespacing=1.3,
                     fontweight='bold' if bold else 'normal', zorder=4, **kw)

    def arrow(self, a, b, accent=False, style='-|>', rad=0.0, dashed=False, lw=None):
        ar = FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=9, lw=lw or (1.0 if accent else 0.75),
                             color=ACCENT if accent else INK, connectionstyle=f'arc3,rad={rad}',
                             linestyle='--' if dashed else '-', zorder=1, shrinkA=0, shrinkB=0)
        self.ax.add_patch(ar)

    def line(self, xs, ys, accent=False, dashed=False):
        self.ax.plot(xs, ys, color=ACCENT if accent else INK, lw=1.0 if accent else 0.75,
                     ls='--' if dashed else '-', zorder=1)

    def save(self, path):
        self.fig.savefig(path, dpi=DPI, facecolor='white')
        plt.close(self.fig)


# ---------- 版式 ----------

def chain(steps, notes=None, feedback=None, base=None, accent_steps=(), box_h=1.5, legend=None):
    """横向流程。notes: {步骤序号: 智力服务介入点文字}（强调色，放在框下）；
    feedback: 回路文字（末步回到首步，或 (i, j, text)）；base: 底栏文字（贯穿全链）。"""
    n = len(steps); gap = 0.45; m = 0.15
    bw = (W - 2 * m - gap * (n - 1)) / n
    h = 0.4 + box_h + (1.5 if notes else 0) + (0.9 if base else 0) + (1.0 if feedback else 0) + (0.5 if legend else 0)
    f = Fig(h)
    y = h - 0.3 - box_h - (1.0 if feedback else 0)
    xs = []
    for i, s in enumerate(steps):
        x = m + i * (bw + gap); xs.append(x)
        f.box(x, y, bw, box_h, s, accent=i in accent_steps)
        if i: f.arrow((x - gap, y + box_h / 2), (x, y + box_h / 2))
    if feedback:
        i, j, t = feedback if isinstance(feedback, tuple) else (n - 1, 0, feedback)
        x1, x2 = xs[i] + bw / 2, xs[j] + bw / 2; yt = y + box_h + 0.55
        f.line([x1, x1, x2], [y + box_h, yt, yt]); f.arrow((x2, yt), (x2, y + box_h))
        f.text((x1 + x2) / 2, yt + 0.22, t, fs=8)
    yy = y
    if notes:
        for i, t in notes.items():
            x = xs[i]; f.arrow((x + bw / 2, y - 0.55), (x + bw / 2, y), accent=True, style='-|>')
            f.box(x - 0.1, y - 1.4, bw + 0.2, 0.85, t, accent=True, fs=8, fill='white')
        yy = y - 1.5
    if base:
        f.box(m, yy - 0.85, W - 2 * m, 0.6, base, fill=FILL2, wrapw=False, fs=8.5)
        yy -= 0.9
    if legend:
        f.text(W - m, 0.25, legend, fs=7.5, color=ACCENT, ha='right')
    return f


def layers(rows, side_title, side_items, top_label=None, bottom_label=None):
    """分层架构：rows 自下而上；右侧强调色竖栏为智力服务。"""
    rh, g = 0.75, 0.18; n = len(rows)
    h = 0.5 + n * rh + (n - 1) * g + (0.6 if top_label else 0) + (0.6 if bottom_label else 0)
    f = Fig(h); lw = 10.3; m = 0.15
    y0 = 0.25 + (0.6 if bottom_label else 0)
    for i, r in enumerate(rows):
        y = y0 + i * (rh + g)
        if isinstance(r, tuple):
            f.box(m, y, 2.6, rh, r[0], fill=FILL2, fs=8.5, bold=True)
            f.box(m + 2.75, y, lw - 2.75, rh, r[1], fs=8.5)
        else:
            f.box(m, y, lw, rh, r)
    top = y0 + n * rh + (n - 1) * g
    sx = m + lw + 0.5; sw = W - m - sx
    f.box(sx, y0, sw, top - y0, '', accent=True)
    f.text(sx + sw / 2, top - 0.4, side_title, color=ACCENT, bold=True)
    k = len(side_items); ih = (top - y0 - 0.9 - (k - 1) * 0.2) / k
    for j, t in enumerate(side_items):
        f.box(sx + 0.2, top - 0.8 - (j + 1) * ih - j * 0.2, sw - 0.4, ih, t, accent=True, fill='white', fs=8.5)
    for i in range(n):
        y = y0 + i * (rh + g) + rh / 2
        f.arrow((sx, y), (m + lw, y), accent=True, style='<|-|>', dashed=True, lw=0.75)
    if top_label: f.text(m + lw / 2, top + 0.3, top_label, fs=8.5)
    if bottom_label: f.text(m + lw / 2, 0.45, bottom_label, fs=8.5)
    return f


def compare(lt, lsteps, rt, rsteps, lfoot=None, rfoot=None, accent_right=True):
    n = max(len(lsteps), len(rsteps)); bh, g = 0.95, 0.45
    h = 1.0 + n * bh + (n - 1) * g + (0.9 if (lfoot or rfoot) else 0) + 0.2
    f = Fig(h); cw = 6.6
    for c, (t, st, foot, acc) in enumerate([(lt, lsteps, lfoot, False), (rt, rsteps, rfoot, accent_right)]):
        x = 0.4 + c * (cw + 1.4)
        f.text(x + cw / 2, h - 0.4, t, bold=True, color=ACCENT if acc else INK, fs=9.5)
        for i, s in enumerate(st):
            y = h - 1.0 - (i + 1) * bh - i * g
            f.box(x, y, cw, bh, s, accent=acc)
            if i: f.arrow((x + cw / 2, y + bh + g), (x + cw / 2, y + bh), accent=acc)
        if foot:
            f.text(x + cw / 2, 0.5, foot, color=ACCENT if acc else INK, bold=True)
    f.line([W / 2, W / 2], [0.3, h - 0.2], dashed=True)
    return f


def cycle(steps, center=None, r=2.5, bw=3.4, bh=0.95):
    n = len(steps); h = 2 * r + bh + 0.8
    f = Fig(h); cx, cy = W / 2, h / 2
    pts = []
    for i, s in enumerate(steps):
        a = math.pi / 2 - 2 * math.pi * i / n
        x, y = cx + r * 1.55 * math.cos(a), cy + r * math.sin(a); pts.append((x, y))
        f.box(x - bw / 2, y - bh / 2, bw, bh, s, accent=(i == 0))
    for i in range(n):
        (x1, y1), (x2, y2) = pts[i], pts[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1; L = math.hypot(dx, dy)
        # 从框边缘出发
        def edge(px, py, ux, uy):
            tx = (bw / 2) / abs(ux) if ux else 1e9; ty = (bh / 2) / abs(uy) if uy else 1e9
            t = min(tx, ty) + 0.08; return px + ux * t, py + uy * t
        ux, uy = dx / L, dy / L
        f.arrow(edge(x1, y1, ux, uy), edge(x2, y2, -ux, -uy), rad=-0.15)
    if center: f.text(cx, cy, center, color=ACCENT, bold=True, fs=9.5)
    return f


def hbar(labels, values, texts, xlabel, xmax=None, h=5.0, accent_idx=None):
    fig = plt.figure(figsize=(W / 2.54, h / 2.54), dpi=DPI)
    ax = fig.add_axes([0.30, 0.29, 0.62, 0.66])
    ys = list(range(len(labels)))[::-1]
    cols = [ACCENT if (accent_idx is None or i in accent_idx) else '#8C8C8C' for i in range(len(labels))]
    ax.barh(ys, values, color=cols, height=0.55)
    for y, v, t in zip(ys, values, texts):
        ax.text(v + (xmax or max(values)) * 0.015, y, t, va='center', fontsize=8.5, color=INK)
    ax.set_yticks(ys); ax.set_yticklabels(labels, fontsize=9, color=INK)
    ax.set_xlim(0, xmax or max(values) * 1.35); ax.set_xlabel(xlabel, fontsize=8.5, color=INK)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'): ax.spines[s].set_color(EDGE); ax.spines[s].set_linewidth(0.75)
    ax.tick_params(labelsize=8.5, colors=INK, width=0.75)
    return fig


def vbar(labels, values, texts, ylabel, ymax=None, h=6.0, colors=None):
    fig = plt.figure(figsize=(W / 2.54, h / 2.54), dpi=DPI)
    ax = fig.add_axes([0.17, 0.16, 0.78, 0.76])
    xs = range(len(labels))
    ax.bar(xs, values, color=colors or [ACCENT] * len(values), width=0.5)
    for x, v, t in zip(xs, values, texts):
        ax.text(x, v + (ymax or max(values)) * 0.02, t, ha='center', va='bottom', fontsize=9, color=INK)
    ax.set_xticks(list(xs)); ax.set_xticklabels(labels, fontsize=9, color=INK)
    ax.set_ylim(0, ymax or max(values) * 1.2); ax.set_ylabel(ylabel, fontsize=8.5, color=INK)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'): ax.spines[s].set_color(EDGE); ax.spines[s].set_linewidth(0.75)
    ax.tick_params(labelsize=8.5, colors=INK, width=0.75)
    return fig
