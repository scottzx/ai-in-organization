"""把 specs.FIGS 插入正文：锚段末尾追加导读句，段后插图片与图注；追加 image-manifest 条目。输出插入记录 JSON。"""
import sys, json, pathlib, collections
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from specs import FIGS
ROOT = pathlib.Path(__file__).resolve().parents[2]
by = collections.defaultdict(list)
for s in FIGS: by[(s['vol'], s['md'])].append(s)
rec = []
for (vol, md), specs in by.items():
    p = ROOT / vol / md; L = p.read_text('utf-8').split('\n')
    hits = []
    for s in specs:
        idx = [i for i, l in enumerate(L) if s['anchor'] in l and not l.startswith('![')]
        assert len(idx) == 1, (s['id'], idx)
        hits.append((idx[0], s))
    for i, s in sorted(hits, key=lambda t: -t[0]):
        orig = L[i]; guide = f"见{{{{fig:{s['title']}}}}}。"
        assert '。' not in s['title']
        L[i] = orig + guide
        L[i+1:i+1] = ['', f"![{s['title']}](assets/{s['file']})", '', f"{s['title']}。{s['note']}"]
        s['_orig'] = orig; s['_line0'] = i + 1
    p.write_text('\n'.join(L), 'utf-8')
    for _, s in hits:  # 插入后的最终行号
        L2 = L; g = [k for k, l in enumerate(L2) if f"](assets/{s['file']})" in l][0]
        rec.append(dict(id=s['id'], file=f"{vol}/assets/{s['file']}", md=f"{vol}/{md}", orig_line=s['_line0'],
                        guide_line=g - 1, img_line=g + 1, title=s['title'], note=s['note'], orig=s['_orig']))
mf = ROOT / 'scripts/docx/image-manifest.yaml'
t = mf.read_text('utf-8').rstrip('\n') + '\n'
for s in FIGS:
    t += (f"- file: {s['file']}\n  chapters: {pathlib.Path(s['md']).stem}\n  action: keep\n  advice: 本书新绘（rev/figures）\n"
          f"  source: 本书绘制\n  url: null\n  not_cc: false\n  redraw_file: null\n  note: {json.dumps(s['note'], ensure_ascii=False)}\n  manual_review: null\n")
mf.write_text(t, 'utf-8')
json.dump(rec, open('/workspace/figures/insert-record.json', 'w'), ensure_ascii=False, indent=1)
print(len(rec))
