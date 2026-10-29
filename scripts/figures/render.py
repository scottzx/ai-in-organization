"""渲染全部配图到各册 assets/。用法：python3 scripts/figures/render.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from specs import FIGS
import figlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
for s in FIGS:
    out = ROOT / s['vol'] / 'assets' / s['file']; out.parent.mkdir(exist_ok=True)
    f = s['draw']()
    if hasattr(f, 'save'): f.fit(s['id']); f.save(out)
    else:
        f.canvas.draw(); rr = f.canvas.get_renderer(); fb = f.bbox
        hidden = set()
        for ax in f.axes:
            for axis, lim in ((ax.xaxis, ax.get_xlim()), (ax.yaxis, ax.get_ylim())):
                for loc, lab in zip(axis.get_ticklocs(), axis.get_ticklabels()):
                    if not (min(lim) - 1e-9 <= loc <= max(lim) + 1e-9): hidden.add(id(lab))
        for t in f.findobj(__import__('matplotlib.text', fromlist=['Text']).Text):
            if not t.get_visible() or not t.get_text() or id(t) in hidden: continue
            e = t.get_window_extent(rr)
            if e.x0 < fb.x0 - 1 or e.y0 < fb.y0 - 1 or e.x1 > fb.x1 + 1 or e.y1 > fb.y1 + 1: figlib.ISSUES.append(f"{s['id']}: 文字越出画布：{t.get_text()!r}")
        f.savefig(out, dpi=300, facecolor='white'); __import__('matplotlib.pyplot').pyplot.close(f)
    print(s['id'], out.relative_to(ROOT))

rep = ROOT.parent / 'figures' / 'overflow-report.txt'
print('\n'.join(figlib.ISSUES) or '无残留溢出')
