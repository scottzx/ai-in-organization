#!/usr/bin/env python3
"""读回 docx 逐项核对格式。用法: python3 check_docx.py [样张.docx] [-o 检查清单.md] [--style style.yaml]"""
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
    ap.add_argument('docx', nargs='?', default=OUT_DIR / '样张-上册.docx')
    ap.add_argument('-o', '--output', default=OUT_DIR / '检查清单-上册.md')
    ap.add_argument('--style', default=HERE / 'style.yaml')
    ap.add_argument('--pdf', default=None, help='同时用 pdftotext 检查该 PDF 中的本书版本号')
    ap.add_argument('--print', dest='print_edition', action='store_true', default=os.environ.get('BOOK_EDITION') == 'print', help='--pdf 为印刷版：参考文献与来源行须带网址')
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.style).read_text('utf-8')); L = cfg['levels']; F = cfg['fonts']
    doc = Document(a.docx)
    _side = Path(a.docx).with_suffix('.build.json')
    unnumbered = sum(1 for x in json.loads(_side.read_text('utf-8')).get('chapters', []) if x.get('chapter') is None and '导读' in x.get('file', '').rsplit('/', 1)[-1] and re.match(r'^[A-Z]', x['file'].rsplit('/', 1)[-1])) if _side.exists() else 0
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
    cn = '一二三四五六七八九十'
    h_counts = {}; cap_seq = {}
    exact = Pt(F['line_spacing_exact_pt'])
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
            check(f'{key} 中文字体(eastAsia)={c["font"]}', front or ea == c['font'], where + f' 实为{ea}')
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
            m = re.match(r'^([图表]) ([0-9A-Z]+)-(\d+)', txt)
            check('图题/表题 编号“图/表 X-Y”', bool(m), where)
            if m:
                k = (m.group(1), m.group(2)); prev = cap_seq.get(k, 0)
                check('图题/表题 章内连续编号', int(m.group(3)) == prev + 1, where + f' 前一号为{prev}')
                cap_seq[k] = int(m.group(3))
                check('表题 有标题文字', len(txt.split('　', 1)) > 1, where + ' 仅有编号，缺表题')
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
    demote = json.loads(_side.read_text('utf-8')).get('demote') if _side.exists() else False
    if demote:
        dm_ch = json.loads(_side.read_text('utf-8')).get('demote_chapters'); dm_ch = {c for c in dm_ch if isinstance(c, int)} if dm_ch else None
        ch = sec = sub = n4 = 0; ch_t = ''; app_h2 = []; guides = sum(1 for x in json.loads(_side.read_text('utf-8'))['chapters'] if x.get('chapter') is None); seen = set()
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
    for si, s in enumerate(doc.sections):
        check('页眉 = 书名(配置 book.title)', s.header.paragraphs[0].text.strip() == cfg['book']['title'], f'第{si+1}节 实为“{s.header.paragraphs[0].text}”')
        check('页脚 含 PAGE 页码域', 'PAGE' in s.footer._element.xml, f'第{si+1}节')
    check('版权页 存在且含书名', any('Copyright' in p.text for p in doc.paragraphs) and any(cfg['book']['title'] in p.text and '书名' in p.text for p in doc.paragraphs), '未找到')
    bk = cfg['book']
    check('版权页 含著作权人/编著单位', any(bk['copyright_holder'] in p.text for p in doc.paragraphs) and any(('编著：' + bk['author']) in p.text for p in doc.paragraphs), '缺著作权人或编著单位')
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
    hints = {'中英文/数字间有空格': [], '数值范围用了“～”“-”“–”（应为一字线“—”）': []}
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
        check('图题格式“图X-Y　标题”且居中', bool(re.match(r'^图 ?\d+-\d+\u3000\S', p.text)) and eff_pf(p, 'alignment') == 1, p.text[:20])
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
        out += [f'### {k}：{len(v)} 处', '']
        out += [f'{n}. {x.replace("|","／")}' for n, x in enumerate(v, 1)] or ['无']
        out.append('')
    out += ['', '说明：扫描包含正文与表格内段落；扉页、版权页、目录页为特殊版式，仅核对字体与颜色。',
            '本机缺“黑体/楷体_GB2312/仿宋_GB2312”实体字体，此清单核对的是 docx 内的字体设定（Word 在装有这些字体的电脑上按设定显示）。']
    Path(a.output).write_text('\n'.join(out) + '\n', 'utf-8')
    print('\n'.join(out[:3])); return 1 if total_fail else 0

if __name__ == '__main__':
    raise SystemExit(main())
