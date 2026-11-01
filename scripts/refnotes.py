"""参考文献条目注文：Word（scripts/docx/build_docx.py）与网页（scripts/build-site.py）共用的判定。

Scott 2026-11-01 定（方案 A 补充修订）：参考文献条目上的脚注不再作为脚注，原注文（引用范围、定位）
以小一号字直接接在条目后面；正文里的脚注照常保留。两端只用本模块判定，保证 Word 与网页一致。

口径（出版审读复核意见）：
1. 参考文献节只认“整行就是标题”的标题行（# 参考文献、## 7. 资料来源、## 本章参考资料 等），
   正文或更长标题里出现同样的词不算；节到同级或更高一级标题为止。
2. 多段脚注（续段缩进 4 格，段间空行）保留分段，不并成一段。
3. 参考文献节里只有列表条目（[1]、1.、- 开头）才算条目；节内说明段落上的脚注仍按普通脚注处理。
"""
import re

REF_HEADING = re.compile(
    r'^\s{0,3}#{1,6}\s+(?:\d+(?:\.\d+)*[.、]?\s*)?(?:本章|导论|原节)?'
    r'(?:参考文献|参考资料|资料来源|references|bibliography)\s*#*\s*$', re.I)
HEADING = re.compile(r'^\s{0,3}(#{1,6})\s')
ENTRY = re.compile(r'^\s{0,3}(?:\[\d+\]|［\d+］|\d+[.)、]\s|[-*+]\s)')
FN_DEF = re.compile(r'^\[\^([^\]]+)\]:\s?(.*)$')
FN_REF = re.compile(r'\[\^([^\]\s]+)\](?!:)')
CONT = re.compile(r'^( {4}|\t)')


def _clean_heading(line):
    return re.sub(r'<a id="[^"]*"></a>|[*`]', '', line)


def is_reference_heading(line):
    return bool(REF_HEADING.match(_clean_heading(line)))


def parse_footnotes(lines):
    """返回 ({标签: [段落文本, ...]}, {定义所占行号})。续行缩进 4 格；空行后仍缩进的为新的一段。"""
    defs, used, k = {}, set(), 0
    while k < len(lines):
        m = FN_DEF.match(lines[k])
        if not m:
            k += 1; continue
        label, paras, cur = m.group(1), [], [m.group(2).strip()]
        used.add(k); k += 1
        while k < len(lines):
            if CONT.match(lines[k]) and lines[k].strip():
                cur.append(lines[k].strip()); used.add(k); k += 1; continue
            if not lines[k].strip():   # 空行后若仍是缩进续段，开新段
                j = k
                while j < len(lines) and not lines[j].strip(): j += 1
                if j < len(lines) and CONT.match(lines[j]):
                    paras.append(_join(cur)); cur = []
                    used.update(range(k, j)); k = j; continue
            break
        paras.append(_join(cur))
        defs[label] = [p for p in paras if p]
    return defs, used


def _join(parts):
    out = ''
    for s in parts:
        if out and re.match(r'[A-Za-z0-9]', out[-1:]) and re.match(r'[A-Za-z0-9]', s[:1]): out += ' '
        out += s
    return out


def entry_lines(lines, skip=frozenset()):
    """参考文献节内列表条目所占行号（含条目的懒续行）。skip：脚注定义行。"""
    out, level, in_entry, fence = set(), None, False, False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith('```'): fence = not fence
        if fence or i in skip:
            in_entry = False; continue
        h = HEADING.match(ln)
        if h:
            n = len(h.group(1)); in_entry = False
            if level is not None and n <= level: level = None
            if is_reference_heading(ln): level = n
            continue
        if level is None or not s:
            in_entry = False; continue
        if ENTRY.match(ln): in_entry = True
        elif CONT.match(ln) and in_entry: pass
        elif not in_entry: continue
        out.add(i)
    return out


def plan(lines):
    """返回 (defs, def_lines, inline)：inline 为 {行号: [该行要改成注文的脚注标签, ...]}。"""
    defs, used = parse_footnotes(lines)
    inline = {}
    for i in sorted(entry_lines(lines, used)):
        labels = [m.group(1) for m in FN_REF.finditer(lines[i]) if m.group(1) in defs]
        if labels: inline[i] = labels
    return defs, used, inline


def strip_md(text):
    """注文纯文本（用于 Word／网页一致性核对）。"""
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*|\*(.+?)\*|`([^`]*)`', lambda m: next(g for g in m.groups() if g is not None), text)
    return re.sub(r'\s+', '', text)


def converted(path_lines):
    """[(行号, 条目文本, 标签, [段落...])]：本篇全部改为条目注文的脚注。"""
    defs, used, inline = plan(path_lines)
    return [(i, FN_REF.sub('', path_lines[i]).strip(), lab, defs[lab]) for i, labs in inline.items() for lab in labs]
