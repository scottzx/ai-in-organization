#!/usr/bin/env python3
"""Word 嵌入字体：把 docx 用到的字体文件按 ECMA-376 混淆为 word/fonts/*.odttf，
写入 fontTable.xml 的 w:embedRegular/w:embedBold、fontTable.xml.rels、[Content_Types].xml，
并在 settings.xml 打开 w:embedTrueTypeFonts、w:saveSubsetFonts。
字体文件按 style.yaml fonts.embed 查找（search_dirs、环境变量 BOOK_FONT_DIR），找不到的字体如实列为缺失，不拿别的字体冒充。"""
import os, re, uuid, zipfile, shutil, tempfile
from pathlib import Path
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PR = 'http://schemas.openxmlformats.org/package/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
RT_FONT = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/font'
ODTTF_CT = 'application/vnd.openxmlformats-officedocument.obfuscatedFont'
q = lambda ns, t: f'{{{ns}}}{t}'

def obfuscate(data, guid):
    """ECMA-376 Part 2 §… 字体混淆：前 32 字节与 GUID 逆序字节异或（对称，解混淆同一函数）。"""
    key = bytes.fromhex(guid.strip('{}').replace('-', ''))[::-1]
    b = bytearray(data)
    for i in range(32): b[i] ^= key[i % 16]
    return bytes(b)

def used_fonts(zf):
    """正文、页眉页脚、脚注直接用到的字体，加上被引用样式（含 basedOn 链）和 docDefaults 的字体。
    python-docx 模板里未被使用的样式（如 Macro Text 的 Courier）不算。"""
    from lxml import etree
    W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    names, used_ids = set(), set()
    def take(el):
        for rf in el.iter(W + 'rFonts'):
            for k in ('eastAsia', 'ascii', 'hAnsi', 'cs'):
                v = rf.get(W + k)
                if v: names.add(v)
    for n in zf.namelist():
        if re.match(r'word/(document|header\d*|footer\d*|footnotes)\.xml$', n):
            root = etree.fromstring(zf.read(n)); take(root)
            for t in ('pStyle', 'rStyle', 'tblStyle'):
                used_ids.update(e.get(W + 'val') for e in root.iter(W + t))
    if 'word/styles.xml' in zf.namelist():
        st = etree.fromstring(zf.read('word/styles.xml'))
        for d in st.iter(W + 'docDefaults'): take(d)
        by_id = {e.get(W + 'styleId'): e for e in st.iter(W + 'style')}
        for e in by_id.values():
            if e.get(W + 'default') == '1': used_ids.add(e.get(W + 'styleId'))
        seen = set()
        todo = [i for i in used_ids if i]
        while todo:
            i = todo.pop()
            if i in seen or i not in by_id: continue
            seen.add(i); take(by_id[i])
            for t in ('basedOn', 'link'):
                for e in by_id[i].findall(W + t): todo.append(e.get(W + 'val'))
    return sorted(names)

def _family_names(path):
    from fontTools.ttLib import TTFont
    try:
        f = TTFont(str(path), lazy=True, fontNumber=0)
        if 'fvar' in f: return set(), False   # 可变字体 Word 不能可靠嵌入，跳过（fetch_fonts.py 已生成静态 Regular/Bold）
        out = {r.toUnicode().strip() for r in f['name'].names if r.nameID in (1, 4, 16)}
        sub = {r.toUnicode().strip().lower() for r in f['name'].names if r.nameID in (2, 17)}
        return out, ('bold' in ' '.join(sub) and 'regular' not in sub)
    except Exception:
        return set(), False

def find_fonts(names, cfg):
    """返回 {字体名: {'regular': 路径, 'bold': 路径?}}；只收 TrueType/OpenType 单字体文件（.ttf/.otf），.ttc 不能嵌入 Word。"""
    e = (cfg.get('fonts', {}).get('embed') or {})
    dirs = [os.environ['BOOK_FONT_DIR']] if os.environ.get('BOOK_FONT_DIR') else []
    here = Path(__file__).resolve().parent   # 相对路径按本脚本目录解析（如 fonts/ 下随仓库的 Source Serif 4）
    dirs += [str(here / os.path.expanduser(d)) if not os.path.isabs(os.path.expanduser(d)) else os.path.expanduser(d) for d in e.get('search_dirs', [])]
    files = {k: [x.lower() for x in v] for k, v in (e.get('files') or {}).items()}
    found = {}
    cands = []
    for d in dirs:
        if os.path.isdir(d):
            cands += [p for p in Path(d).rglob('*') if p.suffix.lower() in ('.ttf', '.otf')]
    for p in cands:
        fam, bold = None, False
        for n in names:
            if p.name.lower() in files.get(n, []) or p.stem == n: fam = n; bold = bool(re.search(r'bd|bold', p.stem, re.I))
        if fam is None:
            fams, bold = _family_names(p)
            fam = next((n for n in names if n in fams), None)
        if fam: found.setdefault(fam, {}).setdefault('bold' if bold else 'regular', p)
    return {k: v for k, v in found.items() if 'regular' in v}

def doc_chars(parts):
    """docx 中实际出现的字符（正文、页眉页脚、脚注、目录），外加 ASCII 可见字符和常用全角标点，供字体子集化。"""
    txt = set(chr(c) for c in range(0x20, 0x7f)) | set('　，。、；：？！“”‘’（）《》〈〉【】—…·－～％／０１２３４５６７８９')
    for n, b in parts.items():
        if re.match(r'word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$', n):
            for m in re.finditer(rb'<w:(?:t|instrText)(?: [^>]*)?>([^<]*)</w:', b):
                txt |= set(etree.fromstring(b'<x>' + m.group(1) + b'</x>').text or '')
    return ''.join(sorted(txt))

def subset_font(src, text):
    """按 text 子集化（保留 name 表与排版特性，字体名不变），返回 TTF 字节；失败则返回 None（调用方改嵌完整字体）。"""
    from fontTools import subset
    try:
        opt = subset.Options(); opt.name_IDs = ['*']; opt.name_languages = ['*']; opt.layout_features = ['*']
        opt.notdef_outline = True; opt.glyph_names = False; opt.hinting = True; opt.legacy_kern = True
        f = subset.load_font(str(src), opt); sb = subset.Subsetter(opt); sb.populate(text=text); sb.subset(f)
        bio = __import__('io').BytesIO(); f.save(bio); return bio.getvalue()
    except Exception as ex:
        print(f'  子集化失败，嵌入完整字体：{src}（{ex}）'); return None

def embed(docx_path, cfg):
    """原地改写 docx。返回 {'embedded': [{font, kind, file, bytes}], 'missing': [字体名]}。"""
    e = cfg.get('fonts', {}).get('embed') or {}
    if not e.get('enabled', True): return {'embedded': [], 'missing': [], 'disabled': True}
    zin = zipfile.ZipFile(docx_path)
    names = used_fonts(zin); hits = find_fonts(names, cfg)
    parts = {n: zin.read(n) for n in zin.namelist()}; zin.close()
    ft = etree.fromstring(parts['word/fontTable.xml'])
    rels_name = 'word/_rels/fontTable.xml.rels'
    rels = etree.fromstring(parts[rels_name]) if rels_name in parts else etree.Element(q(PR, 'Relationships'), nsmap={None: PR})
    res = {'embedded': [], 'missing': [n for n in names if n not in hits]}
    do_sub = e.get('subset', True); text = doc_chars(parts) if do_sub else ''
    k = 0
    for name in names:
        if name not in hits: continue
        font = next((f for f in ft.findall(q(W, 'font')) if f.get(q(W, 'name')) == name), None)
        if font is None:
            font = etree.SubElement(ft, q(W, 'font')); font.set(q(W, 'name'), name)
        for kind in ('regular', 'bold'):
            src = hits[name].get(kind)
            if not src: continue
            k += 1; guid = '{' + str(uuid.uuid4()).upper() + '}'; target = f'fonts/font{k}.odttf'
            data = (subset_font(src, text) if do_sub else None) or src.read_bytes()   # 子集化：只保留本书用到的字，docx 不至过大
            parts['word/' + target] = obfuscate(data, guid)
            rid = f'rIdFont{k}'
            rel = etree.SubElement(rels, q(PR, 'Relationship')); rel.set('Id', rid); rel.set('Type', RT_FONT); rel.set('Target', target)
            tag = 'embedRegular' if kind == 'regular' else 'embedBold'
            old = font.find(q(W, tag))
            if old is not None: font.remove(old)
            em = etree.SubElement(font, q(W, tag)); em.set(q(R, 'id'), rid); em.set(q(W, 'fontKey'), guid)
            res['embedded'].append({'font': name, 'kind': kind, 'file': str(src), 'bytes': len(data), 'source_bytes': src.stat().st_size})
    if res['embedded']:
        parts['word/fontTable.xml'] = etree.tostring(ft, xml_declaration=True, encoding='UTF-8', standalone=True)
        parts[rels_name] = etree.tostring(rels, xml_declaration=True, encoding='UTF-8', standalone=True)
        ct = etree.fromstring(parts['[Content_Types].xml'])
        if not any(d.get('Extension') == 'odttf' for d in ct.findall(q(CT, 'Default'))):
            d = etree.Element(q(CT, 'Default')); d.set('Extension', 'odttf'); d.set('ContentType', ODTTF_CT); ct.insert(0, d)
        parts['[Content_Types].xml'] = etree.tostring(ct, xml_declaration=True, encoding='UTF-8', standalone=True)
    st = etree.fromstring(parts['word/settings.xml'])
    for tag in ('saveSubsetFonts', 'embedTrueTypeFonts'):   # 顺序按 CT_Settings：embedTrueTypeFonts 在 saveSubsetFonts 前，均紧随 zoom 等之后
        if st.find(q(W, tag)) is None:
            el = etree.Element(q(W, tag))
            anchor = None
            for prev in ('removePersonalInformation', 'removeDateAndTime', 'zoom', 'view', 'writeProtection'):
                anchor = st.find(q(W, prev))
                if anchor is not None: break
            if anchor is not None: anchor.addnext(el)
            else: st.insert(0, el)
    if not res['embedded']:   # 没有任何字体文件时不声称已嵌入
        for tag in ('embedTrueTypeFonts', 'saveSubsetFonts'):
            el = st.find(q(W, tag))
            if el is not None: st.remove(el)
    parts['word/settings.xml'] = etree.tostring(st, xml_declaration=True, encoding='UTF-8', standalone=True)
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False, dir=os.path.dirname(os.path.abspath(docx_path))) as fh:   # 不用 mktemp（有竞态）
        tmp = fh.name
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in parts.items(): z.writestr(n, b)
    os.chmod(tmp, 0o644)   # NamedTemporaryFile 建的是 0600（出版审读 #78 P2②）
    shutil.move(tmp, docx_path)
    return res

def verify(docx_path):
    """check_docx 用：返回 (embedTrueTypeFonts 已开, {字体名: 问题或 None}, 已用字体列表)。odttf 须能解混淆并被 fontTools 解析。"""
    import io
    from fontTools.ttLib import TTFont
    z = zipfile.ZipFile(docx_path)
    names = used_fonts(z)
    st = etree.fromstring(z.read('word/settings.xml'))
    on = st.find(q(W, 'embedTrueTypeFonts')) is not None
    ft = etree.fromstring(z.read('word/fontTable.xml'))
    rels = {}
    if 'word/_rels/fontTable.xml.rels' in z.namelist():
        rels = {r.get('Id'): r.get('Target') for r in etree.fromstring(z.read('word/_rels/fontTable.xml.rels'))}
    out = {}
    for n in names:
        f = next((x for x in ft.findall(q(W, 'font')) if x.get(q(W, 'name')) == n), None)
        em = f.find(q(W, 'embedRegular')) if f is not None else None
        if em is None: out[n] = '未嵌入'; continue
        tgt = rels.get(em.get(q(R, 'id')))
        if not tgt or 'word/' + tgt not in z.namelist(): out[n] = '关系或部件缺失'; continue
        try:
            TTFont(io.BytesIO(obfuscate(z.read('word/' + tgt), em.get(q(W, 'fontKey')))), lazy=True)['name']; out[n] = None
        except Exception as ex: out[n] = f'解混淆后不是有效字体（{ex.__class__.__name__}）'
    return on, out, names
