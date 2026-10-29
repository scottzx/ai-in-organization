#!/usr/bin/env python3
"""Markdown -> docx 排版脚本（《企业数智化转型研究报告》二次修订）。

用法:
  python3 build_docx.py                       # 默认：上册 -> 样张-上册.docx
  python3 build_docx.py --volume upper -o out.docx
  python3 build_docx.py --files a.md:9 b.md:10 -o 中册.docx   # 任意文件:新章号（null=不编号, A=附录）
  python3 build_docx.py --style style.yaml --repo <仓库根目录>   # 默认即本仓库，可用 BOOK_REPO 覆盖
格式参数全部在 style.yaml。只读取仓库，不写仓库。
支持：自动目录(TOC 域)、页眉书名、页脚页码、扉页+版权页、一级标题按新章号重编(中文数字)、
二级以下按“章.节.小节”重编、表格/图片自动编号“表 X-Y”“图 X-Y”、清除网页导航元素。
"""
from urllib.parse import unquote
import os, argparse, copy, fnmatch, json, re, shutil, sys
from docx.opc.part import Part
from docx.opc.packuri import PackURI
from lxml import etree
from pathlib import Path
import yaml
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Pt, Cm, RGBColor, Emu

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent          # 仓库根目录（scripts/docx 的上两级）
OUT_DIR = Path(os.environ.get('DOCX_OUT_DIR', REPO_ROOT / 'output' / 'docx'))
ALIGN = {'left': WD_ALIGN_PARAGRAPH.LEFT, 'center': WD_ALIGN_PARAGRAPH.CENTER,
         'justify': WD_ALIGN_PARAGRAPH.JUSTIFY, 'right': WD_ALIGN_PARAGRAPH.RIGHT}
CN = '零一二三四五六七八九'

def cn_num(n):
    n = int(n)
    if n < 10: return CN[n]
    if n < 20: return '十' + (CN[n % 10] if n % 10 else '')
    if n < 100: return CN[n // 10] + '十' + (CN[n % 10] if n % 10 else '')
    raise ValueError(n)

# ---------------- 低层 XML 工具 ----------------
def set_fonts(rpr_owner, east, latin):
    """rpr_owner: run/style 的 element；设置 ascii/hAnsi/cs/eastAsia 并去掉主题字体。"""
    rpr = rpr_owner.get_or_add_rPr()
    rf = rpr.find(qn('w:rFonts'))
    if rf is None:
        rf = OxmlElement('w:rFonts'); rpr.insert(0, rf)
    for a in ('w:asciiTheme', 'w:hAnsiTheme', 'w:eastAsiaTheme', 'w:cstheme'):
        if rf.get(qn(a)) is not None: del rf.attrib[qn(a)]
    rf.set(qn('w:ascii'), latin); rf.set(qn('w:hAnsi'), latin); rf.set(qn('w:cs'), latin)
    rf.set(qn('w:eastAsia'), east); rf.set(qn('w:hint'), 'eastAsia')

def fmt_font(font, element, east, latin, size, bold, color):
    font.name = latin
    set_fonts(element, east, latin)
    font.size = Pt(size); font.bold = bold; font.italic = False
    font.color.rgb = RGBColor.from_string(color)
    font.underline = False

def fmt_par(pf, cfg, align, first_chars=0, size=12):
    pf.space_before = Pt(cfg['fonts']['space_before_pt']); pf.space_after = Pt(cfg['fonts']['space_after_pt'])
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(cfg['fonts']['line_spacing_exact_pt'])
    pf.alignment = ALIGN[align]
    pf.left_indent = Pt(0); pf.right_indent = Pt(0)
    pf.first_line_indent = Pt(size * first_chars) if first_chars else Pt(0)

def set_first_line_chars(p_element_owner, chars):
    ppr = p_element_owner.get_or_add_pPr()
    ind = ppr.find(qn('w:ind'))
    if ind is None: ind = OxmlElement('w:ind'); ppr.append(ind)
    ind.set(qn('w:firstLineChars'), str(int(chars * 100)))

def add_field(paragraph, instr, placeholder=''):
    def fc(t):
        r = OxmlElement('w:r'); f = OxmlElement('w:fldChar'); f.set(qn('w:fldCharType'), t); r.append(f); return r
    p = paragraph._p
    p.append(fc('begin'))
    r = OxmlElement('w:r'); it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = f' {instr} '; r.append(it); p.append(r)
    p.append(fc('separate'))
    run = paragraph.add_run(placeholder)
    p.append(fc('end'))
    return run

# ---------------- 主体 ----------------
class Builder:
    def __init__(self, cfg, repo, registry=None):
        self.allow_web = False; self.fig_errors = []
        self.nav_hits, self.caption_hits, self.secmap, self.chapter_notes = [], [], {}, {}
        self.demote, self.host, self.members, self.whole_ch, self.sec, self.last_ch, self.whole, self.is_guide = {}, {}, {}, set(), {}, None, False, False
        self.cfg, self.repo = cfg, repo
        self.latin = cfg['fonts']['latin']; self.color = cfg['fonts']['color']
        self.doc = Document()
        captions = repo / 'scripts/pdf-table-captions.json'
        self.table_titles = json.loads(captions.read_text('utf-8')) if captions.exists() else {}
        self.xrefs = []
        self.chap_counters = {}      # 章号 -> [ntab, nfig]：同一章的多个篇目连续编号
        self.registry = registry if registry is not None else {}   # {('图'|'表', 题名): [编号...]}，上一轮收集，供 {{fig:}}/{{tab:}} 解析
        self.collect = {}            # 本轮收集
        self.ref_errors = []
        self.log = {'chapters': [], 'tables': [], 'figures': [], 'warnings': []}
        self.setup_styles(); self.setup_page()

    # 样式
    def setup_styles(self):
        st, L = self.doc.styles, self.cfg['levels']
        def mk(name, base_type=1):
            try: return st[name]
            except KeyError: return st.add_style(name, base_type)
        spec = {'Normal': 'body', 'Heading 1': 'h1', 'Heading 2': 'h2', 'Heading 3': 'h3', 'Heading 4': 'h4',
                'Caption': 'caption', '表格文字': 'table'}
        for name, key in spec.items():
            s = mk(name); c = L[key]
            fmt_font(s.font, s.element, c['font'], self.latin, c['size_pt'], c['bold'], self.color)
            fc = c.get('first_line_chars', 0)
            fmt_par(s.paragraph_format, self.cfg, c['align'], fc, c['size_pt'])
            if fc: set_first_line_chars(s.element, fc)
            if name.startswith('Heading'):
                s.paragraph_format.keep_with_next = True
                s.paragraph_format.page_break_before = bool(c.get('page_break_before'))
        for i in (1, 2, 3):
            s = mk(f'TOC {i}'); b = L['body']
            fmt_font(s.font, s.element, b['font'], self.latin, b['size_pt'], False, self.color)
            fmt_par(s.paragraph_format, self.cfg, 'left', 0, 12); s.paragraph_format.left_indent = Pt(12 * 2 * (i - 1))
        hl = mk('Hyperlink', 2)
        hl.font.color.rgb = RGBColor.from_string(self.color); hl.font.underline = False
        # 让 Word 打开时更新目录与页码域
        upd = OxmlElement('w:updateFields'); upd.set(qn('w:val'), 'true')
        self.doc.settings.element.append(upd)

    def setup_page(self):
        p = self.cfg['page']; s = self.doc.sections[0]
        s.page_width, s.page_height = Cm(21.0), Cm(29.7)
        s.top_margin, s.bottom_margin = Cm(p['margin_top_cm']), Cm(p['margin_bottom_cm'])
        s.left_margin, s.right_margin = Cm(p['margin_left_cm']), Cm(p['margin_right_cm'])
        self.decorate_section(s, p['front_matter_page_format'], restart=True)

    def decorate_section(self, s, fmt, restart):
        p = self.cfg['page']
        sect = s._sectPr
        pg = sect.find(qn('w:pgNumType'))
        if pg is None: pg = OxmlElement('w:pgNumType'); sect.append(pg)
        pg.set(qn('w:fmt'), fmt)
        if restart: pg.set(qn('w:start'), '1')
        s.header.is_linked_to_previous = False; s.footer.is_linked_to_previous = False
        hp = s.header.paragraphs[0]; hp.text = ''
        r = hp.add_run(self.cfg['book']['title'])
        self.style_run(r, p['header_font'], p['header_size_pt'])
        fmt_par(hp.paragraph_format, self.cfg, 'center'); hp.paragraph_format.line_spacing = Pt(p['header_size_pt'] * 1.5)
        # 页眉下框线
        ppr = hp._p.get_or_add_pPr(); bdr = OxmlElement('w:pBdr'); b = OxmlElement('w:bottom')
        for k, v in (('val', 'single'), ('sz', '6'), ('space', '1'), ('color', self.color)): b.set(qn('w:' + k), v)
        bdr.append(b); ppr.append(bdr)
        fp = s.footer.paragraphs[0]; fp.text = ''
        fmt_par(fp.paragraph_format, self.cfg, 'center'); fp.paragraph_format.line_spacing = Pt(p['footer_size_pt'] * 1.5)
        run = add_field(fp, 'PAGE', '1'); self.style_run(run, self.latin, p['footer_size_pt'])
        for r in fp.runs: self.style_run(r, self.latin, p['footer_size_pt'])

    def style_run(self, run, east, size, bold=None):
        fmt_font(run.font, run._r, east, self.latin, size, bool(bold), self.color)

    def lv(self, key): return self.cfg['levels'][key]

    def para(self, style, text='', key=None, align=None):
        p = self.doc.add_paragraph(style=style)
        key = key or {'Normal': 'body', 'Caption': 'caption', '表格文字': 'table'}.get(style, 'body')
        c = self.lv(key); fc = c.get('first_line_chars', 0) if key == 'body' else 0
        fmt_par(p.paragraph_format, self.cfg, align or c['align'], fc, c['size_pt'])
        if fc: set_first_line_chars(p._p, fc)
        if text: self.inline(p, text, key)
        return p

    # 行内 Markdown：**粗** *斜* `码` [文字](链接)
    TOK = re.compile(r'(\[\^[^\]]+\]|\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|(?<!\*)\*[^*\s][^*]*?\*(?!\*))')
    def inline(self, p, text, key, bold=False, allow_fn=True):
        c = self.lv(key)
        base_bold = bold or c['bold']
        text = re.sub(r'<a id="[^"]*"></a>', '', text)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = self.resolve_tokens(text)
        for part in self.TOK.split(text):
            if not part: continue
            b = base_bold
            mf = re.fullmatch(r'\[\^([^\]]+)\]', part)
            if mf:
                note = self.fn_defs.get(mf.group(1))
                if note is not None and allow_fn: self.add_footnote(p, note)
                else:
                    self.log['warnings'].append(f'脚注 [^{mf.group(1)}] 无定义，按原文保留')
                    r = p.add_run(part); self.style_run(r, c['font'], c['size_pt'], b)
                continue
            m = re.fullmatch(r'\[([^\]]+)\]\(([^)\s]+)\)', part)
            if part.startswith('**') and part.endswith('**') and len(part) > 4:
                self.inline(p, part[2:-2], key, True, allow_fn); continue
            if m:
                label, url = m.groups()
                if url.startswith('http'):
                    self.hyperlink(p, label, url, c, b)
                    if getattr(self, 'print_edition', False) and self.in_reference():   # 印刷版：参考文献/来源行补印网址
                        r = p.add_run('（' + url + '）'); self.style_run(r, c['font'], c['size_pt'], b)
                else:
                    self.inline(p, label, key, b, allow_fn)
                continue
            if part.startswith('`') and part.endswith('`'): part = part[1:-1]
            elif part.startswith('*') and part.endswith('*') and len(part) > 2: part = part[1:-1]
            r = p.add_run(part); self.style_run(r, c['font'], c['size_pt'], b)

    XTOK = re.compile(r'\{\{(fig|tab):([^{}]+)\}\}')
    def resolve_tokens(self, text):
        """跨文件引用：{{fig:图题}} / {{tab:表题}} → “图X-Y”/“表X-Y”，按全书图题（不含编号）精确匹配。"""
        def sub(m):
            kind = '图' if m.group(1) == 'fig' else '表'; t = m.group(2).strip()
            hits = self.registry.get((kind, norm_title(t)), [])
            where = getattr(self, 'cur_file', '?')
            if len(hits) == 1: return hits[0]['no']
            msg = (f'{where}: {{{{{m.group(1)}:{t}}}}} 未找到对应{kind}题' if not hits else
                   f'{where}: {{{{{m.group(1)}:{t}}}}} 匹配到多个{kind}：' + '、'.join(f"{h['no']}（{h['file']}）" for h in hits))
            self.ref_errors.append(msg)
            return f'【{kind}引用错误：{t}】'
        return self.XTOK.sub(sub, text)

    def hyperlink(self, p, label, url, c, bold):
        rid = (getattr(self, '_link_part', None) or p.part).relate_to(url, RT.HYPERLINK, is_external=True)
        h = OxmlElement('w:hyperlink'); h.set(qn('r:id'), rid)
        r = p.add_run(label); self.style_run(r, c['font'], c['size_pt'], bold)
        r.style = self.doc.styles['Hyperlink']
        r.font.color.rgb = RGBColor.from_string(self.color); r.font.underline = False
        r._r.getparent().remove(r._r); h.append(r._r); p._p.append(h)

    # 前置部分
    def front_matter(self):
        b = self.cfg['book']
        for _ in range(6): self.para('Normal', key='body', align='center')
        for text, size in ((b['title'], 22), (b['subtitle'], 18), ('', 12), (b['author'] + '　编著', 16), (b['edition'], 14), (b['date'], 14)):
            p = self.para('Normal', key='body', align='center')
            if text:
                r = p.add_run(text); self.style_run(r, self.lv('h1')['font'], size)
                p.paragraph_format.line_spacing = Pt(max(self.cfg['fonts']['line_spacing_exact_pt'], size * 1.6))
        self.page_break()
        # 版权页（置底，用空段推到页面下部）
        for _ in range(10): self.para('Normal', key='body')
        p = self.para('Normal', key='body', align='left'); p.paragraph_format.first_line_indent = Pt(0); set_first_line_chars(p._p, 0)
        r = p.add_run('版权声明'); self.style_run(r, self.lv('h1')['font'], 12, True)
        for line in self.cfg['copyright']:
            p = self.para('Normal', key='body', align='left'); p.paragraph_format.first_line_indent = Pt(0)
            set_first_line_chars(p._p, 0)
            r = p.add_run(line.format(title=b['title'], holder=b['copyright_holder'], author=b['author'])); self.style_run(r, self.lv('body')['font'], 10.5)
        self.page_break()
        # 目录
        p = self.para('Normal', key='body', align='center'); p.paragraph_format.first_line_indent = Pt(0); set_first_line_chars(p._p, 0)
        r = p.add_run('目　　录'); self.style_run(r, self.cfg['levels']['toc_title']['font'], self.cfg['levels']['toc_title']['size_pt'], self.cfg['levels']['toc_title'].get('bold', False))
        p = self.para('Normal', key='body', align='left'); p.paragraph_format.first_line_indent = Pt(0); set_first_line_chars(p._p, 0)
        run = add_field(p, f'TOC \\o "{self.cfg["toc"]["levels"]}" \\h \\z \\u', '（目录域：在 Word 中打开时选择“更新域”或按 F9 生成）')
        self.style_run(run, self.lv('body')['font'], 12)
        # 正文另起一节，页码阿拉伯数字从 1 开始
        s = self.doc.add_section(WD_SECTION.NEW_PAGE)
        self.decorate_section(s, 'decimal', self.cfg['page']['body_restart_page_number'])
        self.first_chapter = True

    def page_break(self):
        p = self.doc.add_paragraph(); fmt_par(p.paragraph_format, self.cfg, 'left'); p.add_run().add_break(WD_BREAK.PAGE)

    # 章节
    REFERENCE_HEADING = re.compile(r'(参考资料|参考文献|资料来源)\s*$')
    def in_reference(self):
        return getattr(self, 'ref_file', False) or getattr(self, 'ref_level', None) is not None

    def chapter(self, md_path, ch):
        rel = md_path.relative_to(self.repo).as_posix()
        self.ref_level = None; self.ref_file = rel.endswith('索引/资料来源说明.md')
        raw = md_path.read_text('utf-8').splitlines()
        self.fn_defs, lines, k = {}, [], 0
        while k < len(raw):
            md = re.match(r'^\[\^([^\]]+)\]:\s?(.*)$', raw[k])
            if md:
                txt = md.group(2); k += 1
                while k < len(raw) and re.match(r'^( {4}|\t)\S', raw[k]): txt += raw[k].strip(); k += 1
                self.fn_defs[md.group(1)] = txt; continue
            lines.append(raw[k]); k += 1
        kept = []
        for n0, l in enumerate(lines):   # 网页导航行：整行只有站内 .md 链接（以 · ｜ | 分隔），一律过滤
            # 网页残留行（源稿与 Word 应一致，脚本不静默删除）：默认报错；--allow-web-residue 时临时跳过以出样张
            t0 = l.strip()
            kind = '导航行' if t0 and NAV_RE.fullmatch(t0) else ('页眉行' if WEBHDR_RE.match(t0) else None)
            if kind:
                self.nav_hits.append(f'{rel}:{n0 + 1}  {kind}「{t0[:40]}」')
                if self.allow_web: kept.append(''); continue   # 留空行，保持行号
            kept.append(l)
        lines = kept
        if guide_kind(self.cfg, rel, md_path.name) == 'x00':
            lines = guide_to_plain(lines)
            if self.secmap:   # 篇目表源稿代号 → 书中节号＋节名
                def code2sec(l):
                    m = re.match(r'^([A-Z]\d{2})\s+\S+?：', l)
                    return self.secmap[m.group(1)] if m and m.group(1) in self.secmap else l
                lines = [code2sec(l) for l in lines]
        self.ch = ch; self.n2 = self.n3 = self.n4 = 0
        self.is_guide = guide_kind(self.cfg, rel, md_path.name) == 'x00'
        if self.demote:
            host = self.host.get(rel, ch)
            if host in self.demote and host != self.last_ch:   # 本章第一篇（或导读页）前印章标题；下册附编按附录字母印“附录X　标题”
                self.last_ch = host; self.sec.setdefault(host, 0)
                self.heading_raw(1, self.cfg['numbering']['chapter_format'].format(cn=cn_num(host), title=self.demote[host]) if isinstance(host, int)
                                 else f'附录{host}\u3000{self.demote[host]}')
            self.whole = ch in self.demote and len(self.members.get(ch, [])) == 1 and self.is_guide is False and ch in self.whole_ch
        # 册首 front 篇目（style.yaml volumes.<vol>.front，如下册 00-导言.md）不编章号：图表号用“导”，即 图导-1／表导-1；其余不编号篇目仍按 0 计
        _front = {f"{v['dir']}/{f}" for v in self.cfg.get('volumes', {}).values() if isinstance(v, dict) and v.get('dir') for f in v.get('front', [])}
        label = str(ch) if ch is not None else ('导' if rel in _front else '0')
        self.label = label; self.cur_file = rel
        # 图表号按“全书章号”计：同一章的后续篇目接着上一篇的序号；不编号的导读页（label 0）、front 篇目（label 导）各自单独计
        self.ntab, self.nfig = self.chap_counters.get(label, (0, 0))
        self.tab_base = self.ntab   # 本篇第一个表在本章中的序号偏移（表题按本篇内序号取）
        self.titles = [t['title'] for t in self.table_titles.get(rel, [])]
        for t in self.titles:
            if t and CAPNO_RE.match(t): self.caption_hits.append(f'{rel}  表题「{t[:30]}」')
        self.titles = [CAPNO_RE.sub('', t).strip() if t else t for t in self.titles]
        i, skip_index = 0, False
        para_buf = []
        def flush():
            if para_buf:
                out = ''
                for s in para_buf:   # 仅按 Markdown 软换行规则拼接，不改动行内空格
                    s = s.strip('\r\n').lstrip()
                    if out and re.match(r'[A-Za-z0-9]', out[-1:]) and re.match(r'[A-Za-z0-9]', s[:1]): out += ' '
                    out += s.rstrip(' ') if not s.endswith('  ') else s.rstrip(' ') + '\n'
                self.para('Normal', out.rstrip('\n')); para_buf.clear()
        refs_start = len(self.xrefs)
        while i < len(lines):
            ln = lines[i]; s = ln.strip()
            self.scan_refs(rel, i + 1, ln)
            # 清除网页元素
            if re.fullmatch(r'<a id="[^"]*"></a>', s) or s in ('---', '***') or \
               False:
                flush(); i += 1; continue
            if s == '本章索引':
                flush(); i += 1
                while i < len(lines) and (not lines[i].strip() or re.match(r'^\s*[-*] \[.*\]\(#', lines[i])): i += 1
                continue
            m = re.match(r'^(#{1,4})\s+(.*)$', s)
            if m:
                flush(); hl, ht = len(m.group(1)), m.group(2).strip()
                if self.ref_level is not None and hl <= self.ref_level: self.ref_level = None
                if self.REFERENCE_HEADING.search(re.sub(r'[*`]', '', ht)): self.ref_level = hl
                self.heading(hl, ht); i += 1; continue
            if s.startswith('|') and i + 1 < len(lines) and re.match(r'^\s*\|?\s*:?-{2,}', lines[i + 1]):
                flush(); rows = []
                while i < len(lines) and lines[i].strip().startswith('|'):
                    rows.append(lines[i].strip()); i += 1
                self.table(rows); continue
            mi = re.fullmatch(r'\[?!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)(?:\]\([^)]*\))?', s)
            if mi:
                flush(); i += 1
                alt, orig, note = mi.group(1), None, None
                j = i
                while j < len(lines) and not lines[j].strip(): j += 1
                where = f'{rel}:{i}'
                if CAPNO_RE.match(alt):
                    self.caption_hits.append(f'{rel}:{i}  替代文字「{alt[:30]}」'); orig = re.match(r'^[图表][ 　]*([0-9A-Z]+[-－.]\d+)', alt).group(1)
                title = CAPNO_RE.sub('', alt).strip()   # 图题以替代文字为准，锚点按它解析
                if not title: self.fig_errors.append(f'{where}  替代文字为空，无图题')
                cl = lines[j].strip() if j < len(lines) else ''
                if not cl or cl.startswith(('![', '[![', '#', '|')):
                    self.fig_errors.append(f'{where}  图片后缺图题说明行（须含“资料来源”或“数据来源”）')
                else:
                    if CAPNO_RE.match(cl):
                        self.caption_hits.append(f'{rel}:{j + 1}  图题行「{cl[:30]}」'); orig = orig or re.match(r'^[图表][ 　]*([0-9A-Z]+[-－.]\d+)', cl).group(1)
                    body = CAPNO_RE.sub('', cl).strip()
                    if not re.search(r'资料来源|数据来源', body):
                        self.fig_errors.append(f'{rel}:{j + 1}  图题说明行缺“资料来源/数据来源”「{body[:30]}」')
                    elif re.match(r'^(资料来源|数据来源)', body): note = body
                    else:
                        head, _, note = body.partition('。')
                        P = lambda t: re.sub(r'[\s\u3000\u00a0，。、；：:,.;（）()“”"\'《》·—\-]', '', t)
                        if P(head) != P(title):
                            self.fig_errors.append(f'{rel}:{j + 1}  图题说明行标题「{head[:24]}」与替代文字「{title[:24]}」不一致')
                    i = j + 1
                alt = title
                self.figure(md_path.parent / unquote(mi.group(2)), alt, orig_no=orig, orig_note=note.strip() if note else None, where=where)
                continue
            if not s: flush(); i += 1; continue
            if s.startswith('>'):
                flush(); self.para('Normal', s.lstrip('>').strip()); i += 1; continue
            ml = re.match(r'^\s*[-*+]\s+(.*)$', ln)
            if ml: flush(); self.para('Normal', '• ' + ml.group(1)); i += 1; continue
            mn = re.match(r'^\s*(\d+)[.)]\s+(.*)$', ln)
            if mn: flush(); self.para('Normal', f'{mn.group(1)}. {mn.group(2)}'); i += 1; continue
            para_buf.append(ln); i += 1
        flush()
        self.resolve_refs(refs_start)
        self.log['chapters'].append({'file': rel, 'chapter': ch, 'tables': self.ntab - self.tab_base, 'figures': self.nfig - self.chap_counters.get(label, (0, 0))[1]})
        self.chap_counters[label] = (self.ntab, self.nfig)

    REF = re.compile(r'(?:见|如|参见|详见)?(?:[图表][ 　]?[0-9A-Z]+(?:[-－.][0-9]+)?(?![0-9])|(?:如|见)?[上下前后][图表](?:所示)?|此表|该表|本表|该图|此图)')
    def scan_refs(self, rel, lineno, ln):
        if ln.lstrip().startswith(('#', '|', '![')) or '](http' in ln and re.match(r'^\[\d+\]', ln.strip()):
            pass
        if ln.lstrip().startswith(('#', '|')): return
        for m in self.REF.finditer(ln):
            tok = m.group(0)
            if re.search(r'图示|表述|表明|表达|表现|代表|图谱|意图|试图|地图|蓝图', ln[max(0, m.start()-1):m.end()+1]) and not re.search(r'[图表][ 　]?[0-9]', tok):
                continue
            ctx = ln[max(0, m.start()-12):m.end()+12].strip()
            self.xrefs.append({'file': rel, 'line': lineno, 'text': tok, 'ctx': ctx,
                               'ntab': self.ntab, 'nfig': self.nfig, 'chapter': self.label})

    def resolve_refs(self, start):
        for r in self.xrefs[start:]:
            kind = '表' if '表' in r['text'] else '图'
            total = self.ntab if kind == '表' else self.nfig
            seen = r['ntab'] if kind == '表' else r['nfig']
            m = re.search(r'[图表][ 　]?([0-9A-Z]+)(?:[-－.]([0-9]+))?', r['text'])
            target, status = None, ''
            fm = {f['old'].replace('－', '-'): f['new'] for f in self.log.get('figmap', []) if f.get('old') and f['where'].startswith(r['file'])}
            oldno = f"{m.group(1)}-{m.group(2)}" if m and m.group(2) else None
            if kind == '图' and oldno in fm:
                r['new'] = fm[oldno]; r['status'] = '一致（按源稿图题映射）' if fm[oldno] != '已删除' else '所引图已按图片清单删除，需改写'
                r['ok'] = fm[oldno] != '已删除'; r['kind'] = kind; continue
            if m and m.group(1)[0].isdigit() or (m and m.group(2)):
                if m.group(2):
                    oldch, n = m.group(1), int(m.group(2))
                    if oldch != self.label: status = f'原章号 {oldch} 与新章号 {self.label} 不一致，需核对'
                else:
                    n = int(m.group(1)); status = '旧式不带章号的编号，需改写为“X-Y”'
                target = n if n <= total else None
                if target is None: status = f'本章只有 {total} 个{kind}，引用的{kind}不存在'
            elif re.search(r'[下后]', r['text']):
                target = seen + 1 if seen + 1 <= total else None
                status = '方位指代，建议改为明确编号' if target else f'其后无{kind}，指代不明'
            elif re.search(r'[上前]|此|该|本', r['text']):
                target = seen if seen >= 1 else None
                status = '方位指代，建议改为明确编号' if target else f'此前无{kind}，指代不明'
            r['kind'] = kind
            r['new'] = f'{kind} {self.label}-{target}' if target else '—'
            r['status'] = status or '一致'
            r['ok'] = bool(target) and r['status'] in ('一致', '方位指代，建议改为明确编号')

    def write_xref(self, path):
        L = ['# 图表交叉引用对照表（上册样张）', '',
             f'- 生成脚本：build_docx.py，随样张自动生成；书中实际图 {len(self.log["figures"])} 个、表 {len(self.log["tables"])} 个。',
             f'- 扫描到正文引用 {len(self.xrefs)} 处；需处理 {sum(1 for r in self.xrefs if not r["ok"])} 处（✗），方位指代建议改写 {sum(1 for r in self.xrefs if r["status"].startswith("方位"))} 处（△）。', '',
             '## 一、引用对照', '', '| # | 位置（源文件:行） | 原文 | 上下文 | 原图号 | 重编后实际编号 | 判定 |', '|---|---|---|---|---|---|---|']
        for i, r in enumerate(self.xrefs, 1):
            mark = '✗' if not r['ok'] else ('△' if r['status'].startswith('方位') else '✓')
            orig = r['text'] if re.search(r'[0-9]', r['text']) else '（无编号）'
            L.append(f"| {i} | {r['file']}:{r['line']} | {r['text']} | {r['ctx'].replace('|','／')} | {orig} | {r['new']} | {mark} {r['status']} |")
        if not self.xrefs: L.append('| — | — | 未发现引用 | — | — | — | — |')
        if self.log.get('figmap'):
            L += ['', '## 二、源稿图号 → 重编图号', '', '| 位置 | 图片文件 | 源稿图号 | 重编后 |', '|---|---|---|---|']
            L += [f"| {f['where']} | {f['file']} | {f['old'] or '（无）'} | {f['new']} |" for f in self.log['figmap']]
        L += ['', '## 三、重编后图表清单', '']
        L += [f'- {t}' for t in self.log['tables'] + self.log['figures']]
        L += ['', '说明：扫描规则覆盖“见图/表 X-Y”“图X”“表X”“上/下/前/后图（表）”“如上图所示”“此表/该表/本表”。上册源稿无插图，图号仅在表格上验证；中下册含图片后同一脚本适用。']
        Path(path).write_text('\n'.join(L) + '\n', 'utf-8')

    def heading(self, level, text):
        text = re.sub(r'<a id="[^"]*"></a>', '', text).strip()
        ch = self.ch
        if self.demote and (ch in self.demote or (ch is None and self.is_guide)):   # 合订本：只降级配置了 chapter_titles 的章（中册、下册）
            return self.heading_demoted(level, text, ch)
        if isinstance(ch, str) and re.fullmatch(r'[A-Z]', ch) and level == 1:   # 附录题：字母随本书编排（合订本重排字母）
            text = re.sub(r'^附录[A-Z]', f'附录{ch}', re.sub(r'<a id="[^"]*"></a>', '', text).strip())
        if isinstance(ch, str) and re.fullmatch(r'[A-Z]', ch) and level == 2:   # 附录二级标题：脚本编号 A.1、A.2…（同正文 X.Y）
            self.app_n = (self.app_n + 1) if getattr(self, 'app_ch', None) == ch else 1; self.app_ch = ch
            body = re.sub(r'^((?:[A-Z]|\d+)(?:\.\d+)*|[一二三四五六七八九十]+、|第[一二三四五六七八九十]+节|\d+\s*[.、．)）])[\s　]*', '', text)
            return self.heading_raw(2, f'{ch}.{self.app_n} {body}')
        if level == 1:
            if isinstance(ch, int):
                title = re.sub(r'^第[一二三四五六七八九十百零\d]+章[\s　]*', '', text)
                text = self.cfg['numbering']['chapter_format'].format(cn=cn_num(ch), title=title)
            p = self.doc.add_paragraph(style='Heading 1')
            if getattr(self, 'first_chapter', False):
                p.paragraph_format.page_break_before = False; self.first_chapter = False
        else:
            numbered = re.match(r'^((?:\d+|[A-Z])(?:\.\d+)+|\d+)[\s　]+(.*)$', text)
            if ch is not None and level == 2 and not numbered and re.match(r'^第[一二三四五六七八九十]+节', text):
                self.n2 += 1; self.n3 = self.n4 = 0   # “第X节”式二级标题：只计数，供三级自动编号，标题文字不改
            if ch is not None and level == 3 and not numbered:
                m3 = re.match(r'^\d+\s*[.、．)）]\s*(.+)$', text)   # 仅真正的 Markdown 三级标题：手写“1. ”“2、”前缀换成 X.Y.Z
                if m3: numbered = re.match(r'^(\S+)\s+(.*)$', '0 ' + m3.group(1))
            if numbered and ch is not None:
                body = numbered.group(2)
                if level == 2: self.n2 += 1; self.n3 = self.n4 = 0; num = f'{ch}.{self.n2}'
                elif level == 3: self.n3 += 1; self.n4 = 0; num = f'{ch}.{self.n2}.{self.n3}'
                else: self.n4 += 1; num = f'{ch}.{self.n2}.{self.n3}.{self.n4}'
                text = f'{num} {body}'
            p = self.doc.add_paragraph(style=f'Heading {level}')
        key = f'h{level}'; c = self.lv(key)
        fmt_par(p.paragraph_format, self.cfg, c['align'], 0, c['size_pt'])
        self.inline(p, text, key)

    def heading_raw(self, level, text):
        p = self.doc.add_paragraph(style=f'Heading {level}')
        if level == 1 and getattr(self, 'first_chapter', False):
            p.paragraph_format.page_break_before = False; self.first_chapter = False
        c = self.lv(f'h{level}'); fmt_par(p.paragraph_format, self.cfg, c['align'], 0, c['size_pt'])
        self.inline(p, text, f'h{level}')

    def heading_demoted(self, level, text, ch):
        """中册降级：章标题由脚本按 style.yaml 印；篇目 # → X.Y（二级），## → X.Y.Z（三级），### → 四级“（n）”。
        整章即一篇（第九章导读）：# 不印，## → X.Y，### → X.Y.Z。门类导读页：# → 不编号二级。"""
        strip_sec = lambda t: re.sub(r'^(第[一二三四五六七八九十]+节|[一二三四五六七八九十]+、|\d+\s*[.、．)）])[\s　]*', '', t)
        if ch is None:   # 门类导读页
            if level == 1: self.heading_raw(2, text)
            return
        lv = level - 1 if self.whole else level
        if lv <= 0: return   # 整章篇目的 #：与章标题重复，不印
        if lv == 1:
            self.sec[ch] += 1; self.n2 = self.sec[ch]; self.n3 = self.n4 = 0
            body = strip_sec(re.sub(r'^(第[一二三四五六七八九十百零\d]+章|附?[A-Z]\d{2})[\s　]*', '', text))
            return self.heading_raw(2, f'{ch}.{self.n2} {body}')
        if lv == 2:
            if re.match(r'^(参考资料|参考文献|资料来源)$', text): return self.heading_raw(3, text)   # 节末参考资料：不编号
            self.n3 += 1; self.n4 = 0
            return self.heading_raw(3, f'{ch}.{self.n2}.{self.n3} {strip_sec(text)}')
        self.n4 += 1   # 四级：体例“不编号或用（1）”，取“（n）”
        return self.heading_raw(4, f'（{self.n4}）{strip_sec(text)}')

    def caption(self, kind, title):
        if kind == '表':
            self.ntab += 1; n = self.ntab; fmt = self.cfg['numbering']['table_format']
        else:
            self.nfig += 1; n = self.nfig; fmt = self.cfg['numbering']['figure_format']
        text = fmt.format(ch=self.label, n=n, title=title).rstrip('　 ')
        p = self.para('Caption', key='caption')
        r = p.add_run(text); c = self.lv('caption'); self.style_run(r, c['font'], c['size_pt'], c['bold'])
        self.log['tables' if kind == '表' else 'figures'].append(text)
        if title: self.collect.setdefault((kind, norm_title(title)), []).append({'no': f'{kind}{self.label}-{n}', 'file': self.cur_file})
        return p

    def table(self, rows):
        cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
        header, body = cells[0], cells[2:]
        idx = self.ntab - self.tab_base
        title = self.titles[idx] if idx < len(self.titles) else ''
        if not title: self.log['warnings'].append(f'第{self.label}章 表{idx+1} 无表题，仅编号')
        cap = self.caption('表', title); cap.paragraph_format.keep_with_next = True
        ncol = max(len(header), *(len(r) for r in body)) if body else len(header)
        t = self.doc.add_table(rows=1 + len(body), cols=ncol)
        t.style = self.doc.styles['Table Grid']; t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for ri, row in enumerate([header] + body):
            for ci in range(ncol):
                cell = t.cell(ri, ci); p = cell.paragraphs[0]; p.style = self.doc.styles['表格文字']
                c = self.lv('table')
                fmt_par(p.paragraph_format, self.cfg, 'center' if ri == 0 else c['align'], 0, c['size_pt'])
                self.inline(p, row[ci] if ci < len(row) else '', 'table', ri == 0)
        # 表格边框黑色
        self.para('Normal', key='body')  # 表后空行（行距同正文）

    def load_manifest(self):
        if hasattr(self, 'manifest'): return self.manifest
        m = self.cfg.get('images', {}).get('manifest')
        mp = (HERE / m) if m else None
        self.manifest = {}
        if mp and mp.exists():
            for e in (yaml.safe_load(mp.read_text('utf-8')) or {}).get('images', []): self.manifest[e['file']] = e
        return self.manifest

    def figure(self, path, alt, orig_no=None, orig_note=None, where=''):
        ic = self.cfg.get('images', {}); entry = self.load_manifest().get(path.name)
        if entry:
            act = entry.get('action', 'keep')
            if isinstance(act, dict): act = act.get(ic.get('edition', 'ebook'), 'keep')
            if act == 'delete':
                self.log['figures_removed'] = self.log.get('figures_removed', []) + [str(path.name)]
                self.log.setdefault('figmap', []).append({'where': where, 'old': orig_no, 'new': '已删除', 'file': path.name}); return
            if act == 'redraw':
                if entry.get('redraw_file') and (HERE / entry['redraw_file']).exists(): path = HERE / entry['redraw_file']
                else:
                    p = self.para('Normal', key='body', align='center'); p.paragraph_format.first_line_indent = Pt(0); set_first_line_chars(p._p, 0)
                    r = p.add_run(f'【待重绘：{path.name}】'); self.style_run(r, self.lv('body')['font'], 12, True)
                    self.log['warnings'].append(f'待重绘图片占位: {path.name}')
                    self.caption('图', alt); self.figure_note(entry)
                    self.log.setdefault('figmap', []).append({'where': where, 'old': orig_no, 'new': f'图 {self.label}-{self.nfig}', 'file': path.name}); return
        if not path.exists():
            self.log['warnings'].append(f'图片缺失: {path}'); return
        if path.suffix.lower() == '.svg':
            png = path.with_suffix('.png')
            if png.exists(): path = png
            else: self.log['warnings'].append(f'SVG 暂不支持直接嵌入: {path}'); return
        p = self.para('Normal', key='body', align='center'); p.paragraph_format.first_line_indent = Pt(0); set_first_line_chars(p._p, 0)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE  # 图片段必须单倍，否则固定行距会裁切图片
        r = p.add_run(); r.add_picture(str(path))
        pic = r._r.xpath('.//wp:extent')[0]; w, h = int(pic.get('cx')), int(pic.get('cy'))
        maxw = int(Cm(14.5))
        if w > maxw:
            scale = maxw / w
            for e in r._r.xpath('.//wp:extent | .//a:ext'):
                e.set('cx', str(int(w * scale))); e.set('cy', str(int(h * scale)))
        p.paragraph_format.keep_with_next = True
        self.caption('图', alt)
        self.log.setdefault('figmap', []).append({'where': where, 'old': orig_no, 'new': f'图 {self.label}-{self.nfig}', 'file': path.name})
        if entry: self.figure_note(entry)
        elif orig_note: self.figure_note({'note': orig_note})

    def figure_note(self, e):
        ic = self.cfg['images']; c = self.lv('figure_note')
        cc = ic['cc_note'] if e.get('not_cc', True) else ''
        txt = e.get('note') or ic['note_format'].format(source=e.get('source', '来源待补'), cc=cc).strip()
        p = self.para('Normal', key='figure_note', align=c['align']); p.paragraph_format.first_line_indent = Pt(0); set_first_line_chars(p._p, 0)
        self.inline(p, txt, 'figure_note')

    # ---- 真脚注 ----
    def footnotes_root(self):
        if getattr(self, '_fn_root', None) is not None: return self._fn_root
        W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        xml = (f'<w:footnotes xmlns:w="{W}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
               '<w:footnote w:type="separator" w:id="-1"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:separator/></w:r></w:p></w:footnote>'
               '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>'
               '</w:footnotes>')
        self._fn_root = etree.fromstring(xml.encode())
        self._fn_next = 1
        root = self._fn_root
        class FnPart(Part):
            @property
            def blob(self_): return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
        self._fn_part = FnPart(PackURI('/word/footnotes.xml'),
                               'application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml', b'', self.doc.part.package)
        self.doc.part.relate_to(self._fn_part, RT.FOOTNOTES)
        return self._fn_root

    def add_footnote(self, p, text):
        root = self.footnotes_root(); fid = self._fn_next; self._fn_next += 1
        c = self.lv('footnote')
        # 正文中的引用标记（上标）
        r = p.add_run(); self.style_run(r, c['font'], self.lv('body')['size_pt'])
        rpr = r._r.get_or_add_rPr(); va = OxmlElement('w:vertAlign'); va.set(qn('w:val'), 'superscript'); rpr.append(va)
        ref = OxmlElement('w:footnoteReference'); ref.set(qn('w:id'), str(fid)); r._r.append(ref)
        # 脚注内容：借一个临时段落用同一套行内解析，再搬进 footnotes.xml
        tmp = self.doc.add_paragraph()
        fmt_par(tmp.paragraph_format, self.cfg, c['align'], 0, c['size_pt'])
        tmp.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        mr = tmp.add_run(); self.style_run(mr, c['font'], c['size_pt'])
        mrpr = mr._r.get_or_add_rPr(); va2 = OxmlElement('w:vertAlign'); va2.set(qn('w:val'), 'superscript'); mrpr.append(va2)
        mr._r.append(OxmlElement('w:footnoteRef'))
        sp = tmp.add_run(' '); self.style_run(sp, c['font'], c['size_pt'])
        self._link_part = self._fn_part
        self.inline(tmp, text, 'footnote', allow_fn=False)
        self._link_part = None
        tmp._p.getparent().remove(tmp._p)
        fn = OxmlElement('w:footnote'); fn.set(qn('w:id'), str(fid)); fn.append(tmp._p); root.append(fn)
        self.log.setdefault('footnotes', []).append(text[:30])

    def guide_page_breaks(self):
        """章标题下有导读（任何非编号内容）时，第一个 X.1 二级节另起一页。"""
        ps = self.doc.paragraphs; NUM = re.compile(r'^(?:\d+|[A-Z])\.1(?:\s|　)')
        for k, p in enumerate(ps):
            if p.style.name != 'Heading 1': continue
            j = k + 1
            while j < len(ps) and ps[j].style.name != 'Heading 1':
                if ps[j].style.name == 'Heading 2' and NUM.match(ps[j].text): break
                j += 1
            if j < len(ps) and ps[j].style.name == 'Heading 2' and any(x.text.strip() for x in ps[k + 1:j]):
                ps[j].paragraph_format.page_break_before = True

    def save(self, out):
        # 门类导读已删除：不再做“导读单独成页、X.1 前分页”

        self.doc.core_properties.title = self.cfg['book']['title']
        self.doc.core_properties.author = self.cfg['book']['author']
        import indent_fix; self.log['flush_left_chars_fixed'] = indent_fix.fix(self.doc)   # 顶格段落（firstLine=0）不得继承非零 firstLineChars
        self.doc.save(out)

NAV_RE = re.compile(r'(?:>\s*)?(?:\*\*)?(?:(?:返回|上一[章篇节]|下一[章篇节])[:：]?\s*)?(?:\[[^\]]+\]\((?!https?:)[^)\s]*(?:\.md|README)[^)\s]*\)\s*(?:[·•｜|/、，,→←]\s*)?)+(?:\*\*)?')
WEBHDR_RE = re.compile(r'^(?:>\s*)?一芥智能研究院\s*[｜|].*[｜|]')
CAPNO_RE = re.compile(r'^[图表][ 　]*(?:\d+|[A-Z])[-－.]\d+(?![-－.\d])[ 　]*')

def norm_title(t):
    t = re.sub(r'^[图表]\s*[0-9A-Z]+[-－]\d+[\s　]*', '', t.strip())
    return re.sub(r'[\s　]+', '', t)

LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]+\)')

def guide_kind(cfg, rel, name):
    gp = cfg.get('exclude', {}).get('guide_pages') or {}
    if not gp or (gp.get('dir') and not rel.startswith(gp['dir'].rstrip('/') + '/')): return None
    if name in gp.get('current', []): return 'old'
    if any(fnmatch.fnmatch(name, p) for p in gp.get('x00_patterns', [])): return 'x00'
    return None

def guide_to_plain(lines):
    """导读页：把链接表/链接列表改成纯文本篇目列表（无超链接、无表格）；其余行仅去掉超链接。"""
    lines = [l for l in re.sub(r"<!--.*?-->", "", "\n".join(lines), flags=re.S).split("\n")]
    out, i = [], 0
    while i < len(lines):
        if lines[i].lstrip().startswith('|'):
            blk = []
            while i < len(lines) and lines[i].lstrip().startswith('|'): blk.append(lines[i]); i += 1
            if not any(LINK_RE.search(r) for r in blk): out += blk; continue
            rows = [[c.strip() for c in r.strip().strip('|').split('|')] for r in blk]
            rows = [r for r in rows if not all(re.fullmatch(r':?-{2,}:?', c) for c in r if c)]
            if rows and not any(LINK_RE.search(c) for c in rows[0]): rows = rows[1:]   # 表头
            out.append('篇目：'); out.append('')
            for r in rows:
                cells = [LINK_RE.sub(r'\1', c).strip() for c in r if c.strip()]
                if cells: out.append('　'.join(cells[:1]) + ('：' + '；'.join(cells[1:]) if len(cells) > 1 else '')); out.append('')
            continue
        m = re.match(r'^\s*(?:[-*+]|\d+[.)])\s+(.*)$', lines[i])
        if m and LINK_RE.search(m.group(1)):
            out.append(LINK_RE.sub(r'\1', m.group(1)).strip()); out.append(''); i += 1; continue
        out.append(LINK_RE.sub(r'\1', lines[i])); i += 1
    return out

def excluded(cfg, repo, path):
    ex = cfg.get('exclude', {}); rel = path.relative_to(repo).as_posix()
    if any(fnmatch.fnmatch(path.name, pat) for pat in ex.get('patterns', [])): return '排除模式'
    if rel in ex.get('files', []): return '排除列表'
    gp = ex.get('guide_pages') or {}
    if gp:
        in_dir = not gp.get('dir') or rel.startswith(gp['dir'].rstrip('/') + '/')
        if in_dir and path.name in gp.get('current', []): return '门类导读页（旧名，待改 X00）'
        if in_dir and any(fnmatch.fnmatch(path.name, p) for p in gp.get('x00_patterns', [])):
            return None if gp.get('mode') == 'include_x00' else '门类导读页（X00）'
    if rel in ex.get('force_include', []): return None
    if any(rel.startswith(d.rstrip('/') + '/') for d in ex.get('nav_page_detect_exempt_dirs', [])): return None   # 下册：短篇案例链接多，不按导航页判定
    if ex.get('nav_page_detect') and path.suffix == '.md':
        t = path.read_text('utf-8')
        links = len(re.findall(r'\]\([^)]+\)', t))
        plain = re.sub(r'\[[^\]]*\]\([^)]+\)|<[^>]+>|[#>*|\-\s]', '', t)
        if len(plain) < ex.get('nav_page_max_chars', 1500) and links >= 3: return '导航/分篇入口页'
    return None

def parse_ch(v):
    if v in (None, 'null', 'None', ''): return None
    return int(v) if str(v).isdigit() else str(v)

def volume_items(cfg, repo, name, relabel=None):
    """按 style.yaml 的 volumes.<name> 列出 (篇目路径, 章号)。
    files：逐篇列章号（上册）；chapters：{章号: [篇目]}（中册）；groups：{章号或附录字母: 子目录}，
    目录内篇目按文件名排序、同属一章（下册）；include：按序合并各册（合订本），relabel 重排附录字母。"""
    v = cfg['volumes'][name]; relabel = relabel or {}
    def lab(c): return relabel.get(c, c) if isinstance(c, str) else c
    if 'include' in v:
        out = []
        for sub in v['include']: out += volume_items(cfg, repo, sub, (v.get('appendix_relabel') or {}).get(sub))
        return out
    if 'groups' in v:
        items = [(repo / v['dir'] / f, None) for f in v.get('front', [])]   # 册首不编号篇目（下册导言），排在各章之前
        for c, sub in v['groups'].items():
            d = repo / v['dir'] / sub
            if not d.is_dir(): sys.exit(f'style.yaml volumes.{name}.groups 指向的目录不存在：{d.relative_to(repo).as_posix()}')
            items += [(p, lab(parse_ch(c))) for p in sorted(d.glob('*.md'))]   # README.md（门类导读）由 exclude.patterns 剔除
        return items
    if 'chapters' in v:   # 按全书章号映射：{章号: [篇目...]}；未列出的 X00 导读页不编号，附录按字母
        fmap = {alt.strip(): ch for ch, fs in v['chapters'].items() for f in fs for alt in str(f).split('|')}
        for f in v.get('unnumbered', []):
            for alt in str(f).split('|'): fmap[alt.strip()] = None
        allf = sorted(p.name for p in (repo / v['dir']).glob('*.md'))
        items = []
        for f in allf:
            if f in fmap: items.append((repo / v['dir'] / f, parse_ch(fmap[f])))
            elif guide_kind(cfg, f"{v['dir']}/{f}", f) == 'x00': items.append((repo / v['dir'] / f, None))
            elif re.match(r'^附录([A-Z])', f): items.append((repo / v['dir'] / f, re.match(r'^附录([A-Z])', f).group(1)))
            else: items.append((repo / v['dir'] / f, '__unmapped__'))
        un = [p.name for p, c in items if c == '__unmapped__' and not excluded(cfg, repo, p)]
        if un: sys.exit('以下篇目未在 style.yaml 映射章号：' + '、'.join(un))
        items = [(p, c) for p, c in items if c != '__unmapped__']
        # 按章号排序（导读页、附录随文件名顺序就近；章内保持文件名顺序）
        order = {alt.strip(): i for i, f in enumerate(v.get('order', [])) for alt in str(f).split('|')}   # “旧名 | 新名”任取其一
        if order: items.sort(key=lambda pc: order.get(pc[0].name, 10**6))
        return [(p, lab(c)) for p, c in items]
    return [(repo / v['dir'] / f, lab(parse_ch(c))) for f, c in v['files']]

def volume_demote(cfg, name, relabel=None):
    """降级版式的章：{章号或附录字母: 章名}，以及整章即一篇的章号集合。"""
    v = cfg['volumes'].get(name, {}); relabel = relabel or {}
    if 'include' in v:
        dm, wh = {}, set()
        for sub in v['include']:
            d, w = volume_demote(cfg, sub, (v.get('appendix_relabel') or {}).get(sub)); dm.update(d); wh |= w
        return dm, wh
    if not v.get('demote'): return {}, set()
    dm = {}
    for k, t in v['chapter_titles'].items():
        c = parse_ch(k); dm[relabel.get(c, c) if isinstance(c, str) else c] = t
    return dm, {int(k) for k in v.get('whole_chapter', [])}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--style', default=HERE / 'style.yaml')
    ap.add_argument('--repo', default=os.environ.get('BOOK_REPO', str(REPO_ROOT)))
    ap.add_argument('--volume', default='upper')
    ap.add_argument('--files', nargs='*', help='相对仓库的路径:章号')
    ap.add_argument('--dir', help='按目录批量（文件名排序），章号从 --start 起连续编号')
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--strict-captions', dest='strict_captions', action='store_true', default=True, help='（默认）图题/替代文字/表题残留手写编号即报错退出')
    ap.add_argument('--allow-caption-numbers', dest='strict_captions', action='store_false', help='临时放行：残留编号只记警告并照常构建（PR #8 合并前用）')
    ap.add_argument('--allow-caption-mismatch', action='store_true', help='图题行标题与替代文字不一致时只警告')
    ap.add_argument('--allow-web-residue', action='store_true', help='临时跳过网页导航行/“一芥智能研究院｜…”页眉行以出样张（默认报错退出）')
    ap.add_argument('--no-toc-pages', action='store_true', help='不预排目录（只留 TOC 域，Word 中按 F9 生成）')
    ap.add_argument('--only', type=int, help='只导出某一章（含其导读页），编号仍按全书')
    ap.add_argument('-o', '--output', default=OUT_DIR / '样张-上册.docx')
    ap.add_argument('--print', dest='print_edition', action='store_true', default=os.environ.get('BOOK_EDITION') == 'print', help='印刷版：参考文献与来源行在题名后补印网址（亦可 BOOK_EDITION=print）')
    a = ap.parse_args()
    cfg = yaml.safe_load(Path(a.style).read_text('utf-8')); repo = Path(a.repo)
    if a.files:
        items = [(repo / f.rsplit(':', 1)[0], parse_ch(f.rsplit(':', 1)[1] if ':' in f else None)) for f in a.files]
    elif a.dir:
        items = [(p, None) for p in sorted((repo / a.dir).glob('*.md'))]
    else:
        if a.volume not in cfg.get('volumes', {}):
            sys.exit(f'{ {"lower": "下册", "all": "合订本"}.get(a.volume, a.volume)}尚未纳入排版配置（style.yaml 的 volumes 下没有 {a.volume}），暂不能导出。')
        items = volume_items(cfg, repo, a.volume)
    kept, skipped = [], []
    for path, ch in items:
        why = excluded(cfg, repo, path)
        (skipped.append((path.relative_to(repo).as_posix(), why)) if why else kept.append((path, ch)))
    if a.dir:   # 门类导读页不占章号（不编号的门类入口），其余连续编号
        n, nk = a.start, []
        for p, _ in kept:
            if guide_kind(cfg, p.relative_to(repo).as_posix(), p.name) == 'x00': nk.append((p, None))
            elif re.match(r'^附录([A-Z])', p.name): nk.append((p, re.match(r'^附录([A-Z])', p.name).group(1)))   # 附录不占章号
            else: nk.append((p, n)); n += 1
        kept = nk
    items = kept
    for f, why in skipped: print(f'  跳过 {f}（{why}）')
    # 两轮：第一轮收集全书图题/表题 → 编号，第二轮据此解析 {{fig:}}/{{tab:}}
    def demote_setup(bb):
        if a.files or a.dir: return
        bb.demote, bb.whole_ch = volume_demote(cfg, a.volume)
        if not bb.demote: return
        cnt = {}
        for path, ch in items:   # 预排节号：篇目代号 → “X.Y 节名”
            if ch in bb.demote and ch not in bb.whole_ch:
                cnt[ch] = cnt.get(ch, 0) + 1
                h = next((l for l in path.read_text('utf-8').splitlines() if l.startswith('# ')), '# ' + path.stem)[2:].strip()
                code = re.match(r'^([A-Z]\d{2})', path.name)
                if code: bb.secmap[code.group(1)] = f"{ch}.{cnt[ch]} " + re.sub(r'^[A-Z]\d{2}[\s　]*', '', h)
        nxt = None
        for path, ch in reversed(items):   # 导读页归属其后第一篇所在章
            rel = path.relative_to(repo).as_posix()
            if ch in bb.demote: nxt = ch; bb.members.setdefault(ch, []).append(rel)
            elif ch is not None: nxt = None   # 合订本：未降级的章（上册）及附录隔断，其前的不编号篇目不归入后面的降级章
            bb.host[rel] = ch if ch is not None else (nxt if guide_kind(cfg, rel, path.name) == 'x00' else None)   # 册首导言等非门类导读页不归入后面的章
    b0 = Builder(cfg, repo); b0.allow_web = a.allow_web_residue; demote_setup(b0); b0.front_matter()
    for path, ch in items: b0.chapter(path, ch)
    b = Builder(cfg, repo, registry=b0.collect); b.print_edition = a.print_edition; b.allow_web = a.allow_web_residue; demote_setup(b); b.log['skipped'] = skipped; b.front_matter()
    for path, ch in items:
        if a.only is None or b.host.get(path.relative_to(repo).as_posix(), ch) == a.only: b.chapter(path, ch)
        # 其余章不排（图表号按章独立计，第10章号不受影响；跨文件引用用第一轮的全书登记表解析）
    dup = {k: v for k, v in b.collect.items() if len(v) > 1}
    b.log['duplicate_titles'] = [{'kind': k[0], 'title': k[1], 'hits': v} for k, v in dup.items()]
    b.log['ref_errors'] = b.ref_errors
    b.log['demote'] = bool(b.demote)
    b.log['demote_chapters'] = [c for c in b.demote]   # 合订本：只有这些章（中册、下册）按降级版式编号，check_docx 据此只核这些章
    b.log['web_residue'] = b.nav_hits; b.log['caption_numbers'] = b.caption_hits
    mism=[e for e in b.fig_errors if '不一致' in e]
    if a.allow_caption_mismatch:
        b.fig_errors=[e for e in b.fig_errors if '不一致' not in e]
        if mism: print(f'警告：图题与替代文字不一致 {len(mism)} 处（--allow-caption-mismatch 放行，图题取替代文字）')
    if b.fig_errors:
        print(f'图题错误 {len(b.fig_errors)} 处，未写出 {a.output}：')
        for h in b.fig_errors: print('   ', h)
        sys.exit(5)
    if b.nav_hits and not a.allow_web_residue:
        print(f'源稿残留网页导航行/页眉行 {len(b.nav_hits)} 处，未写出 {a.output}：')
        for h in b.nav_hits: print('   ', h)
        print('请文字编辑在源稿删除；临时出样张可加 --allow-web-residue（命中处记入 build.json 的 web_residue）。')
        sys.exit(4)
    if b.caption_hits and a.strict_captions:
        print(f'图题/表题残留手写编号 {len(b.caption_hits)} 处（严格模式 --strict-captions，默认开启），未写出 {a.output}：')
        for h in b.caption_hits: print('   ', h)
        print('PR #8 删去源稿图题编号前，可加 --allow-caption-numbers 临时构建（命中处记入 build.json 的 caption_numbers）。')
        sys.exit(3)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    b.save(a.output)
    if not a.no_toc_pages and shutil.which('soffice'):   # 目录预排：标题……页码，按层级缩进
        import toc_fill
        n, miss = toc_fill.fill(a.output, cfg)
        b.log['toc'] = {'entries': n, 'missing_page': miss}
        print(f'  目录预排 {n} 条' + (f'，{len(miss)} 条未找到页码：' + '；'.join(miss[:5]) if miss else ''))
    b.write_xref(Path(a.output).parent / ('图号对照表-' + Path(a.output).stem.replace('样张-', '') + '.md'))
    sys.path.insert(0, str(HERE))
    Path(a.output).with_suffix('.build.json').write_text(json.dumps(b.log, ensure_ascii=False, indent=1), 'utf-8')
    print(f'已生成 {a.output}；表 {len(b.log["tables"])} 个，图 {len(b.log["figures"])} 个，警告 {len(b.log["warnings"])} 条')
    fm = b.log.get('figmap', []); b.log['figure_caption_count'] = {'total_incl_duplicates': len(fm), 'deleted_duplicates': sum(1 for x in fm if x['new'] == '已删除')}
    print(f'  图题统计（含重复图）{len(fm)} 处，其中重复图已删 {b.log["figure_caption_count"]["deleted_duplicates"]} 处')
    for w in b.log['warnings']: print('  警告:', w)
    for e in b.ref_errors: print('  引用错误:', e)
    if b.nav_hits: print(f'  已临时跳过网页残留行 {len(b.nav_hits)} 处（--allow-web-residue）')
    if b.caption_hits:
        print(f'  图题/表题残留手写编号 {len(b.caption_hits)} 处：'); [print('   ', h) for h in b.caption_hits]
        if a.strict_captions: print('  严格模式（--strict-captions，默认）：构建失败。PR #8 合并前可加 --allow-caption-numbers 临时构建。')
    if b.ref_errors: sys.exit(2)
    if b.caption_hits and a.strict_captions: sys.exit(3)

if __name__ == '__main__':
    main()
