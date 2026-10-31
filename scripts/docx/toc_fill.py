#!/usr/bin/env python3
"""目录预排：把 TOC 域的结果写成常见书籍样式（标题……页码，按层级缩进），页码取自 LibreOffice 排版结果。
目录域保留，Word 中“更新域”仍可重排；LibreOffice/PDF 直接显示预排结果。"""
import re, subprocess, tempfile, shutil
from pathlib import Path
from docx import Document
from docx.enum.text import WD_TAB_ALIGNMENT, WD_TAB_LEADER, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Emu
import indent_fix   # 顶格段落：firstLine=0 时 firstLineChars 也置 0（Word 中 Chars 优先）

def _font(run, east, latin, size, bold=False):
    run.font.size = Pt(size); run.font.bold = bold; run.font.name = latin
    rpr = run._r.get_or_add_rPr(); rf = rpr.find(qn('w:rFonts'))
    if rf is None: rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
    for a in ('w:ascii', 'w:hAnsi'): rf.set(qn(a), latin)
    rf.set(qn('w:eastAsia'), east)

class TocError(Exception): pass

N = lambda t: re.sub(r'[\s\u3000\u00a0]', '', t)

def pdf_pages(docx, tmp):
    subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', tmp, str(docx)], capture_output=True, timeout=600)
    pdf = Path(tmp) / (Path(docx).stem + '.pdf')
    info = subprocess.run(['pdfinfo', pdf], capture_output=True, text=True) if pdf.exists() else None
    m = re.search(r'Pages:\s+(\d+)', info.stdout) if info is not None else None
    if not m:   # 出版审读 #78 P2③：LibreOffice 未出 PDF 或 pdfinfo 无输出时明确报错，不再 AttributeError
        raise TocError(f'目录预排失败：{"LibreOffice 未生成 " + pdf.name if info is None else "pdfinfo 无页数输出（" + (info.stderr.strip()[:200] or "空输出") + "）"}')
    n = int(m.group(1))
    out = []
    for i in range(1, n + 1):
        t = subprocess.run(['pdftotext', '-f', str(i), '-l', str(i), '-layout', pdf, '-'], capture_output=True, text=True).stdout
        lines = [l.strip() for l in t.splitlines() if l.strip()]
        out.append((lines[-1] if lines else '', N(t)))
    return out, pdf

def fill(docx_path, cfg, keep_pdf=None):
    doc = Document(docx_path)
    body = doc.paragraphs
    tp = next(p for p in body if 'TOC \\o' in ''.join(t.text or '' for t in p._p.iter(qn('w:instrText'))))
    lv = int(cfg['toc']['levels'].split('-')[1])
    idx = [i for i, p in enumerate(body) if p._p is tp._p][0]
    heads = [(int(p.style.name[-1]), p.text.strip()) for p in body[idx + 1:] if p.style.name.startswith('Heading ') and p.style.name[-1].isdigit() and int(p.style.name[-1]) <= lv and p.text.strip()]
    sec = doc.sections[-1]; width = sec.page_width - sec.left_margin - sec.right_margin
    F = cfg['fonts']; body_font = cfg['levels']['body']['font']; h1_font = cfg['levels']['h1']['font']; latin = F.get('latin', 'Times New Roman')
    # 清掉占位文字，结束符移到最后一条
    xs = list(tp._p)
    sep = [k for k, e in enumerate(xs) if e.find(qn('w:fldChar')) is not None and e.find(qn('w:fldChar')).get(qn('w:fldCharType')) == 'separate'][0]
    end = xs[-1]; assert end.find(qn('w:fldChar')).get(qn('w:fldCharType')) == 'end'
    for e in xs[sep + 1:-1]: tp._p.remove(e)
    tp._p.remove(end)
    prev, runs = tp, []
    for k, (l, text) in enumerate(heads):
        q = OxmlElement('w:p'); prev._p.addnext(q)
        from docx.text.paragraph import Paragraph
        para = Paragraph(q, tp._parent)
        pf = para.paragraph_format
        pf.left_indent = Pt(24 * (l - 1)); pf.first_line_indent = Pt(0)
        pf.space_before = Pt(0); pf.space_after = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
        pf.line_spacing = Pt(F.get('line_spacing_exact_pt', 22))
        pf.tab_stops.add_tab_stop(Emu(width), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = para.add_run(text); _font(r, h1_font if l == 1 else body_font, latin, 12 if l < 3 else 10.5)
        r2 = para.add_run('\t'); _font(r2, body_font, latin, 12)
        r3 = para.add_run('0'); _font(r3, body_font, latin, 12 if l < 3 else 10.5)
        runs.append(r3); prev = para
    e = OxmlElement('w:r'); f = OxmlElement('w:fldChar'); f.set(qn('w:fldCharType'), 'end'); e.append(f); prev._p.append(e)
    indent_fix.fix(doc); doc.save(docx_path)
    tmp = tempfile.mkdtemp()
    pages, pdf = pdf_pages(docx_path, tmp)
    # 正文页：页脚为阿拉伯数字；按顺序查找标题
    bodyp = [(i, int(last), t) for i, (last, t) in enumerate(pages) if re.fullmatch(r'\d+', last)]
    ci, pos, miss = 0, 0, []
    for (l, text), r3 in zip(heads, runs):
        key = N(text)[:14]; found = None
        while ci < len(bodyp):
            j = bodyp[ci][2].find(key, pos)
            if j >= 0: found = bodyp[ci][1]; pos = j + len(key); break
            ci += 1; pos = 0
        if found is None: miss.append(text); ci, pos = max(0, ci - 1), 0; r3.text = '—'
        else: r3.text = str(found)
    indent_fix.fix(doc); doc.save(docx_path)
    shutil.rmtree(tmp, ignore_errors=True)
    return len(heads), miss


W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def _entries(root):
    """TOC 域内各条目段落：[(标题文字, 页码 w:t 元素)]。"""
    ps = list(root.iter(W + 'p')); out = []; inside = False
    for p in ps:
        if not inside:
            if any('TOC \\o' in (t.text or '') for t in p.iter(W + 'instrText')): inside = True
            continue
        ts = [t for t in p.iter(W + 't')]
        if len(ts) >= 2: out.append((''.join(t.text or '' for t in ts[:-1]), ts[-1]))
        if any(f.get(W + 'fldCharType') == 'end' for f in p.iter(W + 'fldChar')): break
    return out

def locate(pages, titles):
    """按顺序在正文页（页脚为阿拉伯数字）中找各标题，返回页码字符串列表（找不到为 '—'）。"""
    bodyp = [(int(last), t) for last, t in pages if re.fullmatch(r'\d+', last)]
    ci, pos, res = 0, 0, []
    for text in titles:
        key = N(text)[:14]; found = None
        while ci < len(bodyp):
            j = bodyp[ci][1].find(key, pos)
            if j >= 0: found = bodyp[ci][0]; pos = j + len(key); break
            ci += 1; pos = 0
        if found is None: ci, pos = max(0, ci - 1), 0; res.append('—')
        else: res.append(str(found))
    return res

def compare(docx_path, keep_pdf=None):
    """渲染成品，返回 [(标题, 目录页码, 实际页码)] 与 PDF 路径。"""
    import zipfile
    from lxml import etree
    root = etree.fromstring(zipfile.ZipFile(docx_path).read('word/document.xml'))
    ents = _entries(root)
    tmp = tempfile.mkdtemp(); pages, pdf = pdf_pages(docx_path, tmp)
    real = locate(pages, [e[0] for e in ents])
    if keep_pdf: shutil.copy2(pdf, keep_pdf)
    shutil.rmtree(tmp, ignore_errors=True)
    return [(e[0], e[1].text, r) for e, r in zip(ents, real)]

def recheck(docx_path, cfg=None, max_rounds=3):
    """出版审读 #108 复审 P2②：fill 预排时成品尚未嵌入字体、未清理包，LibreOffice 用的字形度量与成品不同，
    后半本分页会差 1 页。这里对成品包再渲染，直接改 document.xml 里的页码文字（不经 python-docx 重存），
    目录在罗马页码节，改数字不影响正文分页；重复至一致。"""
    import zipfile
    from lxml import etree
    fixed = 0
    for rnd in range(1, max_rounds + 1):
        res = compare(docx_path)
        if all(a == b for t, a, b in res): return {'ok': True, 'rounds': rnd, 'fixed': fixed}
        zi = zipfile.ZipFile(docx_path); items = [(n, zi.read(n)) for n in zi.namelist()]; zi.close()
        root = etree.fromstring(dict(items)['word/document.xml'])
        ents = _entries(root); real = [b for t, a, b in res]
        for (t, el), r in zip(ents, real):
            if el.text != r: el.text = r; fixed += 1
        data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        with zipfile.ZipFile(docx_path, 'w', zipfile.ZIP_DEFLATED) as zo:
            for n, b in items: zo.writestr(n, data if n == 'word/document.xml' else b)
    return {'ok': not [1 for t, a, b in compare(docx_path) if a != b], 'rounds': max_rounds, 'fixed': fixed}
