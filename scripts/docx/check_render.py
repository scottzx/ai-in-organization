#!/usr/bin/env python3
"""渲染检查（出版审读 #108 复审）：LibreOffice 转 PDF 后实测
  1. 页数；2. “只有表题、没有表格内容”的页（页面正文最后一行是表题）；3. 目录页码与实际页码是否一一对应。
用法：python3 check_render.py 成品.docx [--pdf 保留PDF路径]；有问题时退出码 1。"""
import argparse, re, subprocess, sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import toc_fill

CAP = re.compile(r'^表\s?[0-9A-Z导]+-\d+')

def orphan_captions(pdf):
    n = int(re.search(r'Pages:\s+(\d+)', subprocess.run(['pdfinfo', pdf], capture_output=True, text=True).stdout).group(1))
    bad = []
    for i in range(1, n + 1):
        t = subprocess.run(['pdftotext', '-f', str(i), '-l', str(i), '-layout', pdf, '-'], capture_output=True, text=True).stdout
        ls = [l.strip() for l in t.splitlines() if l.strip()]
        body = ls[1:-1]   # 去页眉、页脚
        if body and CAP.match(body[-1]): bad.append((i, ls[-1], body[-1][:40]))
    return n, bad

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('docx'); ap.add_argument('--pdf'); a = ap.parse_args()
    tmp = tempfile.mkdtemp(); pdf = Path(a.pdf) if a.pdf else Path(tmp) / 'out.pdf'
    res = toc_fill.compare(a.docx, keep_pdf=pdf)
    n, bad = orphan_captions(pdf)
    mism = [(t, x, y) for t, x, y in res if x != y]
    print(f'{Path(a.docx).name}：{n} 页；只有表题的页 {len(bad)} 处；目录 {len(res)} 条，页码不符 {len(mism)} 条')
    for i, pg, c in bad: print(f'  只有表题：PDF 第{i}页（印刷页 {pg}）末行“{c}”')
    for t, x, y in mism[:20]: print(f'  目录不符：{t[:30]} 目录 {x} 实际 {y}')
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if bad or mism else 0)

if __name__ == '__main__': main()
