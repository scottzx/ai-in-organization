#!/usr/bin/env python3
"""分册交付包（Scott 2026-11-01）：上、中、下三册 docx + 一页「索引说明」docx，打成一个 zip。

用法：
  python3 package_volumes.py --build -o 输出目录      # 逐册（一次一册）调用 build_docx.py 导出后打包
  python3 package_volumes.py -o 输出目录              # 输出目录里已有三册 docx 时只出索引说明并打包
页数一律由 LibreOffice 渲染 PDF 后 pdfinfo 实测；章节范围、附录从成品 docx 的一级标题读出，不手填。"""
import argparse, re, subprocess, sys, tempfile, zipfile
from pathlib import Path
import yaml
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_docx import Builder
from docx import Document
VN = {'upper': '上册', 'middle': '中册', 'lower': '下册'}
CHAP = re.compile(r'^第([一二三四五六七八九十]+)章')

def name(cfg, vol): return f"{cfg['book']['title'].strip('《》')}-{VN[vol]}.docx"

def pdf_pages(docx):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, str(docx)], capture_output=True, timeout=900)
        pdf = Path(tmp) / (Path(docx).stem + '.pdf')
        if not pdf.exists(): sys.exit(f'LibreOffice 未能渲染 {docx}')
        return int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout).group(1))

def outline(docx):
    h1 = [p.text.strip() for p in Document(docx).paragraphs if p.style.name == 'Heading 1' and p.text.strip()]
    chaps = [t for t in h1 if CHAP.match(t)]
    apps = [t for t in h1 if t.startswith('附录')]
    other = [t.split('\u3000')[0] for t in h1 if t not in chaps and t not in apps]
    # 顺序核对：目录（前置）→ 正文 → 附录，附录之后不得再有正文一级标题
    last_app = max((i for i, t in enumerate(h1) if t.startswith('附录')), default=-1)
    first_app = min((i for i, t in enumerate(h1) if t.startswith('附录')), default=len(h1))
    if last_app >= 0 and any(not t.startswith('附录') for t in h1[first_app:]):
        sys.exit(f'{Path(docx).name}：附录之后还有正文一级标题，未按“目录→正文→附录”排')
    return chaps, apps, other

def chap_range(chaps):
    if not chaps: return '—'
    a, b = CHAP.match(chaps[0]).group(1), CHAP.match(chaps[-1]).group(1)
    return f'第{a}章至第{b}章（{len(chaps)} 章）'

def index_doc(cfg, repo, rows, out):
    b = Builder(cfg, repo); b.cur_file = '索引说明'; b.fn_defs = {}
    b.first_chapter = True
    b.heading_raw(1, '索引说明')
    b.para('Normal', f"{cfg['book']['title']}分为上、中、下三册，各册单独成书，均按目录、正文、附录的顺序编排，页码各自从正文第 1 页起编。各册内容如下。")
    for r in rows:
        p = b.para('Normal'); b.inline(p, f"{VN[r['vol']]}（{r['file']}）", 'body', bold=True, allow_fn=False)
        b.para('Normal', f"内容：{r['summary']}")
        b.para('Normal', f"页数：共 {r['pages']} 页（含封面、版权页和目录）。")
        b.para('Normal', f"章节范围：{r['range']}" + (f"；另有{'、'.join(r['other'])}" if r['other'] else '') + '。')
        b.para('Normal', '附录：' + ('；'.join(r['apps']) if r['apps'] else '无') + '。')
    b.save(out)
    import fonts_embed, package_clean
    fonts_embed.embed(out, cfg); package_clean.clean(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('-o', required=True, help='输出目录')
    ap.add_argument('--build', action='store_true', help='先逐册导出三册（一次一册）')
    ap.add_argument('--repo', default=str(HERE.parents[1]))
    a = ap.parse_args(); out = Path(a.o); out.mkdir(parents=True, exist_ok=True); repo = Path(a.repo)
    cfg = yaml.safe_load((HERE / 'style.yaml').read_text('utf-8')); D = cfg['delivery']
    rows = []
    for vol in D['volumes']:
        f = out / name(cfg, vol)
        if a.build:
            r = subprocess.run([sys.executable, str(HERE / 'build_docx.py'), '--volume', vol, '-o', str(f)])
            if r.returncode: sys.exit(f'{VN[vol]}导出失败（退出码 {r.returncode}）')
        if not f.exists(): sys.exit(f'缺少 {f}')
        chaps, apps, other = outline(f)
        rows.append({'vol': vol, 'file': f.name, 'summary': D['summaries'][vol], 'pages': pdf_pages(f),
                     'range': chap_range(chaps), 'apps': apps, 'other': other})
        print(f"{VN[vol]}：{rows[-1]['pages']} 页；{rows[-1]['range']}；附录 {len(apps)} 个")
    idx = out / D['index_name']; index_doc(cfg, repo, rows, idx)
    n = pdf_pages(idx)
    if n != 1: sys.exit(f'索引说明渲染为 {n} 页，应为 1 页')
    z = out / D['zip_name']
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for r in rows: zf.write(out / r['file'], r['file'])
        zf.write(idx, idx.name)
    print(f'索引说明 1 页；已打包 {z}（{len(rows) + 1} 个文件）')

if __name__ == '__main__': main()
