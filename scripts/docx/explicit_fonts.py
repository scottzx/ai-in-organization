"""文档默认字体、主题字体、全部样式一律改成显式的开源字体（出版审读 #78 P2①）。
python-docx 模板的 docDefaults 引用主题字体（Cambria/Calibri、宋体），未用的 MacroText 等样式写死 Courier；
这里统一改为 style.yaml 的西文字体（Source Serif 4）和中文默认字体（思源宋体 Noto Serif SC），只改字体名，不动字号、行距、缩进。"""
import re
from docx.oxml.ns import qn

EAST_DEFAULT = 'Noto Serif SC'
THEME_ATTRS = ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme')

def allowed(cfg):
    return set((cfg.get('fonts', {}).get('embed') or {}).get('files', {})) | {cfg['fonts']['latin']}

def _fix_rfonts(rf, latin, east, ok):
    for a in THEME_ATTRS:
        if rf.get(qn(a)) is not None: del rf.attrib[qn(a)]
    for a in ('w:ascii', 'w:hAnsi', 'w:cs'):
        if rf.get(qn(a)) not in ok or rf.get(qn(a)) is None: rf.set(qn(a), latin)
    if rf.get(qn('w:eastAsia')) not in ok: rf.set(qn('w:eastAsia'), east)

def fix(doc, cfg):
    latin = cfg['fonts']['latin']; ok = allowed(cfg); n = 0
    st = doc.styles.element
    rpr = st.find(qn('w:docDefaults') + '/' + qn('w:rPrDefault') + '/' + qn('w:rPr'))
    if rpr is not None:
        rf = rpr.find(qn('w:rFonts'))
        if rf is None:
            from docx.oxml import OxmlElement
            rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
        _fix_rfonts(rf, latin, EAST_DEFAULT, ok); n += 1
    for rf in st.iter(qn('w:rFonts')):
        if any(rf.get(qn(a)) is not None for a in THEME_ATTRS) or any(rf.get(qn(a)) is not None and rf.get(qn(a)) not in ok for a in ('w:ascii', 'w:hAnsi', 'w:cs', 'w:eastAsia')):
            _fix_rfonts(rf, latin, EAST_DEFAULT, ok); n += 1
    for part in doc.part.package.iter_parts():
        if re.match(r'/word/theme/theme\d*\.xml$', str(part.partname)):
            x = part.blob.decode('utf-8')
            x = re.sub(r'(<a:latin typeface=")[^"]*(")', lambda m: m.group(1) + latin + m.group(2), x)
            x = re.sub(r'(<a:ea typeface=")[^"]*(")', lambda m: m.group(1) + EAST_DEFAULT + m.group(2), x)
            x = re.sub(r'(<a:cs typeface=")[^"]*(")', lambda m: m.group(1) + latin + m.group(2), x)
            x = re.sub(r'(<a:font script="(?:Hans|Hant|Jpan|Hang)" typeface=")[^"]*(")', lambda m: m.group(1) + EAST_DEFAULT + m.group(2), x)
            x = re.sub(r'(<a:font script="(?!Hans|Hant|Jpan|Hang)[^"]*" typeface=")[^"]*(")', lambda m: m.group(1) + latin + m.group(2), x)
            part._blob = x.encode('utf-8'); n += 1
    return n

def audit(docx_path, cfg):
    """check_docx 用：返回不合格处列表（docDefaults/样式引用主题字体或非开源字体、主题字体非开源字体）。"""
    import zipfile
    ok = allowed(cfg); bad = []
    z = zipfile.ZipFile(docx_path)
    s = z.read('word/styles.xml').decode('utf-8')
    if re.search(r'w:(?:ascii|hAnsi|eastAsia|cs)Theme=', s): bad.append('styles.xml 引用主题字体')
    rfs = ' '.join(re.findall(r'<w:rFonts [^>]*>', s))
    for f in sorted(set(re.findall(r'w:(?:ascii|hAnsi|eastAsia|cs)="([^"]*)"', rfs)) - ok): bad.append(f'styles.xml 用了 {f}')
    if not re.search(r'<w:rPrDefault>\s*<w:rPr>\s*<w:rFonts [^>]*w:ascii=', s): bad.append('docDefaults 无显式字体')
    for n in z.namelist():
        if re.match(r'word/theme/theme\d*\.xml$', n):
            t = z.read(n).decode('utf-8')
            for f in sorted(set(re.findall(r'typeface="([^"]*)"', t)) - ok - {''}): bad.append(f'{n} 用了 {f}')
    return bad
