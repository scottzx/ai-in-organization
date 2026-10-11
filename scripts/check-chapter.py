#!/usr/bin/env python3
"""检查单章的案例引用：正文是否干净、章末参考资料是否收全、字数是否异常。

用法：python3 scripts/check-chapter.py 上册-研究报告/03-单点提效为何未传导到整体交付.md
"""
import re
import sys
from pathlib import Path

CODE = r'(?:附[A-B]\d{2}|[A-Z]\d{2}|待\d{2})'
PAIR = re.compile(r'\[[^\]]*\]\[' + CODE + r'\]|\[' + CODE + r'\](?!\()')
ENTRY = re.compile(r'\[' + CODE + r'\](?!\()|（' + CODE + r'）')
DEF = re.compile(r'^\[[^\]]+\]:\s')


def main(path):
    text = Path(path).read_text(encoding='utf-8')
    han = len(re.findall(r'[\u4e00-\u9fff]', text))
    body, refs, codes = [], 0, set()
    zone = 'body'
    for line in text.split('\n'):
        if DEF.match(line.strip()):
            continue
        if re.match(r'^##\s+本章参考资料', line):
            zone = 'refs'
            continue
        found = ENTRY.findall(line)
        if zone == 'refs':
            refs += len(found)
            codes.update(c for c in found if c)
        elif found:
            body.append(line.strip()[:100])
    print(f'汉字数            {han}')
    print(f'正文里的案例引用   {len(body)}   ← 应为 0')
    for l in body:
        print(f'  残留: {l}')
    print(f'本章参考资料条目   {refs}')
    print(f'覆盖案例          {len(codes)}: {"、".join(sorted(codes))}')
    return 0 if not body else 1


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1]))
