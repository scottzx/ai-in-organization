#!/usr/bin/env python3
"""Check case structure and reject editorial placeholders in published prose."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import unicodedata

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'templates/case-structure.json').read_text(encoding='utf-8'))
REQUIRED = CONFIG['required_h2']
INDEX = json.loads((ROOT / '索引/案例来源索引.json').read_text(encoding='utf-8'))
ENTRIES = {entry['id']: entry for entry in INDEX['entries']}
# 册首不编号篇目（如下册导言）不是案例，名单读 style.yaml 的 volumes.<vol>.front
STYLE = yaml.safe_load((ROOT / 'scripts/docx/style.yaml').read_text(encoding='utf-8'))
BRIEF_REQUIRED = ['资料来源']
# 简述篇白名单：取自 Datawhale《FDE案例100》、已压缩为一两段事实简述的21篇（PR #95）。
# 其他篇目即使在来源索引里标了 presentation: brief，也按七节模板检查并报错。
BRIEF_IDS = frozenset('''C01 C02 C07 C10 C11 C23 C24 C25 F01 F07 F08 F10 J01 L01 L03 L06
M01 M02 M03 S01 附B01'''.split())
# 简述篇“资料来源”之前的正文上限（不计空白，含一级标题、锚点与阶段行）。现有最长314字，留余量。
BRIEF_MAX_CHARS = 400


def nfc(path):
    """路径按 NFC 规范化后比较（macOS 文件名常为 NFD）。"""
    return unicodedata.normalize('NFC', str(Path(path).resolve()))


FRONT = {nfc(ROOT / v['dir'] / f) for v in STYLE.get('volumes', {}).values()
         if isinstance(v, dict) and v.get('dir') for f in v.get('front', [])}


def visible_lines(text):
    """Ignore fenced examples and HTML comments while keeping source line numbers."""
    text = re.sub(r'<!--[\s\S]*?-->', lambda m: '\n' * m[0].count('\n'), text)
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if fence:
            if re.fullmatch(r'\s*' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
                fence = None
            continue
        if match:
            fence = match[1]
            continue
        yield number, line


def display_path(path):
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def check_case(path):
    errors = []
    try:
        lines = list(visible_lines(path.read_text(encoding='utf-8')))
    except (OSError, UnicodeError) as exc:
        return {'path': display_path(path), 'errors': [str(exc)]}
    headings = []
    for number, line in lines:
        match = re.match(r'^(#{1,6})\s+(.+?)\s*$', line)
        if match:
            headings.append((number, len(match[1]), match[2]))
    h1 = [(number, title) for number, level, title in headings if level == 1]
    entry = None
    if len(h1) != 1:
        errors.append('必须且只能有一个一级标题')
    else:
        case_id = h1[0][1].split(' ', 1)[0]
        entry = ENTRIES.get(case_id)
        if entry is None:
            errors.append(f'案例编号未登记：{case_id}')
        elif h1[0][1] != CONFIG['h1_format'].format(**entry):
            errors.append('一级标题的编号或题名与来源索引不一致')
        if headings and headings[0][1] != 1:
            errors.append('一级标题必须在其他标题之前')
    sections = [(number, title) for number, level, title in headings if level == 2]
    titles = [title for _, title in sections]
    # 简述篇（来源索引 presentation=brief 且在 BRIEF_IDS 白名单内）：一两段事实简述，只设“资料来源”一节。
    brief = False
    if entry and entry.get('presentation') == 'brief':
        if entry['id'] in BRIEF_IDS:
            brief = True
        else:
            errors.append(f'简述篇未列入白名单：{entry["id"]}')
    required = BRIEF_REQUIRED if brief else REQUIRED
    if brief:
        source_line = next((number for number, level, title in headings if level == 2 and title == '资料来源'), None)
        for number, level, title in headings:
            if level > 1 and number != source_line:
                errors.append(f'简述篇正文不得有其他标题：第{number}行“{title}”')
        body = ''.join(line for number, line in lines if source_line is None or number < source_line)
        size = len(re.sub(r'\s', '', body))
        if size > BRIEF_MAX_CHARS:
            errors.append(f'简述篇正文超过{BRIEF_MAX_CHARS}字：{size}字')
    missing = [title for title in required if title not in titles]
    extra = [title for title in titles if title not in required]
    duplicates = [title for title, count in Counter(titles).items() if count > 1]
    if missing:
        errors.append('缺少二级标题：' + '；'.join(missing))
    if extra:
        errors.append('非模板二级标题：' + '；'.join(extra))
    if duplicates:
        errors.append('重复二级标题：' + '；'.join(duplicates))
    if not missing and not extra and not duplicates and titles != required:
        errors.append('二级标题顺序不符合模板')
    for i, (start, title) in enumerate(sections):
        end = sections[i + 1][0] if i + 1 < len(sections) else float('inf')
        content = [line for number, line in lines if start < number < end]
        prose = '\n'.join(line for line in content if not re.match(r'^#{1,6}\s', line))
        prose = re.sub(r'</?[A-Za-z][\w-]*(?:\s[^>]*)?/?>', '', prose)
        if not re.sub(r'[\s*_\-|]', '', prose):
            errors.append('空节：' + title)
    scene_headings = {}
    for i, (start, title) in enumerate(sections):
        if title not in REQUIRED[2:5]:
            continue
        end = sections[i + 1][0] if i + 1 < len(sections) else float('inf')
        scene_headings[title] = [heading for number, level, heading in headings
                                 if start < number < end and level == 3]
    # Several named scenes must correspond through problem, implementation and result.
    multiple_scenes = (entry and len(entry['fragments']) > 1) or (
        len(scene_headings.get(REQUIRED[2], [])) > 1 and len(scene_headings.get(REQUIRED[4], [])) > 1)
    if multiple_scenes and any(len(items) > 1 for items in scene_headings.values()):
        names = [scene_headings.get(title, []) for title in REQUIRED[2:5]]
        if names[0] != names[1] or names[1] != names[2]:
            errors.append('问题、方案、效果的三级场景标题必须同名、同序')
    for number, line in lines:
        plain = re.sub(r'[*_]', '', line).strip()
        if re.search(CONFIG['editorial_placeholder_pattern'], plain):
            errors.append(f'第{number}行存在不应写入正文的资料补充任务')
        if re.search(r'(?:^|[：:])\s*(?:待补|待填写|TODO|TBD)[：:。.!！]?$', plain, re.I) or re.search(r'\{[^{}]+\}', plain):
            errors.append(f'第{number}行存在未替换占位符')
    visible = '\n'.join(line for _, line in lines)
    anchor_matches = list(re.finditer(r'<a\s+id="([^"]+)"\s*>', visible))
    anchors = [match[1] for match in anchor_matches]
    for anchor, count in Counter(anchors).items():
        if count > 1:
            errors.append('重复场景锚点：' + anchor)
    if entry:
        for fragment in entry['fragments']:
            if fragment['anchor'] not in anchors:
                errors.append('缺少原场景锚点：' + fragment['anchor'])
                continue
            position = anchors.index(fragment['anchor'])
            start = anchor_matches[position].end()
            end = anchor_matches[position + 1].start() if position + 1 < len(anchor_matches) else len(visible)
            metadata = '**阶段：' + fragment['stage_label'] + '。**'
            if metadata not in visible[start:end]:
                errors.append('场景阶段缺失或与来源索引不一致：' + fragment['source_fragment_id'])
    return {'path': display_path(path), 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path, help='Case Markdown files or directories already migrated to the template')
    args = parser.parse_args()
    files = set()
    input_errors = []
    skipped = 0
    for path in args.paths:
        if path.is_dir():
            files.update(p.resolve() for p in path.rglob('*.md') if p.name != 'README.md' and nfc(p) not in FRONT)
        elif path.is_file() and path.suffix == '.md':
            if nfc(path) in FRONT:   # 显式传入的册首 front 篇目同样跳过
                print(f'跳过册首不编号篇目（style.yaml front）：{display_path(path.resolve())}', file=sys.stderr)
                skipped += 1
                continue
            files.add(path.resolve())
        else:
            input_errors.append('不存在的案例文件或目录：' + str(path))
    if not files and not skipped:   # 只传了 front 篇目：已跳过，不算输入错误
        input_errors.append('未找到案例Markdown文件')
    results = [check_case(path) for path in sorted(files)]
    passed = not input_errors and all(not item['errors'] for item in results)
    print(json.dumps({'passed': passed, 'files_checked': len(results),
                      'required_sections': REQUIRED, 'input_errors': input_errors,
                      'results': results}, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
