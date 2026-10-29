"""首行缩进：Word 中 firstLineChars 优先于 firstLine。
段落（或其样式）首行缩进为 0、却带有（含从样式继承的）非零 firstLineChars 时，实际仍会缩进。
本模块找出这类“应顶格却缩进”的段落，并把 firstLineChars 显式置 0。"""
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _style_ind(style, attr):
    while style is not None:
        ppr = style.element.pPr
        ind = ppr.find(qn('w:ind')) if ppr is not None else None
        if ind is not None and ind.get(qn(attr)) is not None: return ind.get(qn(attr))
        style = style.base_style
    return None


def effective(p):
    """(firstLine, firstLineChars)：先取段落自身，再沿样式链继承。"""
    ppr = p._p.pPr; ind = ppr.find(qn('w:ind')) if ppr is not None else None
    fl = ind.get(qn('w:firstLine')) if ind is not None else None
    fc = ind.get(qn('w:firstLineChars')) if ind is not None else None
    if fl is None: fl = _style_ind(p.style, 'w:firstLine')
    if fc is None: fc = _style_ind(p.style, 'w:firstLineChars')
    return fl, fc


def all_paragraphs(doc):
    out = list(doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells: out += c.paragraphs
    return out


def offenders(doc):
    """首行缩进为 0（firstLine=0）而有效 firstLineChars 非零的段落。"""
    return [p for p in all_paragraphs(doc) for fl, fc in [effective(p)] if fl in ('0',) and fc not in (None, '0')]


def fix(doc):
    """把这类段落的 firstLineChars 显式置 0；返回修正段数。样式层同样处理（firstLine=0 的样式不继承非零字符缩进）。"""
    n = 0
    for s in doc.styles:
        try: el = s.element; ppr = el.pPr
        except AttributeError: continue
        ind = ppr.find(qn('w:ind')) if ppr is not None else None
        if ind is not None and ind.get(qn('w:firstLine')) == '0' and ind.get(qn('w:firstLineChars')) is None \
                and getattr(s, 'base_style', None) is not None and _style_ind(s.base_style, 'w:firstLineChars') not in (None, '0'):
            ind.set(qn('w:firstLineChars'), '0')
    for p in offenders(doc):
        ppr = p._p.get_or_add_pPr(); ind = ppr.find(qn('w:ind'))
        if ind is None: ind = OxmlElement('w:ind'); ppr.append(ind)
        ind.set(qn('w:firstLineChars'), '0'); n += 1
    return n
