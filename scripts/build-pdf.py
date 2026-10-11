#!/usr/bin/env python3
"""Build the distribution PDF from the maintained Markdown (Pandoc + ReportLab).

Usage: python3 scripts/build-pdf.py
Override BOOK_BODY_FONT and BOOK_HEADING_FONT to use other Unicode TTF fonts.
"""
from pathlib import Path
from collections import Counter
from html import escape
from urllib.parse import unquote, urlsplit, quote
import hashlib
import json
import os
import re
import subprocess

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Flowable, CondPageBreak,
)
from reportlab.platypus.tableofcontents import TableOfContents
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
TITLE = '企业数智化转型研究报告'
DATE = '2026年10月11日'
VERSION = '上册 v8.0 / 下册 v7.0'
PDF = OUT / (TITLE + '-上下册合订本.pdf')
NAVY = colors.HexColor('#16334A')
TEAL = colors.HexColor('#227C80')
GRAY = colors.HexColor('#667581')
WIDTH, HEIGHT = A4
MARGIN = 21 * mm
TEXT_WIDTH = WIDTH - 2 * MARGIN


def key(path, anchor=''):
    return 'd' + hashlib.sha256((str(path.relative_to(ROOT)) + '#' + anchor).encode()).hexdigest()[:22]


def plain(items):
    result = []
    for x in items:
        t, c = x['t'], x.get('c')
        if t == 'Str': result.append(c)
        elif t in ('Space', 'SoftBreak', 'LineBreak'): result.append(' ')
        elif t in ('Strong', 'Emph', 'Strikeout', 'SmallCaps', 'Superscript', 'Subscript'): result.append(plain(c))
        elif t in ('Link', 'Image'): result.append(plain(c[1]))
        elif t == 'Code': result.append(c[1])
        elif t in ('Span','Cite'): result.append(plain(c[1]))
        elif t == 'Quoted': result.append('“' + plain(c[1]) + '”')
        elif t == 'Math': result.append(c[1])
        elif t not in ('RawInline', 'Note'): raise ValueError(f'Unsupported inline: {t}')
    return ''.join(result)


def slug(text):
    return re.sub(r'[^\w\-\s]', '', text.lower()).replace(' ', '-')


class Anchor(Flowable):
    def __init__(self, names):
        super().__init__()
        self.names = names
        self.width = self.height = 0
        self.keepWithNext = True

    def draw(self):
        for name in self.names:
            self.canv.bookmarkHorizontalAbsolute(name, self.canv.absolutePosition(0, 0)[1])


class KnowledgeDiagram(Flowable):
    """Vector equivalent of the source Mermaid graph; preserves every node/edge."""
    def __init__(self):
        super().__init__()
        self.width, self.height = TEXT_WIDTH, 260

    def draw(self):
        c = self.canv
        c.scale(TEXT_WIDTH/490,1)
        nodes = {
            'A': ('手机、桌面、项目与会话资料', 0, 185),
            'B': ('资源注册', 170, 185), 'C': ('统一索引', 340, 185),
            'D': ('当前任务', 340, 230),
            'E': ('按访问范围取回来源', 340, 115),
            'F': ('组织有效上下文', 170, 115),
            'G': ('执行、判断与交接', 0, 115),
            'H': ('结果、修正与候选知识', 0, 45),
            'I': ('确认并维护知识', 170, 45),
        }
        boxw, boxh = 130, 31
        def arrow(points):
            c.setStrokeColor(TEAL)
            p = c.beginPath(); p.moveTo(*points[0])
            for point in points[1:]: p.lineTo(*point)
            c.drawPath(p)
            x, y = points[-1]; px, py = points[-2]
            import math
            a = math.atan2(y-py, x-px)
            p = c.beginPath(); p.moveTo(x, y)
            p.lineTo(x-6*math.cos(a-.45), y-6*math.sin(a-.45))
            p.lineTo(x-6*math.cos(a+.45), y-6*math.sin(a+.45)); p.close()
            c.setFillColor(TEAL); c.drawPath(p, fill=1, stroke=0)
        arrow([(130,185),(170,185)])
        arrow([(300,185),(340,185)])
        arrow([(405,214.5),(405,200.5)])
        arrow([(405,169.5),(405,130.5)])
        arrow([(340,115),(300,115)])
        arrow([(170,115),(130,115)])
        arrow([(65,99.5),(65,60.5)])
        arrow([(130,45),(170,45)])
        arrow([(300,45),(480,45),(480,185),(470,185)])
        for text, x, y in nodes.values():
            c.setFillColor(colors.HexColor('#EEF5F6')); c.setStrokeColor(colors.HexColor('#B6D1D4'))
            c.roundRect(x,y-boxh/2,boxw,boxh,5,fill=1)
            c.setFillColor(NAVY); c.setFont('BookBody',8.5)
            c.drawCentredString(x+boxw/2,y-3,text)


class BookDoc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=23*mm, bottomMargin=22*mm,
                         title=TITLE, author='一芥智能研究院',
                         subject=f'从智力服务到精益经营；{VERSION}；{DATE}',
                         creator='一芥智能研究院 / Markdown + ReportLab')
        frame = Frame(MARGIN,22*mm,TEXT_WIDTH,HEIGHT-45*mm, leftPadding=0,
                      rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='book',frames=frame,onPage=self.page_chrome))
        self.section_pages = {}
        self.current_part = ''

    def beforeDocument(self):
        self.current_part = ''
        self.section_pages = {}

    def page_chrome(self, canvas, doc):
        if doc.page == 1: return
        canvas.saveState()
        canvas.setFont('BookBody',8)
        canvas.setFillColor(GRAY)
        canvas.drawString(MARGIN,HEIGHT-13*mm,TITLE)
        canvas.drawRightString(WIDTH-MARGIN,HEIGHT-13*mm,'上下册合订本')
        canvas.setStrokeColor(colors.HexColor('#D6DFE3'))
        canvas.line(MARGIN,HEIGHT-16*mm,WIDTH-MARGIN,HEIGHT-16*mm)
        canvas.drawString(MARGIN,12*mm,'一芥智能研究院  ·  2026.10')
        canvas.drawRightString(WIDTH-MARGIN,12*mm,str(doc.page))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if not isinstance(flowable,Paragraph) or not hasattr(flowable,'book_entry'): return
        level, title, name, toc = flowable.book_entry
        if level<2: self.canv.bookmarkPage(name)
        self.canv.addOutlineEntry(title,name,level=level,closed=(level>0))
        if toc: self.notify('TOCEntry',(level,title,self.page,name))
        if level == 0: self.current_part = title
        if hasattr(flowable,'source_path'):
            self.section_pages[flowable.source_path] = self.page


class Builder:
    def __init__(self):
        pdfmetrics.registerFont(TTFont('BookBody',os.environ.get('BOOK_BODY_FONT','/Library/Fonts/Arial Unicode.ttf')))
        pdfmetrics.registerFont(TTFont('BookHeading',os.environ.get('BOOK_HEADING_FONT','/System/Library/Fonts/STHeiti Medium.ttc')))
        pdfmetrics.registerFontFamily('BookBody',normal='BookBody',bold='BookHeading',italic='BookBody',boldItalic='BookHeading')
        self.styles = {}
        for name,size,leading,before,after in [
            ('body',10.5,18.5,0,7),('small',8.5,13.5,0,6),
            ('h1',21,31,0,18),('h2',14,23,14,9),('h3',11.5,20,10,6),
            ('cell',8.7,13.5,0,0),('cellhead',8.7,13.5,0,0),
            ('part',30,43,20,24),('toc0',13,22,10,7),('toc1',9.8,15,0,2),
        ]:
            self.styles[name] = ParagraphStyle(name,fontName='BookHeading' if name in ('h1','h2','h3','part','cellhead','toc0') else 'BookBody',
                fontSize=size,leading=leading,spaceBefore=before,spaceAfter=after,
                textColor=NAVY if name.startswith('h') or name in ('part','cellhead') else colors.HexColor('#26343E'),
                wordWrap='CJK',splitLongWords=True,keepWithNext=name in ('h1','h2','h3','part'))
        self.styles['toc1'].leftIndent = 12
        self.story=[]
        self.sources=[]
        self.coverage=[]
        self.links=Counter()
        self.included=set()
        self.anchors=set()
        self.current=None

    def para(self,text,style='body'):
        return Paragraph(text,self.styles[style])

    def href(self,target):
        parsed=urlsplit(target)
        if parsed.scheme in ('http','https','mailto'):
            self.links['external']+=1
            return escape(target,quote=True)
        dest=(self.current.parent/unquote(parsed.path)).resolve() if parsed.path else self.current
        if dest == ROOT/'README.md':
            self.links['internal']+=1
            return '#publication-note'
        if dest in self.included:
            anchor=unquote(parsed.fragment)
            name=key(dest,anchor)
            if name not in self.anchors: raise ValueError(f'Missing PDF destination {self.current}: {target}')
            self.links['internal']+=1
            return '#'+name
        self.links['repository']+=1
        url='https://github.com/scottzx/ai-in-organization/blob/main/'+quote(str(dest.relative_to(ROOT)))
        if parsed.fragment: url+='#'+quote(unquote(parsed.fragment))
        return escape(url,quote=True)

    def inline(self,items):
        result=[]
        for x in items:
            t,c=x['t'],x.get('c')
            if t=='Str': result.append(escape(c))
            elif t in ('Space','SoftBreak'): result.append(' ')
            elif t=='LineBreak': result.append('<br/>')
            elif t in ('Strong','Emph','SmallCaps','Strikeout','Superscript','Subscript'):
                tag={'Strong':'b','Emph':'i','SmallCaps':'b','Strikeout':'strike','Superscript':'super','Subscript':'sub'}[t]
                result.append(f'<{tag}>{self.inline(c)}</{tag}>')
            elif t=='Link': result.append(f'<a href="{self.href(c[2][0])}" color="#227C80">{self.inline(c[1])}</a>')
            elif t=='Code': result.append(escape(c[1]))
            elif t in ('Span','Cite'): result.append(self.inline(c[1]))
            elif t=='Quoted': result.append('“'+self.inline(c[1])+'”')
            elif t=='RawInline':
                for anchor in re.findall(r'id="([^"]+)"',c[1]): result.append(f'<a name="{key(self.current,anchor)}"/>')
            else: raise ValueError(f'Unsupported inline {t}')
        return ''.join(result)

    def load(self,path):
        text=path.read_text()
        # Omit web navigation and repeated per-file imprints; preserve manuscript text.
        lines=[]
        for line in text.splitlines():
            if line.startswith('一芥智能研究院｜'): continue
            if line.startswith('[') and ' · ' in line and not line.startswith('[^'): continue
            lines.append(line)
        source='\n'.join(lines)
        source=re.sub(r'(<a\s+id="[^"]+"[^>]*></a>)\n(?=#)',r'\1\n\n',source)
        ast=json.loads(subprocess.check_output(['pandoc','-f','markdown-citations','-t','json'],input=source.encode()))
        return ast['blocks']

    def register(self,path,blocks):
        self.included.add(path)
        self.anchors.add(key(path))
        for anchor in re.findall(r'<a\s+id="([^"]+)"',path.read_text()):
            self.anchors.add(key(path,anchor))
        for b in blocks:
            if b['t']=='Header':
                self.anchors.add(key(path,b['c'][1][0]))
                self.anchors.add(key(path,slug(plain(b['c'][2]))))
            elif b['t']=='RawBlock':
                for a in re.findall(r'id="([^"]+)"',b['c'][1]): self.anchors.add(key(path,a))

    def blocks(self,blocks,cell=False):
        out=[]
        for b in blocks:
            t,c=b['t'],b.get('c')
            if t in ('Para','Plain'):
                text=plain(c)
                if text:
                    self.coverage.append(text)
                    out.append(self.para(self.inline(c),'cell' if cell else ('small' if text.startswith(('本节来源','来源定位：')) else 'body')))
                else:
                    names=[key(self.current,a) for x in c if x['t']=='RawInline'
                           for a in re.findall(r'id="([^"]+)"',x['c'][1])]
                    if names: out.append(Anchor(names))
            elif t=='Header':
                level,attrs,items=c; title=plain(items)
                names=list(dict.fromkeys([key(self.current,attrs[0]),key(self.current,slug(title))]))
                while out and isinstance(out[-1],Anchor):
                    names.extend(out.pop().names)
                previous_heading=out and isinstance(out[-1],Paragraph) and out[-1].style.name in ('h1','h2','h3')
                if level>1 and not previous_heading: out.append(CondPageBreak(100))
                out.append(Anchor(names))
                p=self.para(self.inline(items),'h1' if level==1 else 'h2' if level==2 else 'h3')
                if level==1:
                    p.book_entry=(1,title,key(self.current),True)
                    p.source_path=str(self.current.relative_to(ROOT))
                elif level==2 and '上册-研究报告' in self.current.parts:
                    p.book_entry=(2,title,names[0],False)
                out.append(p); self.coverage.append(title)
            elif t=='RawBlock':
                names=[key(self.current,a) for a in re.findall(r'id="([^"]+)"',c[1])]
                if names: out.append(Anchor(names))
                elif c[1].strip(): raise ValueError(f'Unsupported HTML {c[1]}')
            elif t in ('BulletList','OrderedList'):
                entries=c if t=='BulletList' else c[1]
                start=1 if t=='BulletList' else c[0][0]
                for i,entry in enumerate(entries):
                    child=self.blocks(entry,cell)
                    if child and isinstance(child[0],Paragraph):
                        prefix='• ' if t=='BulletList' else f'{start+i}. '
                        child[0]=self.para(prefix+child[0].text,'cell' if cell else 'body')
                    out.extend(child)
            elif t=='Table': out.append(self.table(c))
            elif t=='HorizontalRule': pass
            elif t=='BlockQuote': out.extend(self.blocks(c,cell))
            elif t=='Div': out.extend(self.blocks(c[1],cell))
            elif t=='CodeBlock':
                if 'mermaid' in c[0][1]: out.append(KnowledgeDiagram())
                else: out.append(self.para(escape(c[1]).replace('\n','<br/>'),'small'))
            else: raise ValueError(f'Unsupported block: {t}')
        return out

    def table(self,c):
        _,_,colspec,head,bodies,foot=c
        rows=list(head[1])
        for body in bodies: rows.extend(body[2]+body[3])
        rows.extend(foot[1])
        data=[]
        for i,row in enumerate(rows):
            cells=[]
            for cell in row[1]:
                if cell[2:4]!=[1,1]: raise ValueError('Spanning table cell requires explicit handling')
                flows=self.blocks(cell[4],cell=True)
                if i==0:
                    flows=[self.para(f.text,'cellhead') if isinstance(f,Paragraph) else f for f in flows]
                cells.append(flows or self.para('','cell'))
            data.append(cells)
        # Fit widths to content with a cap so long cells wrap into readable columns.
        n=len(colspec)
        weights=[]
        for j in range(n):
            lengths=[sum(len(f.getPlainText()) for f in row[j] if isinstance(f,Paragraph)) for row in data]
            weights.append(max(4,min(34,max(lengths)**0.58*3)))
        widths=[TEXT_WIDTH*w/sum(weights) for w in weights]
        table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1,splitInRow=0)
        table.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E5EFF2')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F6F8F9')]),
            ('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#AAC2CD')),
            ('LINEBELOW',(0,1),(-1,-1),.3,colors.HexColor('#DCE4E7')),
            ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ]))
        table.spaceAfter=12
        return table

    def add_part(self,title,subtitle,name):
        self.story.append(PageBreak())
        self.story.append(Spacer(1,65*mm))
        p=self.para(title,'part'); p.book_entry=(0,title,name,True)
        self.story.extend([p,self.para(subtitle),PageBreak()])

    def run(self):
        OUT.mkdir(parents=True,exist_ok=True)
        upper=ROOT/'上册-研究报告'; lower=ROOT/'下册-案例汇编'
        upper_paths=[upper/'README.md']+sorted(upper.glob('0[0-6]-*.md'))+sorted(upper.glob('附录*.md'))
        index=json.loads((ROOT/'索引/案例来源索引.json').read_text())
        lower_paths=[lower/'README.md']
        groups=[]
        for e in index['entries']:
            path=ROOT/e['path']
            if path.parent not in groups:
                groups.append(path.parent); lower_paths.append(path.parent/'README.md')
            lower_paths.append(path)
        extra_paths=[ROOT/'索引/阅读路径.md',ROOT/'索引/资料来源说明.md']
        paths=upper_paths+lower_paths+extra_paths
        docs={path:self.load(path) for path in paths}
        for path,blocks in docs.items(): self.register(path,blocks)
        self.story.extend([Spacer(1,43*mm),self.para('企业数智化转型<br/>研究报告','part'),
                           self.para('从智力服务到精益经营','h1'),Spacer(1,16*mm),
                           self.para('上册 · 研究报告<br/>下册 · 企业AI案例汇编','h2'),
                           Spacer(1,30*mm),self.para('一芥智能研究院','h2'),
                           self.para(f'两册初稿合订本  |  {VERSION}<br/>{DATE}','small'),PageBreak()])
        p=self.para('版本与使用说明','h1')
        self.story.extend([Anchor(['publication-note']),p])
        self.current=ROOT/'README.md'
        for text in [
            f'本合订本根据{DATE}保存的稿件编排。上册为初稿 v8.0，下册为初稿 v7.0；两册沿用各自内容版本。',
            '本书由一芥智能研究院编写，面向企业经营者、业务负责人和参与组织改造的实践者。上册按问题论证，下册按行业、公司或项目集中呈现案例。',
            '收录上册导论、五章正文、结语与四个附录，下册62个案例入口及行业索引，另附问题阅读路径与资料来源说明。草稿箱、思维导图编辑数据和历史更新记录不编入正文。',
            '正文区分来源事实、一芥分析与待验证判断，并保留使用阶段、效果口径和来源定位。本书未对案例效果作独立审计或完整事实核验。',
            '本书只作经营管理分析与案例整理，不构成法律、财务、税务、医疗或其他专业意见；涉及具体业务操作时，请咨询相应执业者。',
            'Copyright © 2026 一芥智能研究院。MIT许可适用于本仓库有权许可的原创正文、分析与索引；第三方音视频、图书和资料由相应权利人持有。',
            '目录、书签和文内案例引用可跳转；公开出处可点击访问。结构化来源索引与历史更新记录通过项目仓库查阅。',
        ]: self.story.append(self.para(escape(text)))
        self.story.append(self.para('<a href="https://github.com/scottzx/ai-in-organization" color="#227C80">项目仓库与持续更新</a>  ·  <a href="https://github.com/scottzx/ai-in-organization/blob/main/LICENSE" color="#227C80">完整MIT许可证</a>'))
        self.story.extend([PageBreak(),self.para('目录','h1')])
        toc=TableOfContents(); toc.levelStyles=[self.styles['toc0'],self.styles['toc1']]
        toc.dotsMinLevel=0
        self.story.append(toc)
        for title,sub,name,part_paths in [
            ('上册  研究报告','从智力服务到精益经营  |  初稿 v8.0','upper-volume',upper_paths),
            ('下册  企业AI案例汇编','62个阅读入口 · 101个场景与证据片段  |  初稿 v7.0','lower-volume',lower_paths),
            ('阅读与来源索引','按研究问题阅读 · 资料来源说明','source-indexes',extra_paths),
        ]:
            self.add_part(title,sub,name)
            for i,path in enumerate(part_paths):
                if i: self.story.append(PageBreak())
                self.current=path
                self.story.append(Anchor([key(path)]))
                self.story.extend(self.blocks(docs[path]))
                self.sources.append({'path':str(path.relative_to(ROOT)),
                                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        doc=BookDoc(PDF); doc.multiBuild(self.story)
        reader=PdfReader(PDF)
        page_texts=[]
        for number,page in enumerate(reader.pages,1):
            lines=(page.extract_text() or '').splitlines()
            if number>1:
                chrome_end=next(i for i,line in enumerate(lines[:6]) if line.strip()==str(number))
                lines=lines[chrome_end+1:]
            page_texts.append('\n'.join(lines))
        extracted=''.join(page_texts)
        empty=[i for i,text in enumerate(page_texts,1) if not text.strip()]
        if empty: raise ValueError(f'Empty PDF body pages: {empty}')
        normalize=lambda s:re.sub(r'\s+','',s)
        compact=normalize(extracted)
        missing=[t for t in self.coverage if normalize(t) not in compact]
        if missing: raise ValueError(f'PDF content check failed ({len(missing)}): {missing[:3]}')
        annotations=Counter()
        page_ids={page.indirect_reference.idnum for page in reader.pages}
        for page in reader.pages:
            for ref in page.get('/Annots',[]):
                a=ref.get_object()
                if a.get('/Subtype')=='/Link':
                    annotations['external' if a.get('/A',{}).get('/URI') else 'internal']+=1
                    destination=a.get('/Dest')
                    if destination and destination[0].idnum not in page_ids:
                        raise ValueError('PDF internal link points outside this document')
        manifest={'title':TITLE,'manuscript_date':'2026-10-11','versions':{'upper':'v8.0','lower':'v7.0'},
                  'pdf':PDF.name,'pages':len(reader.pages),'sha256':hashlib.sha256(PDF.read_bytes()).hexdigest(),
                  'source_files':self.sources,'section_pages':doc.section_pages,
                  'case_entries':len(index['entries']),'scene_fragments':index['counts']['all_fragments'],
                  'content_checks':{'visible_text_fragments':len(self.coverage),'missing':len(missing),'empty_body_pages':empty},
                  'links':dict(self.links),'pdf_link_annotations':dict(annotations)}
        (OUT/'build-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:v for k,v in manifest.items() if k not in ('source_files','section_pages')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    Builder().run()
