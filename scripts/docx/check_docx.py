#!/usr/bin/env python3
"""读回 docx 逐项核对格式。用法: python3 check_docx.py [企业数智化转型思路-上册.docx] [-o 检查清单.md] [--style style.yaml]"""
import json
import argparse, os, re, yaml
from pathlib import Path
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.enum.text import WD_LINE_SPACING, WD_ALIGN_PARAGRAPH

HERE = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get('DOCX_OUT_DIR', HERE.parent.parent / 'output' / 'docx'))
AL = {'left': (None, WD_ALIGN_PARAGRAPH.LEFT), 'center': (WD_ALIGN_PARAGRAPH.CENTER,),
      'justify': (WD_ALIGN_PARAGRAPH.JUSTIFY,), 'right': (WD_ALIGN_PARAGRAPH.RIGHT,)}

_GF = {}; _GF_USED = {}; _GF_BAD = []   # 回退字符统计（提示项）、白名单外的回退（不通过）
def gf_ok(text, want, ea):
    """缺字回退（glyph_fallback.py）：仅当该 run 的每个字都不在应有字体中、且改用的是 style.yaml fonts.glyph_fallback 中的字体时才算合格。"""
    import yaml
    cfg = yaml.safe_load(open(Path(__file__).resolve().parent / 'style.yaml', encoding='utf-8'))
    if ea not in (cfg.get('fonts', {}).get('glyph_fallback') or []): return False
    allow = set(cfg.get('fonts', {}).get('glyph_fallback_chars') or [])
    for ch in text:
        if ch not in allow: _GF_BAD.append(f'U+{ord(ch):04X} {ch}')
        else: _GF_USED[f'U+{ord(ch):04X} {ch}（{want}→{ea}）'] = _GF_USED.get(f'U+{ord(ch):04X} {ch}（{want}→{ea}）', 0) + 1
    if want not in _GF:
        import fonts_embed
        from fontTools.ttLib import TTFont
        f = fonts_embed.find_fonts([want], cfg).get(want)
        _GF[want] = set(TTFont(str(f['regular']), lazy=True).getBestCmap()) if f else None
    cm = _GF[want]
    return cm is not None and all(ord(ch) >= 0x80 and ord(ch) not in cm and ch in allow for ch in text)

def chain(obj_style):
    s = obj_style
    while s is not None: yield s; s = s.base_style

def rfont(el, attr):
    rpr = el.find(qn('w:rPr'))
    rf = rpr.find(qn('w:rFonts')) if rpr is not None else None
    return rf.get(qn('w:' + attr)) if rf is not None else None

def eff_run(run, para):
    """返回 (eastAsia, ascii, size_pt, bold, color)，按 run -> 段落样式链 -> 文档默认 解析。"""
    def get(fn):
        v = fn(run)
        if v is not None: return v
        for s in chain(para.style):
            v = fn(s)
            if v is not None: return v
        return None
    ea = get(lambda o: rfont(o.element if hasattr(o, 'element') and not hasattr(o, '_r') else o._r, 'eastAsia'))
    asc = get(lambda o: rfont(o.element if hasattr(o, 'element') and not hasattr(o, '_r') else o._r, 'ascii'))
    size = get(lambda o: o.font.size)
    bold = get(lambda o: o.font.bold)
    color = get(lambda o: o.font.color.rgb if o.font.color and o.font.color.type else None)
    return ea, asc, size.pt if size else None, bool(bold), str(color) if color else None

def eff_pf(para, attr):
    v = getattr(para.paragraph_format, attr)
    if v is not None: return v
    for s in chain(para.style):
        v = getattr(s.paragraph_format, attr)
        if v is not None: return v
    return None

def classify(p, in_table):
    sn = p.style.name
    if in_table: return 'table'
    if sn.startswith('Heading '): return 'h' + sn[-1]
    if sn == 'Caption': return 'caption'
    if sn == 'Normal' and re.match(r'^(资料来源|数据来源)：', p.text): return None   # 图下来源注，单独样式口径
    if sn == 'Normal': return 'body'
    return None

# 本书版本号检查（Scott 口径：正文、版权页、Word/PDF 均不印本书版本号，版本只记在 CHANGELOG）
VER_RE = re.compile(r'初稿 ?v\d|(?<![A-Za-z0-9/._\-])v\d+\.\d+(?![\d.])')
VER_URL = re.compile(r'(https?://|www\.)\S+')
VER_ALLOW = [re.compile(x) for x in (r'CC BY[\w\- ]*\d+\.\d+', r'arXiv[:：]?\s*\S*v\d', r'\d{4}\.\d{4,5}v\d')]
VER_REF = re.compile(r'^\s*(\[\d+\]|［\d+］|\d+\.\s|参考(文献|资料)|资料来源|数据来源|引用[:：]|注[:：\d])|访问日期')
def version_hits(text):
    """返回本书版本号命中片段；网址、参考文献/引用行、白名单内的外部版本号放行。"""
    hits = []
    for line in text.splitlines():
        if VER_REF.search(line): continue
        t = VER_URL.sub(' ', line)
        for rx in VER_ALLOW: t = rx.sub(' ', t)
        for m in VER_RE.finditer(t):
            hits.append(t[max(0, m.start()-10):m.end()+6].strip())
    return hits

def pdf_version_hits(path):
    import subprocess
    txt = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(path), '-'], capture_output=True, text=True, check=True).stdout
    meta = subprocess.run(['pdfinfo', '-enc', 'UTF-8', str(path)], capture_output=True, text=True).stdout
    out = [f'第{n}页：{h}' for n, page in enumerate(txt.split('\f'), 1) for h in version_hits(page)]
    out += [f'PDF属性：{h}' for h in version_hits(meta)]
    return out

COPYRIGHT_MARKERS_DEFAULT = ['版权页', '版权所有', '著作权人']   # 单独的“CC BY”“知识共享”不算（中册附录B 图源索引表多处出现）
def pdf_url_hits(path, copyright_markers=None):
    """PDF 文字层中的网址按形态分类：印刷版补印的“（https…）”、参考文献原文著录的“. https…”、
    版权页上的网址（CC 许可协议、项目仓库地址，总编辑定为允许范围），其余算正文裸链。"""
    markers = [re.sub(r'\s+', '', m) for m in (copyright_markers or COPYRIGHT_MARKERS_DEFAULT)]
    import subprocess
    txt = subprocess.run(['pdftotext', '-enc', 'UTF-8', str(path), '-'], capture_output=True, text=True, check=True).stdout
    pages, allow = [], []   # allow：版权页在拼接文本中的 [起, 止) 区间
    for pg in txt.split('\f'):   # 去掉页眉（书名＋篇名两行）与页码，避免跨页网址被页眉隔开
        ls = [l for l in pg.splitlines() if l.strip()]
        if len(ls) > 3: ls = ls[2:]
        if ls and re.fullmatch(r'\s*[\divxlcIVXLC]+\s*', ls[-1]): ls = ls[:-1]
        seg = re.sub(r'\s+', '', ''.join(ls))
        start = sum(len(x) for x in pages)
        if any(mk in seg for mk in markers): allow.append((start, start + len(seg)))
        pages.append(seg)
    txt = ''.join(pages)
    printed, literal, bare, copyr = [], [], [], []
    for m in re.finditer(r'https?://', txt):
        pre = txt[max(0, m.start() - 1):m.start()]; ctx = txt[max(0, m.start() - 30):m.start() + 50]
        if any(a <= m.start() < b for a, b in allow): copyr.append(ctx); continue
        # 两端对齐的短行里 pdftotext 可能把“（”提到同行前面（如“[1]（Huawei．…报告https…”），回看 40 字内未闭合的“（”也算补印
        back = txt[max(0, m.start() - 40):m.start()]
        if pre != '（' and '（' in back and '）' not in back[back.rfind('（'):]: pre = '（'
        (printed if pre == '（' else literal if pre == '.' else bare).append(ctx)
    return printed, literal, bare, copyr

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('docx', nargs='?', default=OUT_DIR / '企业数智化转型思路-上册.docx')
    ap.add_argument('-o', '--output', default=OUT_DIR / '检查清单-上册.md')
    ap.add_argument('--style', default=HERE / 'style.yaml')
    ap.add_argument('--pdf', default=None, help='同时用 pdftotext 检查该 PDF 中的本书版本号')
    ap.add_argument('--print', dest='print_edition', action='store_true', default=os.environ.get('BOOK_EDITION') == 'print', help='--pdf 为印刷版：参考文献与来源行须带网址')
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.style).read_text('utf-8')); L = cfg['levels']; F = cfg['fonts']
    doc = Document(a.docx)
    _side = Path(a.docx).with_suffix('.build.json')
    BJ = json.loads(_side.read_text('utf-8')) if _side.exists() else {}   # build.json 只读一次
    _chaps = BJ.get('chapters', [])
    # 「导言」只允许来自某册 style.yaml volumes.<vol>.front 的册首篇目（如下册 00-导言.md）；以 build.json 实际收入的篇目为准，
    # 并核对每个「导言」一级标题确是该 front 篇目（按源稿首个 # 标题比对），不只核数量
    import unicodedata
    NFC = lambda x: unicodedata.normalize('NFC', x)
    _front = {NFC(f"{v['dir']}/{f}") for v in cfg.get('volumes', {}).values() if isinstance(v, dict) and v.get('dir') for f in v.get('front', [])}
    _repo = Path(os.environ.get('BOOK_REPO', HERE.parent.parent))
    def _h1(rel):
        fp = _repo / rel
        t = fp.read_text('utf-8') if fp.exists() else ''
        m = re.search(r'^#\s+(.+?)\s*$', t, re.M)
        return re.sub(r'[\s\u3000]', '', m.group(1)) if m else None
    front_queue = [_h1(x['file']) for x in _chaps if x.get('chapter') is None and NFC(x.get('file', '')) in _front]
    unnumbered = sum(1 for x in _chaps if x.get('chapter') is None and '导读' in x.get('file', '').rsplit('/', 1)[-1] and re.match(r'^[A-Z]', x['file'].rsplit('/', 1)[-1]))
    items = {}  # 检查项 -> [总数, 失败位置列表]
    def check(name, ok, where):
        it = items.setdefault(name, [0, []]); it[0] += 1
        if not ok: it[1].append(where)
    # 收集段落（含表格内），并记录所在章
    paras = [(p, False) for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                paras += [(p, True) for p in c.paragraphs]
    chapter = '前置'; body_started = False
    app_letter = None   # 当前一级标题若为“附录X　…”，记其字母；题注只在附录内可用字母，且须与本附录字母一致
    in_front = False; front_caps = []; front_no = 0   # 当前一级标题是否为 front 篇目的「导言」；front 篇目内题注；第几个 front 篇目（每篇“导”号单独连续）
    cn = '一二三四五六七八九十'
    h_counts = {}; cap_seq = {}
    exact = Pt(F['line_spacing_exact_pt'])
    BODY_INDENT_CHARS = 2   # Scott 2026-10-29 确认：正文首行缩进 4 个英文字符＝2 个中文字符
    check(f'style.yaml 正文首行缩进={BODY_INDENT_CHARS}字符（4 个英文字符）', L['body'].get('first_line_chars') == BODY_INDENT_CHARS, f"style.yaml levels.body.first_line_chars 为 {L['body'].get('first_line_chars')}")
    _ns = doc.styles['Normal'].element.pPr; _ni = _ns.find(qn('w:ind')) if _ns is not None else None
    check(f'Normal 样式首行缩进={BODY_INDENT_CHARS}字符（firstLineChars={BODY_INDENT_CHARS * 100}）', _ni is not None and _ni.get(qn('w:firstLineChars')) == str(BODY_INDENT_CHARS * 100) and _ni.get(qn('w:firstLine')) == str(int(L['body']['size_pt'] * BODY_INDENT_CHARS * 20)), f'Normal 实为 {None if _ni is None else dict(_ni.attrib)}')
    for idx, (p, intab) in enumerate(paras):
        key = classify(p, intab)
        txt = p.text.strip()
        if key == 'h1': chapter = txt[:14]; body_started = True
        where = f'段{idx+1}〔{chapter}〕“{txt[:18]}”'
        if not txt or key is None: continue
        c = L[key]
        # 前置页（扉页/版权页/目录）中的 Normal 段为特殊排版，字号不按正文检查
        front = not body_started and key == 'body'
        for r in p.runs:
            if not r.text.strip(): continue
            ea, asc, size, bold, color = eff_run(r, p)
            check(f'{key} 中文字体(eastAsia)={c["font"]}', front or ea == c['font'] or gf_ok(r.text, c['font'], ea), where + f' 实为{ea}')
            check(f'全部 西文字体={F["latin"]}', asc == F['latin'], where + f' 实为{asc}')
            if not front:
                check(f'{key} 字号={c["size_pt"]}pt', size == c['size_pt'], where + f' 实为{size}')
                check(f'{key} 加粗={c["bold"]}', bold == c['bold'] or (key in ('table', 'body') and bold), where + f' 实为{bold}')
            check(f'全部 文字颜色=#{F["color"]}', color == F['color'], where + f' 实为{color}')
        # 超链接颜色
        for h in p._p.findall(qn('w:hyperlink')):
            for col in h.iter(qn('w:color')):
                check('超链接 颜色=黑色', col.get(qn('w:val')).upper() == F['color'], where)
        if front: continue
        check('全部 行距=固定值%gpt' % F['line_spacing_exact_pt'],
              eff_pf(p, 'line_spacing_rule') == WD_LINE_SPACING.EXACTLY and eff_pf(p, 'line_spacing') == exact,
              where + f' 实为{eff_pf(p, "line_spacing_rule")}/{eff_pf(p, "line_spacing")}')
        sb, sa = eff_pf(p, 'space_before'), eff_pf(p, 'space_after')
        check('全部 段前段后=0', (sb or 0) == 0 and (sa or 0) == 0, where + f' 实为{sb}/{sa}')
        fi = eff_pf(p, 'first_line_indent') or 0
        if key == 'body':
            want = Pt(c['size_pt'] * c['first_line_chars'])
            ind = p._p.pPr.find(qn('w:ind')) if p._p.pPr is not None else None
            chars = ind.get(qn('w:firstLineChars')) if ind is not None else None
            check(f'body 首行缩进={c["first_line_chars"]}字符', fi == want and chars == str(c['first_line_chars'] * 100), where + f' 实为{fi}/{chars}')
        elif key.startswith('h') or key == 'caption':
            ind = p._p.pPr.find(qn('w:ind')) if p._p.pPr is not None else None
            chars = ind.get(qn('w:firstLineChars')) if ind is not None else None
            check(f'{key} 不缩进', fi == 0 and (eff_pf(p, 'left_indent') or 0) == 0 and chars in (None, '0'), where + f' 实为{fi}/{chars}')
        if key != 'table':
            check(f'{key} 对齐={c["align"]}', eff_pf(p, 'alignment') in AL[c['align']], where + f' 实为{eff_pf(p, "alignment")}')
        # 编号
        if key == 'h1':
            ok = bool(re.match(r'^(第[一二三四五六七八九十]+章　\S|导论|结语|附录[A-Z])', txt))
            in_front = False
            _ma = re.match(r'^附录([A-Z])', txt); app_letter = _ma.group(1) if _ma else None
            if not ok and txt.startswith('导言') and front_queue:   # 仅 front 篇目可用「导言」，且须是名单上的下一篇
                exp_h1 = front_queue.pop(0)
                if exp_h1 is None or re.sub(r'[\s\u3000]', '', txt) == exp_h1: ok = True; in_front = True; front_no += 1
            if not ok and unnumbered > 0 and not txt.startswith('第'): unnumbered -= 1; ok = True   # 门类导读入口，不编章号
            check('h1 编号格式“第X章　标题”(中文数字)', ok, where)
            m = re.match(r'^第([一二三四五六七八九十]+)章', txt)
            cur = m.group(1) if m else txt[:3]; h_counts = {'cur': cur, 'n': {}}
            if m:
                exp = h_counts.setdefault('order', None)
        elif key in ('h2', 'h3', 'h4') and re.match(r'^[0-9A-Z]', txt):
            m = re.match(r'^((?:\d+|[A-Z])(?:\.\d+){%d}) ' % (int(key[1]) - 1), txt)
            check(f'{key} 编号层级“X.Y{".Z" * (int(key[1]) - 2)}”', bool(m), where)
        if key == 'caption':
            # 章号为 1 起的数字，或附录内本附录的字母（如附录A 内“图 A-1”）；front 篇目（导言）内只能用“导”（图导-N／表导-N）；“0”一律不合格
            m = re.match(r'^([图表]) ?(导|[1-9]\d*|[A-Z])-(\d+)', txt)
            if m and (m.group(2) == '导') != in_front: m = None
            if m and re.fullmatch(r'[A-Z]', m.group(2)) and m.group(2) != app_letter: m = None   # 字母号只在本附录内、且与附录字母一致
            if m and in_front: front_caps.append(p._p)
            check('图题/表题 编号“图/表 X-Y”（front 篇目为“图/表 导-Y”）', bool(m), where)
            if m:
                k = (m.group(1), m.group(2), front_no if in_front else 0); prev = cap_seq.get(k, 0)
                check('图题/表题 章内连续编号', int(m.group(3)) == prev + 1, where + f' 前一号为{prev}')
                cap_seq[k] = int(m.group(3))
                check('表题 有标题文字', len(txt.split('　', 1)) > 1, where + ' 仅有编号，缺表题')
    # 题注、表格文字五号（Scott 2026-10-30 定）：固定 10.5pt，不只跟 style.yaml
    WUHAO = 10.5
    check('style.yaml 图题表题/表格文字=五号（10.5pt）', L['caption']['size_pt'] == WUHAO and L['table']['size_pt'] == WUHAO, f"caption {L['caption']['size_pt']} / table {L['table']['size_pt']}")
    for idx, (p, intab) in enumerate(paras):
        k = classify(p, intab)
        if k not in ('caption', 'table'): continue
        for r in p.runs:
            if not r.text.strip(): continue
            size = eff_run(r, p)[2]
            check('图题/表题 字号=五号（10.5pt）' if k == 'caption' else '表格文字 字号=五号（10.5pt）', size == WUHAO, f'段{idx+1}“{p.text.strip()[:18]}” 实为{size}')
    for sn in ('Caption', '表格文字'):
        sz = doc.styles[sn].font.size if sn in [x.name for x in doc.styles] else None
        check('Caption/表格文字 样式字号=五号（10.5pt）', sz is not None and sz.pt == WUHAO, f'{sn} 实为{sz.pt if sz else None}')
    # 目录页标题“目　录”：字体、字号、加粗
    tt = L.get('toc_title', {})
    for idx, (p, intab) in enumerate(paras):
        if re.sub(r'\s|　', '', p.text) == '目录' and not intab:
            for r in p.runs:
                if not r.text.strip(): continue
                ea, asc, size, bold, color = eff_run(r, p)
                check(f'目录页标题 字体={tt.get("font")}/字号={tt.get("size_pt")}pt', ea == tt.get('font') and size == tt.get('size_pt'), f'段{idx+1} 实为{ea}/{size}')
                check(f'目录页标题 加粗={tt.get("bold", False)}', bold == bool(tt.get('bold', False)), f'段{idx+1} 实为{bold}')
    # 目录条目、图下来源注：行距固定值、段前段后 0
    for idx, (p, intab) in enumerate(paras):
        sn = p.style.name; txt = p.text.strip()
        if not txt: continue
        kind = 'TOC 条目' if sn.startswith('TOC') or ('\t' in p.text and any(t.get(qn('w:leader')) == 'dot' for t in p._p.iter(qn('w:tab')))) else ('图下来源注' if sn == 'Normal' and re.match(r'^(资料来源|数据来源)：', txt) else None)
        if not kind: continue
        check(f'{kind} 行距=固定值%gpt' % F['line_spacing_exact_pt'], eff_pf(p, 'line_spacing_rule') == WD_LINE_SPACING.EXACTLY and eff_pf(p, 'line_spacing') == exact, f'段{idx+1}“{txt[:18]}” 实为{eff_pf(p, "line_spacing_rule")}/{eff_pf(p, "line_spacing")}')
        sb, sa = eff_pf(p, 'space_before'), eff_pf(p, 'space_after')
        check(f'{kind} 段前段后=0', (sb or 0) == 0 and (sa or 0) == 0, f'段{idx+1}“{txt[:18]}”')
        for r in p.runs:
            if not r.text.strip(): continue
            ea, asc, size, bold, color = eff_run(r, p)
            check(f'{kind} 文字颜色=#{F["color"]}', color == F['color'], f'段{idx+1}')
            check(f'{kind} 中文字体已设(eastAsia)', bool(ea), f'段{idx+1}')
    # 章号连续
    h1 = [p.text for p in doc.paragraphs if p.style.name == 'Heading 1' and p.text.startswith('第')]
    nums = [re.match(r'第(.+?)章', t).group(1) for t in h1]
    from build_docx import cn_num
    CNV = {cn_num(i): i for i in range(1, 100)}
    seq = [CNV.get(x) for x in nums]
    start = seq[0] if seq else 1
    check('h1 章号连续且每章只印一次（全书连续编号，自首章起）', seq == list(range(start, start + len(seq))), f'实为 {nums}')
    # 各级标题编号层次（中册降级版式：X.Y / X.Y.Z / （n））
    demote = BJ.get('demote', False)
    if demote:
        dm_ch = BJ.get('demote_chapters'); dm_ch = {c for c in dm_ch if isinstance(c, int)} if dm_ch else None
        ch = sec = sub = n4 = 0; ch_t = ''; app_h2 = []; guides = sum(1 for x in _chaps if x.get('chapter') is None); seen = set()
        for i, p in enumerate(doc.paragraphs):
            sn, t = p.style.name, p.text.strip(); w = f'段{i+1}「{t[:24]}」'
            if sn == 'Heading 1':
                m = re.match(r'^第(.+?)章', t); ch = CNV.get(m.group(1)) if m else t[:3]; ch_t = t; sec = sub = n4 = 0
                if dm_ch is not None and isinstance(ch, int) and ch not in dm_ch: ch = None   # 合订本中未降级的章（上册）不按降级版式核
            elif isinstance(ch, str) and sn == 'Heading 2' and re.match(r'^附录[A-Z]', ch_t):
                L_ = ch_t[2]; m = re.match(r'^([A-Z])\.(\d+) \S', t)
                check('附录 h2 编号为“A.Y”且字母=所在附录', bool(m) and m.group(1) == L_, w)
                if m:
                    check('附录 h2 A.Y 连续（自1起）', int(m.group(2)) == sec + 1, w + f' 前一节{sec}'); sec = int(m.group(2))
                    check('附录 h2 无手写“一、”等序号残留', not re.match(r'^[A-Z]\.\d+ ([一二三四五六七八九十]+、|第.+节)', t), w)
                    app_h2.append(t)
            elif not isinstance(ch, int): continue   # 附录三级以下按原稿层次
            elif sn == 'Heading 2':
                m = re.match(r'^(\d+)\.(\d+) \S', t); sub = n4 = 0
                if not m:
                    ok = guides > 0; guides -= 1
                    check('h2 不编号者仅为门类导读页', ok, w); continue
                check('h2 “X.Y”章号=所在章', int(m.group(1)) == ch, w)
                check('h2 X.Y 章内连续（自1起）', int(m.group(2)) == sec + 1, w + f' 前一节{sec}'); sec = int(m.group(2))
                check('h2/h3 编号全书无重复', t.split(' ')[0] not in seen, w); seen.add(t.split(' ')[0])
            elif sn == 'Heading 3':
                m = re.match(r'^(\d+)\.(\d+)\.(\d+) \S', t); n4 = 0
                if not m: check('h3 不编号者仅为“参考资料”', t in ('参考资料', '参考文献', '资料来源'), w); continue
                check('h3 “X.Y.Z”前缀=所在节', (int(m.group(1)), int(m.group(2))) == (ch, sec), w)
                check('h3 X.Y.Z 节内连续（自1起）', int(m.group(3)) == sub + 1, w + f' 前一项{sub}'); sub = int(m.group(3))
                check('h2/h3 编号全书无重复', t.split(' ')[0] not in seen, w); seen.add(t.split(' ')[0])
            elif sn == 'Heading 4':
                m = re.match(r'^（(\d+)）\S', t)
                check('h4 用“（n）”或不编号，不用 X.Y.Z', not re.match(r'^\d+\.\d+', t), w)
                if m: check('h4（n） 三级内连续（自1起）', int(m.group(1)) == n4 + 1, w + f' 前一项{n4}'); n4 = int(m.group(1))
        if app_h2:
            toc2 = [p.text for p in doc.paragraphs if p.style.name != 'Heading 2' and re.match(r'^[A-Z]\.\d+ .*\t\S+$', p.text)]
            check('目录列到附录 A.Y（每个附录二级标题都进目录，带页码）', all(any(x.startswith(h + '\t') for x in toc2) for h in app_h2), f'缺 {[h for h in app_h2 if not any(x.startswith(h + chr(9)) for x in toc2)]}')
    caps = [p.text.split('　')[0].replace(' ', '') for p in doc.paragraphs if p.style.name == 'Caption' and re.match(r'^[图表] ', p.text)]
    dups = sorted({c for c in caps if caps.count(c) > 1})
    check('图号/表号 全书无重复', not dups, f'重复：{dups}')
    import re as _re
    check('跨文件引用 无未解析', not any(_re.search(r'【[图表]引用错误：', p.text) or _re.search(r'\{\{(fig|tab):', p.text) for p in doc.paragraphs), '正文中有【引用错误】或未替换的 {{fig:}}/{{tab:}}')
    # 附录字母/附录图表号引用：正文（不含标题、目录、题注）中的“附录X”须有该附录的一级标题，“表X-n/图X-n”须有对应题注（合订本附录字母重排后不得悬空）
    app_heads = {m.group(1) for p in doc.paragraphs if p.style.name == 'Heading 1' for m in [_re.match(r'^附录([A-Z])', p.text)] if m}
    cap_set = set(caps)
    for i, (p, _t) in enumerate(paras):
        if p.style.name.startswith(('Heading', 'TOC', 'toc')) or p.style.name == 'Caption' or '\t' in p.text: continue
        for m in _re.finditer(r'附录\s?([A-Z])(?![A-Za-z])', p.text):
            check('附录字母引用 有对应附录（不悬空）', m.group(1) in app_heads, f'段{i+1}「{p.text[max(0, m.start()-12):m.end()+12]}」')
        for m in _re.finditer(r'([图表])\s?([A-Z])\s?-\s?(\d+)', p.text):
            check('附录字母引用 有对应附录（不悬空）', f'{m.group(1)}{m.group(2)}-{m.group(3)}' in cap_set, f'段{i+1}「{m.group(0)}」')
    check('附录字母引用 有对应附录（不悬空）', True, '')   # 无引用时也列出本项
    import indent_fix   # Word 中 firstLineChars 优先于 firstLine：顶格段落须同时为 0
    _bad = indent_fix.offenders(doc)
    check('首行缩进为 0 的段落 firstLineChars 也为 0（含样式继承）', not _bad, f'{len(_bad)} 段：' + '；'.join(f'{q.style.name}「{q.text[:12]}」' for q in _bad[:10]))
    web = []
    NAVW = r'(上册|中册|下册|全书)?(目录|索引|首页|研究报告|行业解决方案|企业案例|案例汇编)|上一章|下一章|返回|行业分篇说明|行业资料库'
    for i, p in enumerate(doc.paragraphs):
        t = p.text.strip(); segs = [x.strip() for x in re.split(r'\s*[·｜|]\s*', t)] if t else []
        if re.match(r'^一芥智能研究院｜.*｜', t) or (segs and len(t) < 160 and '。' not in t and (len(segs) >= 2 and all(0 < len(x) <= 40 for x in segs) and any(re.fullmatch(NAVW, x) for x in segs) or re.fullmatch(NAVW, t))):
            web.append(f'段{i+1}「{t[:30]}」')
    check('无网页导航行/“一芥智能研究院｜…”页眉行（源稿须删除）', not web, '；'.join(web[:10]) + (f' 等{len(web)}处' if len(web) > 10 else ''))
    # 本书版本号：正文（含表格）、页眉页脚、文件属性
    vh = []
    for i, (p, _) in enumerate(paras):
        vh += [f'段{i+1}：{h}' for h in version_hits(p.text)]
    for si, sec in enumerate(doc.sections):
        for kind in ('header', 'first_page_header', 'even_page_header', 'footer', 'first_page_footer', 'even_page_footer'):
            hf = getattr(sec, kind)
            if hf.is_linked_to_previous and si: continue
            ts = [q.text for q in hf.paragraphs] + [q.text for t in hf.tables for r in t.rows for c in r.cells for q in c.paragraphs]
            vh += [f'节{si+1}{kind}：{h}' for x in ts for h in version_hits(x)]
    cp = doc.core_properties
    for attr in ('title', 'subject', 'keywords', 'comments', 'category', 'version', 'content_status', 'identifier', 'description' if hasattr(cp, 'description') else 'title'):
        v = getattr(cp, attr, None)
        if isinstance(v, str): vh += [f'属性{attr}：{h}' for h in version_hits(v)]
    check('Word 无本书版本号（正文/页眉页脚/文件属性；“初稿 vN”、独立“vN.N”）', not vh, '；'.join(vh[:10]) + (f' 等{len(vh)}处' if len(vh) > 10 else ''))
    if a.pdf:
        ph = pdf_version_hits(a.pdf)
        check(f'PDF 无本书版本号（{Path(a.pdf).name}）', not ph, '；'.join(ph[:10]) + (f' 等{len(ph)}处' if len(ph) > 10 else ''))
        pu, lu, bu, cu = pdf_url_hits(a.pdf, cfg.get('checks', {}).get('copyright_page_markers'))
        check(f'PDF 正文无裸链（网址只出现在参考文献/来源行与版权页；版权页放行 {len(cu)} 处）', not bu, '；'.join(bu[:5]) + (f' 等{len(bu)}处' if len(bu) > 5 else ''))
        if a.print_edition:
            check('PDF 印刷版：参考文献与来源行印出网址（题名（网址））', bool(pu), f'补印 {len(pu)} 处')
        else:
            check('PDF 电子版：不补印网址', not pu, '；'.join(pu[:5]))
    # 表格、图片居中
    from docx.enum.table import WD_TABLE_ALIGNMENT
    for i, t in enumerate(doc.tables):
        check('表格 居中', t.alignment == WD_TABLE_ALIGNMENT.CENTER, f'第{i+1}个表格')
    for i, p in enumerate(doc.paragraphs):
        if p._p.findall('.//' + qn('w:drawing')):
            check('图片 居中', p.alignment == WD_ALIGN_PARAGRAPH.CENTER, f'段{i+1}')
    # 目录、页眉页脚、版权页
    xml = doc.element.xml
    check('目录 TOC 域存在', 'TOC \\o' in xml, '未找到 TOC 域')
    # 分节：第1节封面＋版权页不印页眉页码；第2节目录小写罗马页码自 i 起；第3节起正文阿拉伯页码自 1 起（出版审读 d7b16e3 预审 P1-1）
    secs = doc.sections
    check('分节：封面版权页／目录／正文 三节', len(secs) >= 3, f'实为 {len(secs)} 节')
    def _pg(s_):
        g = s_._sectPr.find(qn('w:pgNumType')); return (g.get(qn('w:fmt')), g.get(qn('w:start'))) if g is not None else (None, None)
    for si, s in enumerate(secs):
        if si == 0:
            hx = s.header._element.xml if not s.header.is_linked_to_previous else ''
            fx = s.footer._element.xml if not s.footer.is_linked_to_previous else ''
            check('封面、版权页 不印页眉页码（第1节页眉页脚为本节专用空白部件）', not s.header.is_linked_to_previous and not s.footer.is_linked_to_previous
                  and not ''.join(q.text for q in s.header.paragraphs + s.footer.paragraphs).strip() and 'PAGE' not in hx + fx, '第1节页眉页脚有内容或无专用部件')
            continue
        check('页眉 = 书名(配置 book.title)', s.header.paragraphs[0].text.strip() == cfg['book']['title'], f'第{si+1}节 实为“{s.header.paragraphs[0].text}”')
        check('页脚 含 PAGE 页码域', 'PAGE' in s.footer._element.xml, f'第{si+1}节')
        if si == 1: check(f'目录节 页码{cfg["page"]["front_matter_page_format"]}自1起', _pg(s) == (cfg['page']['front_matter_page_format'], '1'), f'实为 {_pg(s)}')
        if si == 2: check('正文节 阿拉伯页码自1起（自第一篇，上册即导论）', _pg(s) == ('decimal', '1'), f'实为 {_pg(s)}')
    hparts = [s.header.part.partname for s in secs] if len(secs) >= 2 else []
    check('封面节页眉部件与后续各节不共用', len(hparts) < 2 or hparts[0] not in hparts[1:], f'{hparts}')
    # 跨页表（出版审读 #108 复审 P1）：首行重复表头、不跨页、与表身第 1 行同页；表身各行不加 cantSplit/keepNext
    for i, t in enumerate(doc.tables):
        tr = t.rows[0]._tr; trpr = tr.trPr
        check('表格 首行为重复表头（tblHeader）', trpr is not None and trpr.find(qn('w:tblHeader')) is not None, f'第{i+1}个表格')
        if len(t.rows) > 1:
            check('表格 表头与下行同页（keepNext）且不跨页（cantSplit）', trpr is not None and trpr.find(qn('w:cantSplit')) is not None and all(eff_pf(q, 'keep_with_next') for c in t.rows[0].cells for q in c.paragraphs), f'第{i+1}个表格')
            bad = [ri + 1 for ri, r in enumerate(t.rows) if ri > 0 and ((r._tr.trPr is not None and r._tr.trPr.find(qn('w:cantSplit')) is not None) or any(q.paragraph_format.keep_with_next for c in r.cells for q in c.paragraphs))]
            check('表格 表身各行不加 cantSplit/keepNext（防表题被挤成孤页）', not bad, f'第{i+1}个表格 第{bad[:5]}行')
    for p in doc.paragraphs:
        if p.style.name == 'Caption' and p.text.startswith('表'):
            check('表题 与下段同页（keepNext）', bool(eff_pf(p, 'keep_with_next')), p.text[:20])
    import package_clean   # 成品包：无 stylesWithEffects、无 Courier/Symbol 字体、样式无主题色
    pb = package_clean.audit(a.docx)
    check('成品包无 stylesWithEffects 部件及引用、无 Courier/Symbol 字体名、样式无主题色（themeColor）', not pb, '；'.join(pb))
    import zipfile
    with zipfile.ZipFile(a.docx) as _z: sc = package_clean.styles_color_issues(_z.read('word/styles.xml'))
    check('styles.xml 无非黑颜色、无底纹填充（未用的彩色/底纹内置样式已删）', not sc, '；'.join(sc))
    ZWC = '\u2060\u200b\u200c\u200d\ufeff'   # 正文、页眉页脚、脚注尾注都查（EPUB 搜索复制）
    with zipfile.ZipFile(a.docx) as _z:
        _parts = {n: _z.read(n).decode('utf-8') for n in _z.namelist()
                  if re.fullmatch(r'word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml', n)}
    zw = [f'{n[5:]} U+{ord(ch):04X} {x.count(ch)} 处' for n, x in sorted(_parts.items()) for ch in ZWC if ch in x]
    check('正文、页眉页脚、脚注尾注无零宽控制字符（U+2060/200B/200C/200D/FEFF，影响 EPUB 搜索复制）', not zw, '、'.join(zw))
    check('版权页 存在且含书名', any('Copyright' in p.text for p in doc.paragraphs) and any(cfg['book']['title'] in p.text and '书名' in p.text for p in doc.paragraphs), '未找到')
    bk = cfg['book']
    check('版权页 含著作权人', any(('著作权人：' + bk['copyright_holder']) in p.text for p in doc.paragraphs), '缺著作权人')
    TITLE = '《企业数智化转型思路》'   # Scott 2026-10-30 定
    check(f'书名={TITLE}（style.yaml、页眉、docx 属性 title）', bk['title'] == TITLE and cp.title == TITLE, f'style.yaml “{bk["title"]}” / 属性 “{cp.title}”')
    front_txt = [p.text for p in doc.paragraphs[:next((k for k, p in enumerate(doc.paragraphs) if p.style.name == 'Heading 1'), len(doc.paragraphs))]]
    check('研究院不单独署名（扉页/版权页无“编著”“研究院”，docx 属性 author/last_modified_by 为空）', 'author' not in bk and not cp.author and not cp.last_modified_by and not any(re.search(r'编著|研究院', t) for t in front_txt), f'author“{cp.author}” / 修改者“{cp.last_modified_by}” / 前置页：' + '；'.join(t[:20] for t in front_txt if re.search(r'编著|研究院', t)))
    URLS = ('github.com/scottzx', 'ai-in-organization')   # 官网、仓库地址只在版权页
    _toc = next((k for k, p in enumerate(doc.paragraphs) if any('TOC' in (x.text or '') for x in p._p.iter(qn('w:instrText')))), 0)
    _copy = next((k for k, p in enumerate(doc.paragraphs) if p.text.strip() == '版权声明'), _toc)
    hf = [q.text for s_ in doc.sections for h in (s_.header, s_.footer) for q in h.paragraphs]
    out_url = [f'段{k+1}' for k, (p, _) in enumerate(paras) if any(u in p.text for u in URLS) and not (_copy <= k < _toc)] + [f'页眉页脚“{t[:20]}”' for t in hf if any(u in t for u in URLS)]
    out_url += [f'超链接 {r.target_ref[:40]}' for r in doc.part.rels.values() if r.is_external and any(u in r.target_ref for u in URLS) and not any(u in p.text for p in doc.paragraphs[_copy:_toc] for u in URLS)]
    check('官网/仓库地址只在版权页（正文、页眉页脚、属性不出现）', not out_url and not any(u in (cp.title or '') + (cp.comments or '') for u in URLS), '；'.join(out_url[:10]))
    import fonts_embed   # 嵌入字体：settings 开 embedTrueTypeFonts，所用每种字体在 fontTable 有 embedRegular，odttf 解混淆后是有效字体
    on, fr, used = fonts_embed.verify(a.docx)
    bad = {k: v for k, v in fr.items() if v}
    check('Word 嵌入字体（embedTrueTypeFonts 已开；所用字体均有 odttf 部件且解混淆后有效）', on and not bad, ('未开 embedTrueTypeFonts；' if not on else '') + '；'.join(f'{k}：{v}' for k, v in bad.items()))
    import explicit_fonts   # docDefaults、主题、全部样式只用开源字体（出版审读 #78 P2①）
    efb = explicit_fonts.audit(a.docx, cfg)
    check('文档默认/主题/样式/fontTable 字体均为显式开源字体（无主题引用、无 Times New Roman/宋体/Courier 等；themeFontLang zh-CN）', not efb, '；'.join(efb))
    check('缺字回退仅限 style.yaml fonts.glyph_fallback_chars 白名单字符', not _GF_BAD, '；'.join(sorted(set(_GF_BAD))))
    # 脚注（真脚注 footnotes.xml）
    fpart = next((r.target_part for r in doc.part.rels.values() if r.reltype.endswith('/footnotes')), None)
    nref = len(doc.element.body.findall('.//' + qn('w:footnoteReference')))
    if fpart is None:
        check('脚注 真脚注（本稿无 [^n] 脚注时记 0 处）', nref == 0, f'正文有 {nref} 个脚注引用但缺 footnotes.xml')
    else:
        from lxml import etree
        root = etree.fromstring(fpart.blob); fc = L['footnote']
        notes = [n for n in root.findall(qn('w:footnote')) if int(n.get(qn('w:id'))) > 0]
        check('脚注 引用数=脚注数', nref == len(notes), f'引用{nref} / 脚注{len(notes)}')
        for n in notes:
            for r in n.iter(qn('w:r')):
                if r.find(qn('w:t')) is None: continue
                rf = r.find('.//' + qn('w:rFonts')); sz = r.find('.//' + qn('w:sz')); col = r.find('.//' + qn('w:color'))
                w = f'脚注{n.get(qn("w:id"))}'
                check(f'脚注 字体={fc["font"]}', rf is not None and rf.get(qn('w:eastAsia')) == fc['font'], w)
                check(f'脚注 字号={fc["size_pt"]}pt(五号)', sz is not None and int(sz.get(qn('w:val'))) == int(fc['size_pt'] * 2), w)
                check('脚注 颜色=黑色', col is not None and col.get(qn('w:val')).upper() == F['color'], w)
    # 提示项（不计入通过/不通过，仅供文字编辑修改；排版脚本不自动增删空格或替换连接号）
    # 缺字回退：按“种”（字符数）与“处”（逐字出现次数）分别统计（出版审读 #86 P2①）；无 build.json 时退回 check 端计数并注明（P2②）
    if 'glyph_fallback' in BJ:
        _gfi = sorted((BJ.get('glyph_fallback') or {}).items())
        gf_list = [f"{k}（{v['from']}→{v['to']}）：{v['count']} 处" for k, v in _gfi]
        gf_kinds, gf_total, gf_note = len(_gfi), sum(int(v['count']) for _, v in _gfi), ''
    else:
        _gfi = sorted(_GF_USED.items())
        gf_list = [f'{k}：{n} 处' for k, n in _gfi]
        gf_kinds, gf_total, gf_note = len({k.split('（')[0] for k, _ in _gfi}), sum(n for _, n in _gfi), '（无 build.json，次数仅供参考）'
    GF_KEY = '缺字回退字符（所用字体缺字形，改用已嵌入的开源字体）'
    hints = {'中英文/数字间有空格': [], '数值范围用了“～”“-”“–”（应为一字线“—”）': [], GF_KEY: gf_list}   # 次数以 build.json（glyph_fallback.fix 逐字计数）为准
    cur = '前置'
    for i, p in enumerate(doc.paragraphs):
        t = p.text
        if p.style.name == 'Heading 1': cur = t[:14]
        if p.style.name == 'Caption' or not t.strip() or cur == '前置': continue
        for m in re.finditer(r'[\u4e00-\u9fff，。；：、（）][ \u00a0]+[A-Za-z0-9]|[A-Za-z0-9%][ \u00a0]+[\u4e00-\u9fff，。；：、（）]', t):
            hints['中英文/数字间有空格'].append(f'段{i+1}〔{cur}〕…{t[max(0,m.start()-8):m.end()+8]}…')
        for m in re.finditer(r'\d+(?:\.\d+)?\s*[%％万亿元个天年月日小时分钟秒倍]?\s*[～~\-–]\s*\d+', t):
            if re.match(r'\d{4}-\d{1,2}(-\d{1,2})?$', m.group(0)) or re.search(r'https?://\S*$', t[:m.start()]): continue
            hints['数值范围用了“～”“-”“–”（应为一字线“—”）'].append(f'段{i+1}〔{cur}〕…{t[max(0,m.start()-8):m.end()+8]}…')
    # 目录页与分章
    from docx.oxml.ns import qn as _qn
    body = list(doc.element.body.iterchildren()); ps = doc.paragraphs
    toc_i = next((k for k, p in enumerate(ps) if any('TOC' in (x.text or '') for x in p._p.iter(_qn('w:instrText')))), None)
    check('目录域存在', toc_i is not None, '未找到 TOC 域')
    if toc_i is not None:
        heads = [p for p in ps[toc_i:] if p.style.name in ('Heading 1', 'Heading 2')]
        ents = []; k = toc_i
        while k < len(ps) and not ps[k].style.name.startswith('Heading'):
            if '\t' in ps[k].text: ents.append(ps[k])
            k += 1
        check('目录条目数与 1–2 级标题一致', len(ents) == len(heads), f'目录 {len(ents)} 条 / 标题 {len(heads)} 个')
        for e in ents:
            check('目录条目有引导点与页码', bool(re.search(r'\d+$', e.text)) and e._p.find('.//' + _qn('w:tab')) is not None and any(t.get(_qn('w:leader')) == 'dot' for t in e._p.iter(_qn('w:tab'))), e.text[:20])
        between = ps[toc_i:k]
        check('目录单独成节（目录后有分节符）', any(p._p.find('.//' + _qn('w:sectPr')) is not None for p in between), '目录与正文之间无分节符')
        first = True
        for p in ps[k:]:
            if p.style.name != 'Heading 1': continue
            pb = eff_pf(p, 'page_break_before')
            check('每章（一级标题）从新页开始', bool(pb) or first, p.text[:14]); first = False
    caps = [k for k, p in enumerate(ps) if p.style.name == 'Caption' and p.text.startswith('图')]
    for k in caps:
        p = ps[k]; nx = ps[k + 1].text.strip() if k + 1 < len(ps) else ''
        check('图题格式“图X-Y　标题”（front 篇目“图导-Y”）且居中', bool(re.match(r'^图 ?导-\d+\u3000\S' if any(p._p is e for e in front_caps) else r'^图 ?(?:[1-9]\d*|[A-Z])-\d+\u3000\S', p.text)) and eff_pf(p, 'alignment') == 1, p.text[:20])
        check('图题下一行为资料来源/数据来源', bool(re.match(r'^(资料来源|数据来源)', nx)), p.text[:20])
    # 输出
    total_fail = sum(1 for v in items.values() if v[1])
    out = [f'# 格式检查清单：{Path(a.docx).name}', '',
           f'依据：{Path(a.style).name}（Scott 已确认的格式）。共 {len(items)} 项，'
           f'{"全部通过" if not total_fail else f"{total_fail} 项不通过"}。', '',
           '| # | 检查项 | 检查次数 | 结果 | 不通过位置（最多列 10 处） |', '|---|---|---|---|---|']
    for i, (k, (n, fails)) in enumerate(items.items(), 1):
        out.append(f'| {i} | {k} | {n} | {"✅ 通过" if not fails else f"❌ 不通过 {len(fails)} 处"} | {"；".join(fails[:10]).replace("|","／") if fails else "—"} |')
    out += ['', '## 提示项（供文字编辑修改，不计入通过/不通过）', '']
    for k, v in hints.items():
        out += [f'### {k}：共 {gf_kinds} 种、合计 {gf_total} 处{gf_note}' if k == GF_KEY else f'### {k}：{len(v)} 处', '']
        out += [f'{n}. {x.replace("|","／")}' for n, x in enumerate(v, 1)] or ['无']
        out.append('')
    out += ['', '说明：扫描包含正文与表格内段落；扉页、版权页、目录页为特殊版式，仅核对字体与颜色。',
            '字体嵌入：' + ('、'.join(f'{k}{"✅" if not v else "❌" + v}' for k, v in fr.items()) or '无') + '。缺字体文件时构建如实不嵌入，不以其他字体替代。']
    Path(a.output).write_text('\n'.join(out) + '\n', 'utf-8')
    print('\n'.join(out[:3])); return 1 if total_fail else 0

if __name__ == '__main__':
    raise SystemExit(main())
