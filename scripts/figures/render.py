"""渲染全部配图到各册 assets/。用法：python3 scripts/figures/render.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from specs import FIGS
ROOT = pathlib.Path(__file__).resolve().parents[2]
for s in FIGS:
    out = ROOT / s['vol'] / 'assets' / s['file']; out.parent.mkdir(exist_ok=True)
    f = s['draw']()
    if hasattr(f, 'save'): f.save(out)
    else: f.savefig(out, dpi=300, facecolor='white'); __import__('matplotlib.pyplot').pyplot.close(f)
    print(s['id'], out.relative_to(ROOT))
