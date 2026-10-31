#!/usr/bin/env python3
"""成品包清理（出版审读 d7b16e3 预审 P1-3、P2）：在字体嵌入之后对 docx 包做最后一步处理。

  1. 删除 python-docx 模板残留的 word/stylesWithEffects.xml（内含 Courier 等专有字体名），并删除 rels、[Content_Types] 中对它的引用；
  2. numbering.xml：删除正文未使用的编号定义（模板里带 Symbol 字体的项目符号），同时去掉样式里指向这些编号的 numPr；
  3. styles.xml：去掉全部主题色引用（themeColor/themeTint/themeShade/themeFill…），文字和边框颜色一律改为黑色 000000。
  4. styles.xml：删除正文（含页眉页脚脚注）没有引用的内置样式中带底纹或彩色的那些（Light Shading 等 98 个表格样式及彩色内置样式），
     保留样式的颜色一律改黑、底纹（w:shd 的 fill）一律去掉，清理后 styles.xml 不含非黑颜色和底纹。
只改包结构和未使用的定义，不改正文。"""
import re, shutil, tempfile, zipfile
from pathlib import Path
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q = lambda t: f'{{{W}}}{t}'
SWE = 'word/stylesWithEffects.xml'
THEME_ATTRS = ('themeColor', 'themeTint', 'themeShade', 'themeFill', 'themeFillTint', 'themeFillShade')

def _clean_styles(st, drop_num):
    root = etree.fromstring(st); n = 0
    for el in root.iter():
        hit = False
        for a in THEME_ATTRS:
            if el.get(q(a)) is not None: del el.attrib[q(a)]; hit = True
        if hit:
            n += 1
            if el.get(q('color')) is not None: el.set(q('color'), '000000')   # 边框
            if el.tag == q('color'): el.set(q('val'), '000000')
    for numpr in root.iter(q('numPr')):
        nid = numpr.find(q('numId'))
        if nid is not None and nid.get(q('val')) in drop_num: numpr.getparent().remove(numpr)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), n

BLACK = {'000000', 'auto'}
def colored(el):
    """元素（含子孙）有非黑颜色或底纹填充。"""
    for e in el.iter():
        if e.get(q('fill')) not in (None, 'auto'): return True
        if e.tag == q('color') and e.get(q('val')) not in BLACK: return True
        if e.tag != q('color') and e.get(q('color')) not in (None, *BLACK): return True
    return False

def _prune_styles(st, used):
    """删除未引用的彩色/底纹样式（含全部未引用的表格样式），并把保留样式的颜色改黑、去底纹。返回 (xml, 删除的样式数)。"""
    root = etree.fromstring(st)
    styles = {s.get(q('styleId')): s for s in root.findall(q('style'))}
    keep = set(used) | {i for i, s in styles.items() if s.get(q('default')) == '1'}
    todo = list(keep)
    while todo:   # basedOn / link / next 依赖闭包
        s = styles.get(todo.pop())
        if s is None: continue
        for t in ('basedOn', 'link', 'next'):
            e = s.find(q(t))
            if e is not None and e.get(q('val')) not in keep: keep.add(e.get(q('val'))); todo.append(e.get(q('val')))
    n = 0
    for i, s in styles.items():
        if i not in keep and (s.get(q('type')) == 'table' or colored(s)): root.remove(s); n += 1
    for e in list(root.iter(q('shd'))):
        if e.get(q('fill')) not in (None, 'auto'): e.getparent().remove(e)
    for e in root.iter():
        if e.tag == q('color') and e.get(q('val')) not in BLACK: e.set(q('val'), '000000')
        elif e.tag != q('color') and e.get(q('color')) not in (None, *BLACK): e.set(q('color'), '000000')
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), n

def _clean_numbering(nb, used):
    root = etree.fromstring(nb)
    nums = root.findall(q('num')); drop = set()
    keep_abs = set()
    for nm in nums:
        nid = nm.get(q('numId'))
        if nid in used:
            a = nm.find(q('abstractNumId')); keep_abs.add(a.get(q('val')) if a is not None else None)
        else: drop.add(nid); root.remove(nm)
    for ab in root.findall(q('abstractNum')):
        if ab.get(q('abstractNumId')) not in keep_abs: root.remove(ab)
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), drop

def clean(path):
    path = Path(path); log = {}
    with zipfile.ZipFile(path) as zi:
        names = zi.namelist(); data = {n: zi.read(n) for n in names}; infos = {n: zi.getinfo(n) for n in names}
    # 正文、页眉页脚、脚注里实际用到的编号
    used = set()
    for n in names:
        if re.match(r'word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$', n):
            used |= set(re.findall(rb'<w:numId w:val="(\d+)"', data[n]))
    used = {u.decode() for u in used}
    drop = set()
    if 'word/numbering.xml' in data:
        data['word/numbering.xml'], drop = _clean_numbering(data['word/numbering.xml'], used)
    log['numbering_removed'] = sorted(drop, key=int)
    data['word/styles.xml'], log['theme_color_refs_removed'] = _clean_styles(data['word/styles.xml'], drop)
    sused = set()
    for n in names:
        if re.match(r'word/(document|header\d*|footer\d*|footnotes|endnotes|numbering)\.xml$', n) and n in data:
            sused |= {u.decode() for u in re.findall(rb'<w:(?:pStyle|rStyle|tblStyle|numStyleLink|styleLink) w:val="([^"]+)"', data[n])}
    data['word/styles.xml'], log['styles_removed'] = _prune_styles(data['word/styles.xml'], sused)
    log['stylesWithEffects_removed'] = SWE in data
    data.pop(SWE, None)
    for n in [x for x in data if x.endswith('.rels')]:
        root = etree.fromstring(data[n]); ch = False
        for r in list(root):
            if r.get('Target', '').endswith('stylesWithEffects.xml'): root.remove(r); ch = True
        if ch: data[n] = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    ct = etree.fromstring(data['[Content_Types].xml'])
    for o in list(ct):
        if o.get('PartName', '').endswith('stylesWithEffects.xml'): ct.remove(o)
    data['[Content_Types].xml'] = etree.tostring(ct, xml_declaration=True, encoding='UTF-8', standalone=True)
    fd, tmp = tempfile.mkstemp(suffix='.docx', dir=str(path.parent)); Path(tmp).unlink()
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zo:
        for n in names:
            if n in data:
                zi_ = infos[n]; zo.writestr(n, data[n], compress_type=zi_.compress_type)
    mode = path.stat().st_mode
    shutil.move(tmp, path); path.chmod(mode & 0o777)
    return log

def audit(path):
    """返回问题列表：stylesWithEffects 部件或引用、Courier、Symbol、styles 中的 themeColor。"""
    bad = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if any('stylesWithEffects' in n for n in names): bad.append('包内有 stylesWithEffects 部件')
        for n in names:
            if n.endswith('.rels') or n == '[Content_Types].xml':
                if b'stylesWithEffects' in z.read(n): bad.append(f'{n} 引用 stylesWithEffects')
            if n.endswith('.xml') and n.startswith('word/') and not n.startswith('word/media'):
                b = z.read(n)
                if b'Courier' in b: bad.append(f'{n} 含 Courier')
                if re.search(rb'="Symbol"', b): bad.append(f'{n} 含 Symbol 字体')
        st = z.read('word/styles.xml')
        k = len(re.findall(rb'w:theme(Color|Tint|Shade|Fill)', st))
        if k: bad.append(f'styles.xml 有 {k} 处主题色引用')
    return bad

def styles_color_issues(st):
    """styles.xml 中的非黑颜色（w:color、边框 color）和底纹填充（fill）。"""
    root = etree.fromstring(st); bad = []
    cols = sorted({e.get(q('val')) for e in root.iter(q('color')) if e.get(q('val')) not in BLACK} |
                  {e.get(q('color')) for e in root.iter() if e.tag != q('color') and e.get(q('color')) not in (None, *BLACK)})
    fills = sorted({e.get(q('fill')) for e in root.iter() if e.get(q('fill')) not in (None, 'auto')})
    if cols: bad.append(f'styles.xml 有非黑颜色 {len(cols)} 种：' + '、'.join(cols[:8]))
    if fills: bad.append(f'styles.xml 有底纹填充 {len(fills)} 种：' + '、'.join(fills[:8]))
    return bad
