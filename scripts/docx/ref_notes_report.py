#!/usr/bin/env python3
"""参考文献条目注文清单与 Word／网页一致性核对（供文字编辑核对注文文字）。

用法：python3 ref_notes_report.py --docx upper=上册.docx middle=中册.docx lower=下册.docx --site ../../_site -o ref-notes-list.md
按 style.yaml 各册篇目顺序，用 scripts/refnotes.py 从源稿列出全部改为条目注文的脚注；再分别从 docx（条目段内五号字）
和网页（span.ref-note）读回注文，逐条比对纯文本。有差异时退出码 1。"""
import argparse, html, re, sys, zipfile
from pathlib import Path
import yaml
sys.path.insert(0, str(Path(__file__).resolve().parent)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import refnotes
from build_docx import volume_items, excluded

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NAMES = {'upper': '上册', 'middle': '中册', 'lower': '下册', 'all': '合订本'}

def norm(t): return re.sub(r'\s+', '', html.unescape(t)).replace('\u3000', '')

def word_notes(docx):
    from lxml import etree
    root = etree.fromstring(zipfile.ZipFile(docx).read('word/document.xml'))
    out = []
    for p in root.iter(W + 'p'):
        txt = ''.join(t.text or '' for t in p.iter(W + 't'))
        if not re.match(r'^\s*(\[\d+\]|［\d+］)', txt): continue
        cur = None
        for r in p.iter(W + 'r'):
            sz = r.find(f'{W}rPr/{W}sz'); t = ''.join(x.text or '' for x in r.iter(W + 't'))
            if sz is None or sz.get(W + 'val') != '21': continue
            if t == '\u3000': cur = []; out.append(cur); continue
            if cur is not None: cur.append(t)
    return [norm(''.join(x)) for x in out]

def web_notes(site, rel):
    stem = Path(rel).stem
    cands = [p for p in Path(site).rglob('*.html') if p.stem == stem and Path(rel).parent.name in p.as_posix()]
    if not cands: return None
    h = cands[0].read_text('utf-8')
    return [norm(re.sub(r'<[^>]+>', '', m)) for m in re.findall(r'<span class="ref-note"[^>]*>(.*?)</span>', h, re.S)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--docx', nargs='+', required=True); ap.add_argument('--site', required=True); ap.add_argument('-o', required=True)
    ap.add_argument('--repo', default=str(Path(__file__).resolve().parents[2]))
    a = ap.parse_args(); repo = Path(a.repo)
    cfg = yaml.safe_load((Path(__file__).parent / 'style.yaml').read_text('utf-8'))
    md = ['# 参考文献条目注文清单（Word／网页共用判定）', '',
          '参考文献条目上的脚注已改为条目后的小一号注文（正文脚注照常保留）。判定见 `scripts/refnotes.py`：'
          '只认整行为“参考文献／参考资料／资料来源”等的标题行下的列表条目（[n]、1.、- 开头），节内说明段落不算；多段注文保留分段。', '',
          '请 @文字编辑 核对“注文”一列文字。“Word”“网页”两列为从成品读回后与源稿逐字（去空白）比对的结果。', '']
    total = diff = 0; summary = []
    for spec in a.docx:
        vol, path = spec.split('=', 1)
        wn = word_notes(path); src_all = []
        md += [f'## {NAMES.get(vol, vol)}', '', '| # | 文件 | 条目 | 注文 | Word | 网页 |', '|---|---|---|---|---|---|']
        for f, _ in volume_items(cfg, repo, vol):
            if excluded(cfg, repo, f): continue
            rel = f.relative_to(repo).as_posix(); lines = f.read_text('utf-8').splitlines()
            conv = refnotes.converted(lines)
            if not conv: continue
            web = web_notes(a.site, rel)
            for k, (i, entry, lab, paras) in enumerate(conv):
                s = norm(refnotes.strip_md(''.join(paras)))
                wi = len(src_all); src_all.append(s)
                w_ok = wi < len(wn) and wn[wi] == s
                b_ok = web is not None and k < len(web) and web[k] == s
                total += 1; diff += (not w_ok) + (not b_ok)
                note = '<br>'.join(p.replace('|', '\\|') for p in paras)
                md.append(f'| {len(src_all)} | {rel}:{i + 1} | {entry[:60].replace("|", "\\|")} | {note} | {"一致" if w_ok else "**不一致**"} | {"一致" if b_ok else "**不一致**"} |')
        extra = len(wn) - len(src_all)
        if extra: diff += abs(extra); md.append(f'\n**Word 条目注文数 {len(wn)} 与源稿 {len(src_all)} 不符**')
        summary.append(f'{NAMES.get(vol, vol)} {len(src_all)} 条'); md.append('')
    md.insert(2, f'共 {total} 条（{"、".join(summary)}）；Word／网页与源稿不一致 {diff} 处。')
    md.insert(3, '')
    Path(a.o).write_text('\n'.join(md) + '\n', 'utf-8')
    print(f'条目注文 {total} 条（{"、".join(summary)}），不一致 {diff} 处 -> {a.o}')
    sys.exit(1 if diff else 0)

if __name__ == '__main__': main()
