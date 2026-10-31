#!/usr/bin/env python3
"""检查成品范围内 Markdown 的相对链接与 #锚点（网页版 / EPUB 用）。

范围：scripts/docx/style.yaml 中 --volume all 实际纳入 Word 的篇目（与 build_docx 同一套解析，排除 exclude 规则），
另加网页版导航用的 索引/*.md（阅读路径、资料来源说明等）。
锚点规则：显式 <a id="..."></a>，以及标题自动 slug（与 scripts/build-site.py 的 slug() 一致：
小写、去掉非 \\w/-/空白字符、空格换成 -；同名标题依次加 -1、-2……）。
外部链接（http/https/mailto）不查。
用法：python3 scripts/check-md-links.py [--repo 仓库根] [--style style.yaml] [--volume all] [-v]
退出码：0 全部有效；1 有失效链接或锚点。
"""
import argparse, re, sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'docx'))

LINK = re.compile(r'(?<!!)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(<?([^)\s>]+)>?(?:\s+"[^"]*")?\)')
AID = re.compile(r'<a\s+(?:id|name)="([^"]+)"\s*>\s*</a>')
HEAD = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')


def slug(text):
    return re.sub(r'[^\w\-\s]', '', text.lower()).replace(' ', '-')


def heading_text(raw):
    t = AID.sub('', raw)
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', t)
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'(\*\*|__|\*|_(?=\S)|`)', '', t)
    return t.strip()


_cache = {}
def anchors(path):
    if path in _cache: return _cache[path]
    ids, counts, fence = set(), Counter(), False
    for ln in path.read_text(encoding='utf-8').splitlines():
        if ln.lstrip().startswith(('```', '~~~')): fence = not fence; continue
        if fence: continue
        ids.update(AID.findall(ln))
        m = HEAD.match(ln)
        if m:
            a = slug(heading_text(m.group(2))); n = counts[a]; counts[a] += 1
            ids.add(a if not n else f'{a}-{n}')
    _cache[path] = ids
    return ids


def scope(repo, style, volume):
    import yaml, build_docx as bd
    cfg = yaml.safe_load(Path(style).read_text(encoding='utf-8'))
    files = [p for p, _ in bd.volume_items(cfg, repo, volume) if not bd.excluded(cfg, repo, p)]
    return files + sorted((repo / '索引').glob('*.md'))   # 网页版导航页（阅读路径、资料来源说明等）


def check(files, repo):
    bad = []
    for f in files:
        fence = False
        for i, ln in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            if ln.lstrip().startswith(('```', '~~~')): fence = not fence; continue
            if fence: continue
            for m in LINK.finditer(ln):
                url = m.group(2)
                if re.match(r'^[a-z][a-z0-9+.-]*:', url, re.I): continue
                path, _, frag = url.partition('#')
                tgt = (f.parent / unquote(path)).resolve() if path else f
                rel = f.relative_to(repo).as_posix()
                if not tgt.exists():
                    bad.append((rel, i, url, '目标文件不存在')); continue
                if frag and tgt.suffix == '.md' and unquote(frag) not in anchors(tgt):
                    bad.append((rel, i, url, '锚点不存在'))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=str(HERE.parent))
    ap.add_argument('--style', default=str(HERE / 'docx' / 'style.yaml'))
    ap.add_argument('--volume', default='all')
    ap.add_argument('files', nargs='*', help='只查这些文件（默认按 style.yaml 范围）')
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    files = [Path(x).resolve() for x in a.files] or scope(repo, a.style, a.volume)
    bad = check(files, repo)
    for rel, i, url, why in bad: print(f'{rel}:{i}  {why}  {url}')
    print(f'检查 {len(files)} 个篇目，失效链接/锚点 {len(bad)} 处')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
