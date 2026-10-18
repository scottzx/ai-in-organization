#!/usr/bin/env python3
"""Build the distribution PDF from the maintained Markdown (Pandoc + ReportLab).

Usage: python3 scripts/build-pdf.py
       python3 scripts/build-pdf.py --volume upper
       python3 scripts/build-pdf.py --volume middle
       python3 scripts/build-pdf.py --volume lower
       python3 scripts/build-pdf.py --chapter 上册-研究报告/02-MTL-从市场到有效线索.md
       python3 scripts/build-pdf.py --output output/pdf/企业数智化转型研究报告-排版预览版.pdf
Override BOOK_BODY_FONT, BOOK_HEADING_FONT and BOOK_KAI_FONT for Chinese TTF fonts.
BOOK_DIAGRAM_FONT and BOOK_DIAGRAM_HEADING_FONT override illustration faces.
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
import argparse
from glob import glob
import xml.etree.ElementTree as ET

from reportlab.lib import colors
from reportlab.lib import textsplit
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Flowable, CondPageBreak,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus import paragraph as paragraph_module
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
TITLE = '企业数智化转型研究报告'
MANUSCRIPT_DATE = '2026-10-18'
DATE = '2026年10月18日'
UPPER_VERSION = 'v11.0'
MIDDLE_VERSION = 'v0.5'
LOWER_VERSION = 'v9.0'
VERSION = f'上册 {UPPER_VERSION} / 中册 {MIDDLE_VERSION} / 下册 {LOWER_VERSION}'
PDF = OUT / (TITLE + '-上中下册合订本.pdf')
NAVY = colors.HexColor('#17365D')
BLUE = colors.HexColor('#1D4ED8')
TABLE_BLUE = colors.HexColor('#3D73C6')
GRAY = colors.HexColor('#667581')
WIDTH, HEIGHT = A4
MARGIN = 21 * mm
TEXT_WIDTH = WIDTH - 2 * MARGIN
INK = colors.HexColor('#202020')
# ReportLab's default CJK rules omit common full-width Chinese punctuation.
textsplit.ALL_CANNOT_START += '，；：！？）》〉】〕”’…％'
paragraph_module.ALL_CANNOT_START = textsplit.ALL_CANNOT_START


def font_path(env, candidates):
    override = os.environ.get(env)
    if override:
        return override
    for candidate in candidates:
        for path in sorted(glob(candidate)):
            if Path(path).is_file():
                return path
    raise FileNotFoundError(f'Chinese font unavailable; set {env} to a TrueType font path')


def roman(number):
    result = ''
    for value, letters in ((1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),
                           (90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')):
        count, number = divmod(number, value)
        result += letters * count
    return result


def key(path, anchor=''):
    return 'd' + hashlib.sha256((str(path.relative_to(ROOT)) + '#' + anchor).encode()).hexdigest()[:22]


def plain(items):
    result = []
    for x in items:
        t, c = x['t'], x.get('c')
        if t == 'Str': result.append(c)
        elif t in ('Space', 'SoftBreak', 'LineBreak'): result.append(' ')
        elif t in ('Strong', 'Emph', 'Strikeout', 'SmallCaps', 'Superscript', 'Subscript'): result.append(plain(c))
        elif t == 'Link': result.append(plain(c[1]))
        # Image alt text describes a graphic; it is not a manuscript paragraph.
        elif t == 'Image': pass
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
            c.setStrokeColor(BLUE)
            p = c.beginPath(); p.moveTo(*points[0])
            for point in points[1:]: p.lineTo(*point)
            c.drawPath(p)
            x, y = points[-1]; px, py = points[-2]
            import math
            a = math.atan2(y-py, x-px)
            p = c.beginPath(); p.moveTo(x, y)
            p.lineTo(x-6*math.cos(a-.45), y-6*math.sin(a-.45))
            p.lineTo(x-6*math.cos(a+.45), y-6*math.sin(a+.45)); p.close()
            c.setFillColor(BLUE); c.drawPath(p, fill=1, stroke=0)
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
            c.setFillColor(colors.HexColor('#EAF1FF')); c.setStrokeColor(colors.HexColor('#B8C9E6'))
            c.roundRect(x,y-boxh/2,boxw,boxh,5,fill=1)
            c.setFillColor(NAVY); c.setFont('DiagramBody',8.5)
            c.drawCentredString(x+boxw/2,y-3,text)


class CaptionedFigure(Flowable):
    """Keep a graphic and its centered caption on the same page."""
    def __init__(self, graphic, caption):
        super().__init__()
        self.graphic, self.caption = graphic, caption
        self.spaceBefore = self.spaceAfter = 6
        self.gap = 6
        graphic.spaceBefore = graphic.spaceAfter = 0

    def wrap(self, available_width, available_height):
        self.width = min(TEXT_WIDTH, available_width)
        _, self.caption_height = self.caption.wrap(self.width, available_height)
        if isinstance(self.graphic, ManuscriptImage):
            self.graphic.max_height = HEIGHT - 45*mm - 12 - self.caption_height - self.gap
        _, graphic_height = self.graphic.wrap(self.width, max(0,available_height-self.caption_height-self.gap))
        self.height = graphic_height + self.gap + self.caption_height
        return self.width, self.height

    def draw(self):
        self.graphic.drawOn(self.canv,(self.width-self.graphic.width)/2,self.caption_height+self.gap)
        self.caption.drawOn(self.canv,0,0)


class ManuscriptImage(Flowable):
    """Keep a complete illustration together, retaining SVG text in the PDF.

    The repository's editable diagrams deliberately use this small SVG subset.
    Unsupported SVGs fall back to their Markdown PNG without extra dependencies.
    """
    SVG_TAGS = {'svg', 'g', 'title', 'desc', 'rect', 'polygon', 'polyline', 'circle', 'text'}

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.svg = None
        self.mode = 'raster'
        self.visible_text = []
        self.title = ''
        self.collapsed_title_band = None
        self.hAlign = 'CENTER'
        self.spaceBefore = self.spaceAfter = 6
        candidate = path if path.suffix.lower() == '.svg' else path.with_suffix('.svg')
        if candidate.exists():
            try:
                root = ET.parse(candidate).getroot()
                for node in root.iter():
                    tag = node.tag.rsplit('}', 1)[-1]
                    if tag not in self.SVG_TAGS or 'transform' in node.attrib:
                        raise ValueError(f'Unsupported SVG element: {tag}')
                    if any(name.rsplit('}', 1)[-1] == 'href' for name in node.attrib):
                        raise ValueError('External SVG resources are unsupported')
                viewbox = self.numbers(root.get('viewBox', ''))
                if len(viewbox) == 4:
                    self.origin_x, self.origin_y, self.source_width, self.source_height = viewbox
                else:
                    self.origin_x = self.origin_y = 0
                    self.source_width = self.number(root.get('width', '0'))
                    self.source_height = self.number(root.get('height', '0'))
                if self.source_width <= 0 or self.source_height <= 0:
                    raise ValueError('SVG dimensions must be positive')
                self.svg, self.path, self.mode = root, candidate, 'vector'
                self.visible_text = [''.join(node.itertext()) for node in root.iter()
                                     if node.tag.rsplit('}', 1)[-1] == 'text']
                self.title = next((''.join(node.itertext()) for node in root.iter()
                                   if node.tag.rsplit('}',1)[-1]=='title'),'')
                # The maintained chapter diagrams reserve a header band for the main title.
                # Move that title into the PDF caption and close its former empty band.
                title_nodes=[node for node in root.iter() if node.tag.rsplit('}',1)[-1]=='text'
                             and ''.join(node.itertext())==self.title]
                if len(title_nodes)==1 and self.number(title_nodes[0].get('y','0'))==177:
                    self.collapsed_title_band=(115,205)
                    self.source_height-=90
            except (ET.ParseError, ValueError) as error:
                if path.suffix.lower() == '.svg':
                    raise ValueError(f'Cannot draw {path}: {error}') from error
                print(f'SVG fallback for {candidate.relative_to(ROOT)}: {error}')
        if self.svg is None:
            self.bitmap = ImageReader(str(path))
            self.source_width, self.source_height = self.bitmap.getSize()
        # Reserve enough room for paragraph spacing even on a fresh page.
        self.max_height = HEIGHT - 45 * mm - self.spaceBefore - self.spaceAfter
        self.fit(TEXT_WIDTH)

    @staticmethod
    def numbers(value):
        return [float(n) for n in re.findall(r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?', value)]

    @classmethod
    def number(cls, value):
        values = cls.numbers(str(value))
        if not values: raise ValueError(f'Invalid SVG number: {value}')
        return values[0]

    def fit(self, available_width):
        scale = min(available_width / self.source_width, self.max_height / self.source_height)
        self.width, self.height = self.source_width * scale, self.source_height * scale
        self.scale = scale

    def wrap(self, available_width, available_height):
        self.fit(min(TEXT_WIDTH, available_width))
        # A small reduction can keep an illustration with the preceding prose.
        # Reset to its normal size on every measurement, including later passes.
        if self.height * .88 <= available_height < self.height:
            scale = max(0, available_height - .1) / self.height
            self.width *= scale
            self.height *= scale
            self.scale *= scale
        return self.width, self.height

    def draw(self):
        c = self.canv
        if self.svg is None:
            c.drawImage(self.bitmap, 0, 0, self.width, self.height, mask='auto')
            return
        c.saveState()
        c.translate(0, self.height)
        c.scale(self.scale, -self.scale)
        c.translate(-self.origin_x, -self.origin_y)
        self.draw_svg(self.svg, {})
        c.restoreState()

    def draw_svg(self, node, inherited):
        tag = node.tag.rsplit('}', 1)[-1]
        if tag in ('title', 'desc'): return
        if tag=='text' and self.title and ''.join(node.itertext())==self.title:
            return
        attrs = dict(inherited)
        attrs.update(node.attrib)
        attrs.update(dict(re.findall(r'([\w-]+)\s*:\s*([^;]+)', node.get('style', ''))))
        if tag in ('svg', 'g'):
            # Only presentation attributes inherit; geometry belongs to each node.
            presentation = {k: v for k, v in attrs.items() if k in (
                'fill', 'stroke', 'stroke-width', 'stroke-dasharray', 'stroke-linecap',
                'stroke-linejoin', 'font-family', 'font-size', 'font-weight', 'text-anchor',
            )}
            for child in node: self.draw_svg(child, presentation)
            return
        c = self.canv
        c.saveState()
        fill, stroke = attrs.get('fill', '#000000'), attrs.get('stroke', 'none')
        has_fill, has_stroke = fill != 'none', stroke != 'none'
        if has_fill: c.setFillColor(colors.toColor(fill))
        if has_stroke: c.setStrokeColor(colors.toColor(stroke))
        c.setLineWidth(self.number(attrs.get('stroke-width', 1)))
        c.setLineCap({'butt': 0, 'round': 1, 'square': 2}.get(attrs.get('stroke-linecap'), 0))
        c.setLineJoin({'miter': 0, 'round': 1, 'bevel': 2}.get(attrs.get('stroke-linejoin'), 0))
        dash = attrs.get('stroke-dasharray', 'none')
        c.setDash(self.numbers(dash) if dash != 'none' else [])
        number = lambda name, default=0: self.number(attrs.get(name, default))
        def ycoord(value):
            return value-90 if self.collapsed_title_band and value>=self.collapsed_title_band[1] else value
        if tag == 'rect':
            x, y, w, h = [number(k) for k in ('x', 'y', 'width', 'height')]
            if self.collapsed_title_band and y<=self.collapsed_title_band[0] and y+h>=self.collapsed_title_band[1]:
                h-=90
            y=ycoord(y)
            radius = min(number('rx'), w / 2, h / 2)
            c.roundRect(x, y, w, h, radius, fill=int(has_fill), stroke=int(has_stroke))
        elif tag == 'circle':
            c.circle(number('cx'), ycoord(number('cy')), number('r'), fill=int(has_fill), stroke=int(has_stroke))
        elif tag in ('polygon', 'polyline'):
            points = self.numbers(attrs.get('points', ''))
            if len(points) < 4 or len(points) % 2:
                raise ValueError(f'Invalid SVG points in {self.path}')
            points=[value if i%2==0 else ycoord(value) for i,value in enumerate(points)]
            p = c.beginPath(); p.moveTo(*points[:2])
            for i in range(2, len(points), 2): p.lineTo(*points[i:i+2])
            if tag == 'polygon': p.close()
            c.drawPath(p, fill=int(has_fill), stroke=int(has_stroke))
        elif tag == 'text':
            family = attrs.get('font-family', '')
            weight = attrs.get('font-weight')
            heading = weight in ('bold', '500', '600', '700', '800', '900') if weight is not None else 'STHeiti' in family
            c.setFont('DiagramHeading' if heading else 'DiagramBody', number('font-size', 16))
            c.translate(number('x'), ycoord(number('y')))
            c.scale(1, -1)  # SVG's text baseline remains upright after the Y flip.
            draw_text = {'middle': c.drawCentredString, 'end': c.drawRightString}.get(attrs.get('text-anchor'), c.drawString)
            draw_text(0, 0, ''.join(node.itertext()))
        c.restoreState()


class BookDoc(BaseDocTemplate):
    def __init__(self, path, edition='上中下册合订本', outline_offset=0, front_matter=True,
                 version=VERSION):
        super().__init__(str(path), pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
                         topMargin=23*mm, bottomMargin=22*mm,
                         title=TITLE, author='一芥智能研究院',
                         subject=f'从智力服务到精益经营；{edition}；{version}；{DATE}',
                         creator='一芥智能研究院 / Markdown + ReportLab')
        frame = Frame(MARGIN,22*mm,TEXT_WIDTH,HEIGHT-45*mm, leftPadding=0,
                      rightPadding=0,topPadding=0,bottomPadding=0)
        self.addPageTemplates(PageTemplate(id='book',frames=frame,onPageEnd=self.page_chrome))
        self.section_pages = {}
        self.current_part = ''
        self.current_chapter = ''
        self.edition = edition
        self.outline_offset = outline_offset
        self.front_matter = front_matter
        self.body_start_page = None if front_matter else 1
        self.previous_body_start_page = self.body_start_page

    def beforeDocument(self):
        self.previous_body_start_page = self.body_start_page
        self.body_start_page = None if self.front_matter else 1
        self.current_part = ''
        self.current_chapter = ''
        self.section_pages = {}
        self.page_labels = {}
        self.chrome_text = {}

    def page_label(self, number):
        if self.front_matter and number == 1:
            return ''
        start = self.body_start_page or self.previous_body_start_page
        if start is not None and number >= start:
            return str(number - start + 1)
        return roman(number - 1)

    def page_chrome(self, canvas, doc):
        label = self.page_label(doc.page)
        self.page_labels[doc.page] = label
        if self.front_matter and doc.page == 1:
            canvas.addPageLabel(0, prefix='封面')
            self.chrome_text[doc.page] = []
            return
        if self.front_matter and doc.page == 2:
            canvas.addPageLabel(1, style='ROMAN_UPPER', start=1)
        if doc.page == self.body_start_page:
            canvas.addPageLabel(doc.page - 1, style='ARABIC', start=1)
        canvas.saveState()
        canvas.setFont('BookBody',9)
        canvas.setFillColor(GRAY)
        canvas.drawString(MARGIN,HEIGHT-13*mm,TITLE)
        heading = self.current_chapter or self.current_part or '版本与目录'
        available = TEXT_WIDTH - pdfmetrics.stringWidth(TITLE, 'BookBody', 9) - 18
        while pdfmetrics.stringWidth(heading, 'BookBody', 9) > available:
            heading = heading[:-2] + '…'
        canvas.drawRightString(WIDTH-MARGIN,HEIGHT-13*mm,heading)
        canvas.setStrokeColor(colors.HexColor('#CBD7EE'))
        canvas.line(MARGIN,HEIGHT-16*mm,WIDTH-MARGIN,HEIGHT-16*mm)
        canvas.drawCentredString(WIDTH/2,12*mm,label)
        self.chrome_text[doc.page] = [TITLE, heading, label]
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if getattr(flowable, 'body_start', False):
            self.body_start_page = self.page
        if hasattr(flowable, 'running_title'):
            self.current_chapter = flowable.running_title
        if not isinstance(flowable,Paragraph) or not hasattr(flowable,'book_entry'): return
        level, title, name, toc = flowable.book_entry
        if level<2: self.canv.bookmarkPage(name)
        outline_level = max(0, level - self.outline_offset)
        self.canv.addOutlineEntry(title,name,level=outline_level,closed=(outline_level>0))
        if toc: self.notify('TOCEntry',(getattr(flowable,'toc_level',level),escape(title),self.page,name))
        if level == 0:
            self.current_part = title
            self.current_chapter = ''
        if hasattr(flowable,'source_path'):
            self.section_pages[flowable.source_path] = self.page


class Builder:
    def __init__(self, output=None, volume='all'):
        self.output = Path(output).resolve() if output else None
        self.volume = volume
        self.body_start_source = ROOT/'上册-研究报告/00-导论.md'
        self.fonts = {
            'BookBody': font_path('BOOK_BODY_FONT', [
                '/Applications/wpsoffice.app/Contents/Resources/office6/fonts/FangS-SC.ttf']),
            'BookHeading': font_path('BOOK_HEADING_FONT', ['/System/Library/Fonts/STHeiti Medium.ttc']),
            'BookKai': font_path('BOOK_KAI_FONT', [
                '/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*.asset/AssetData/Kaiti.ttc',
                '/Applications/wpsoffice.app/Contents/Resources/office6/fonts/HYKaiTiJ.ttf']),
            'DiagramBody': font_path('BOOK_DIAGRAM_FONT', ['/System/Library/Fonts/STHeiti Light.ttc']),
            'DiagramHeading': font_path('BOOK_DIAGRAM_HEADING_FONT', ['/System/Library/Fonts/STHeiti Medium.ttc']),
        }
        # Heiti's TTC index 1 is the Simplified Chinese face, matching the PNG/SVG generator.
        self.font_indices = {name: 1 if name.startswith('Diagram') and Path(path).name.startswith('STHeiti') else 0
                             for name, path in self.fonts.items()}
        for name, path in self.fonts.items():
            pdfmetrics.registerFont(TTFont(name,path,subfontIndex=self.font_indices[name]))
            pdfmetrics.registerFontFamily(name,normal=name,bold=name,italic=name,boldItalic=name)
        pdfmetrics.registerFontFamily('BookBody',normal='BookBody',bold='BookHeading',
                                      italic='BookBody',boldItalic='BookHeading')
        self.body_characters = pdfmetrics.getFont('BookBody').face.charToGlyph
        self.styles = {}
        for name,font,size,leading in [
            ('body','BookBody',12,28),('list','BookBody',12,28),('small','BookBody',9,16),
            ('h1','BookHeading',16,28),('h2','BookKai',15,28),
            ('h3','BookBody',14,28),('h4','BookBody',12,28),
            ('cell','BookBody',10.5,17),('cellhead','BookHeading',10.5,17),
            ('tablecaption','BookHeading',10.5,17),('figurecaption','BookHeading',10.5,17),
            ('part','BookHeading',24,36),('toc0','BookHeading',14,28),
            ('toc1','BookHeading',12,24),('toc2','BookBody',12,24),
            ('cover_title','BookHeading',30,44),('cover_subtitle','BookKai',18,30),
            ('cover_meta','BookBody',12,24),('cover_note','BookBody',10.5,20),
        ]:
            self.styles[name] = ParagraphStyle(name,fontName=font,
                fontSize=size,leading=leading,spaceBefore=0,spaceAfter=0,textColor=INK,
                alignment=TA_JUSTIFY if name in ('body','list') else TA_LEFT,
                firstLineIndent=24 if name in ('body','list') else 0,
                wordWrap='CJK',splitLongWords=True,keepWithNext=name in ('h1','h2','h3','h4','part'),
                allowWidows=0,allowOrphans=0)
        for name in ('part','cover_title','cover_subtitle','cover_meta','cover_note'):
            self.styles[name].alignment=TA_CENTER
        self.styles['cellhead'].textColor=colors.white
        self.styles['tablecaption'].textColor=colors.black
        self.styles['figurecaption'].textColor=colors.black
        self.styles['figurecaption'].alignment=TA_CENTER
        for level in range(3):
            self.styles[f'toc{level}'].leftIndent = level*18
            self.styles[f'toc{level}'].rightIndent = 32
        self.story=[]
        self.sources=[]
        self.coverage=[]
        self.links=Counter()
        self.included=set()
        self.anchors=set()
        self.current=None
        self.figures=[]
        self.tables=[]
        self.figure_captions=[]
        self.source_table_counts=Counter()
        self.table_titles=json.loads((ROOT/'scripts/pdf-table-captions.json').read_text())
        self.heading_context=''
        self.figure_text=[]
        self.publication_note=True
        self.middle_industry_groups=False

    def para(self,text,style='body'):
        # Preserve markup and entities while covering symbols absent in FangSong.
        text=''.join(part if part.startswith('<') else
                     ''.join(ch if ord(ch)<128 or ord(ch) in self.body_characters else
                             f'<font name="BookKai">{escape(ch)}</font>' for ch in part)
                     for part in re.split(r'(<[^>]*>)',text))
        return Paragraph(text,self.styles[style])

    def text_markup(self,text):
        return ''.join(escape(ch) if ord(ch) in self.body_characters else
                       f'<font name="BookKai">{escape(ch)}</font>' for ch in text)

    def href(self,target):
        parsed=urlsplit(target)
        if parsed.scheme in ('http','https','mailto'):
            self.links['external']+=1
            return escape(target,quote=True)
        dest=(self.current.parent/unquote(parsed.path)).resolve() if parsed.path else self.current
        if dest.is_relative_to(ROOT/'过程稿'):
            raise ValueError(f'Publication links to internal process file: {self.current}: {target}')
        if dest == ROOT/'README.md' and self.publication_note:
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

    def inline(self,items,strong=False):
        result=[]
        for x in items:
            t,c=x['t'],x.get('c')
            if t=='Str': result.append(self.text_markup(c))
            elif t in ('Space','SoftBreak'): result.append(' ')
            elif t=='LineBreak': result.append('<br/>')
            elif t in ('Strong','SmallCaps'):
                result.append(f'<font name="BookHeading" color="#000000">{self.inline(c,strong=True)}</font>')
            elif t in ('Emph','Strikeout','Superscript','Subscript'):
                tag={'Emph':'i','Strikeout':'strike','Superscript':'super','Subscript':'sub'}[t]
                result.append(f'<{tag}>{self.inline(c,strong=strong)}</{tag}>')
            elif t=='Link':
                color='#000000' if strong else '#1D4ED8'
                result.append(f'<a href="{self.href(c[2][0])}" color="{color}">{self.inline(c[1],strong=strong)}</a>')
            elif t=='Code': result.append(escape(c[1]))
            elif t=='Image': raise ValueError('Images must occupy their own Markdown paragraph')
            elif t in ('Span','Cite'): result.append(self.inline(c[1],strong=strong))
            elif t=='Quoted': result.append('“'+self.inline(c[1],strong=strong)+'”')
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
                # A linked image is still a figure; its link only opens the original.
                c=[item['c'][1][0] if item['t']=='Link' and len(item['c'][1])==1
                   and item['c'][1][0]['t']=='Image' else item for item in c]
                images=[x for x in c if x['t']=='Image']
                if images:
                    if any(x['t'] not in ('Image','Space','SoftBreak','LineBreak') for x in c):
                        raise ValueError('Images must occupy their own Markdown paragraph')
                    out.extend(self.image(x['c']) for x in images)
                    continue
                text=plain(c)
                if text:
                    self.coverage.append(text)
                    p=self.para(self.inline(c),'cell' if cell else ('small' if text.startswith(('本节来源','来源定位：')) else 'body'))
                    # Short, wholly bold labels introduce the following case or stage.
                    # Keep their first following block without changing body typography.
                    if (not cell and len(text)<=60
                            and any(item['t']=='Strong' for item in c)
                            and all(item['t'] in ('Strong','Space','SoftBreak') for item in c)):
                        p.keepWithNext=True
                    out.append(p)
                else:
                    names=[key(self.current,a) for x in c if x['t']=='RawInline'
                           for a in re.findall(r'id="([^"]+)"',x['c'][1])]
                    if names: out.append(Anchor(names))
            elif t=='Header':
                level,attrs,items=c; title=plain(items)
                self.heading_context=title
                names=list(dict.fromkeys([key(self.current,attrs[0]),key(self.current,slug(title))]))
                while out and isinstance(out[-1],Anchor):
                    names.extend(out.pop().names)
                previous_keeps=out and isinstance(out[-1],Paragraph) and (
                    out[-1].style.name in ('h1','h2','h3','h4') or out[-1].getKeepWithNext())
                if level>1 and not previous_keeps: out.append(CondPageBreak(100))
                out.append(Anchor(names))
                p=self.para(self.inline(items),f'h{min(level,4)}')
                if level==1:
                    is_volume_index = self.current.name=='README.md' and self.current.parent.name in ('上册-研究报告','中册-行业解决方案','下册-案例汇编')
                    is_middle_industry = (self.middle_industry_groups
                                          and self.current.parent.name=='中册-行业解决方案'
                                          and bool(re.match(r'[A-Z][0-9]{2}-',self.current.name)))
                    p.book_entry=(2 if is_middle_industry else 1,title,key(self.current),not is_volume_index)
                    if '下册-案例汇编' in self.current.parts and self.current.name!='README.md':
                        p.toc_level=2
                    p.source_path=str(self.current.relative_to(ROOT))
                    p.running_title=title
                    p.body_start=self.current==self.body_start_source
                elif '上册-研究报告' in self.current.parts:
                    p.book_entry=(level,title,names[0],level==2 and self.current.name!='README.md')
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
                        child[0]=self.para(prefix+child[0].text,'cell' if cell else 'list')
                    out.extend(child)
            elif t=='Table': out.append(self.table(c))
            elif t=='HorizontalRule': pass
            elif t=='BlockQuote': out.extend(self.blocks(c,cell))
            elif t=='Div': out.extend(self.blocks(c[1],cell))
            elif t=='Figure':
                # The image helper creates one external, centered caption from its title.
                out.extend(self.blocks(c[2],cell))
            elif t=='CodeBlock':
                if 'mermaid' in c[0][1]:
                    title='图D-1  知识网络的资源访问与知识维护流程'
                    self.figure_captions.append(title)
                    out.append(CaptionedFigure(KnowledgeDiagram(),self.para(escape(title),'figurecaption')))
                else: out.append(self.para(escape(c[1]).replace('\n','<br/>'),'small'))
            else: raise ValueError(f'Unsupported block: {t}')
        return out

    def image(self, c):
        parsed = urlsplit(c[2][0])
        if parsed.scheme or parsed.netloc:
            raise ValueError('PDF illustrations must use local repository paths')
        path = (self.current.parent / unquote(parsed.path)).resolve()
        path.relative_to(ROOT)
        image = ManuscriptImage(path)
        assets = {str(asset.relative_to(ROOT)): hashlib.sha256(asset.read_bytes()).hexdigest()
                  for asset in dict.fromkeys((path, image.path))}
        self.figures.append({'path': str(path.relative_to(ROOT)), 'rendered_source': str(image.path.relative_to(ROOT)),
                             'mode': image.mode, 'sha256': hashlib.sha256(image.path.read_bytes()).hexdigest(),
                             'assets': assets})
        self.figure_text.extend(image.visible_text)
        number=re.match(r'(\d+)-',path.stem)
        label=f'图2-{int(number[1]):02d}' if number and 'chapter-2' in path.parts else f'图{len(self.figures)}'
        title=f'{label}  {image.title or plain(c[1])}'
        self.figures[-1]['caption']=title
        self.figure_captions.append(title)
        return CaptionedFigure(image,self.para(escape(title),'figurecaption'))

    def table(self,c):
        _,_,colspec,head,bodies,foot=c
        headers=[' '.join(plain(block['c']) for block in cell[4] if block['t'] in ('Plain','Para'))
                 for cell in head[1][0][1]] if head[1] else []
        source=str(self.current.relative_to(ROOT))
        self.source_table_counts[source]+=1
        ordinal=self.source_table_counts[source]
        titles=self.table_titles.get(source,[])
        if ordinal<=len(titles) and titles[ordinal-1]['headers']==headers:
            title=titles[ordinal-1]['title']
        else:
            title=re.sub(r'^(?:\d+(?:\.\d+)*|[A-Z]\.\d+)\s*','',self.heading_context)+'对照表'
        caption=f'表{len(self.tables)+1}  {title}'
        self.tables.append({'source':source,'ordinal':ordinal,'headers':headers,'caption':caption})
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
                    flows=[self.para(re.sub(r'\s+color="[^"]*"','',f.text),'cellhead')
                           if isinstance(f,Paragraph) else f for f in flows]
                cells.append(flows or self.para('','cell'))
            data.append(cells)
        # Fit widths to content with a cap so long cells wrap into readable columns.
        n=len(colspec)
        weights=[]
        for j in range(n):
            lengths=[sum(len(f.getPlainText()) for f in row[j] if isinstance(f,Paragraph)) for row in data]
            weights.append(max(4,min(34,max(lengths)**0.58*3)))
        widths=[TEXT_WIDTH*w/sum(weights) for w in weights]
        data.insert(0,[self.para(escape(caption),'tablecaption')]+['']*(n-1))
        table=Table(data,colWidths=widths,repeatRows=2,hAlign='LEFT',splitByRow=1,splitInRow=0)
        table.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),('SPAN',(0,0),(-1,0)),
            ('BACKGROUND',(0,1),(-1,1),TABLE_BLUE),
            ('ROWBACKGROUNDS',(0,2),(-1,-1),[colors.white,colors.HexColor('#F1F5FF')]),
            ('LINEBELOW',(0,1),(-1,1),.7,TABLE_BLUE),
            ('LINEBELOW',(0,2),(-1,-1),.3,colors.HexColor('#C8D8F2')),
            ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
            ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
            ('LEFTPADDING',(0,0),(-1,0),0),('RIGHTPADDING',(0,0),(-1,0),0),
            ('TOPPADDING',(0,0),(-1,0),0),('BOTTOMPADDING',(0,0),(-1,0),6),
        ]))
        table.spaceBefore=table.spaceAfter=6
        return table

    def add_part(self,title,subtitle,name):
        self.story.append(PageBreak())
        self.story.append(Spacer(1,65*mm))
        p=self.para(title,'part'); p.book_entry=(0,title,name,True)
        self.story.extend([p,self.para(subtitle,'cover_meta'),PageBreak()])

    def run(self):
        OUT.mkdir(parents=True,exist_ok=True)
        upper=ROOT/'上册-研究报告'; middle=ROOT/'中册-行业解决方案'; lower=ROOT/'下册-案例汇编'
        upper_paths=[]; middle_paths=[]; lower_paths=[]; index=None
        if self.volume in ('upper','all'):
            numbered_upper_paths=sorted(upper.glob('[0-9][0-9]-*.md'))
            if [path.name[:2] for path in numbered_upper_paths] != [f'{number:02d}' for number in range(10)]:
                raise ValueError('Expected one upper-volume document for each number 00–09 '
                                 '(导论, eight chapters and 结语)')
            upper_paths=[upper/'README.md']+numbered_upper_paths+[upper/'附录A-术语辨析表.md']
        if self.volume in ('middle','all'):
            plan=json.loads((ROOT/'scripts/data/middle/编写范围.json').read_text())
            group_entries={group['from'] for group in plan.get('split_groups', [])}
            middle_paths=[middle/'README.md']+sorted(
                path for path in middle.glob('*.md')
                if path.name != 'README.md' and path.name not in group_entries)
        if self.volume in ('lower','all'):
            index=json.loads((ROOT/'索引/案例来源索引.json').read_text())
            lower_paths=[lower/'README.md']
            groups=[]
            for e in index['entries']:
                path=ROOT/e['path']
                if path.parent not in groups:
                    groups.append(path.parent); lower_paths.append(path.parent/'README.md')
                lower_paths.append(path)
        if self.volume in ('middle','lower'):
            self.body_start_source={'middle':middle,'lower':lower}[self.volume]/'README.md'
        labels={'upper':'上册 · 研究报告','middle':'中册 · 行业解决方案',
                'lower':'下册 · 企业数字化与数智化案例汇编'}
        versions={'upper':UPPER_VERSION,'middle':MIDDLE_VERSION,'lower':LOWER_VERSION}
        edition='上中下册合订本' if self.volume=='all' else labels[self.volume]
        version=VERSION if self.volume=='all' else f'{self.volume_name()} {versions[self.volume]}'
        cover_volumes='<br/>'.join(labels.values()) if self.volume=='all' else labels[self.volume]
        cover_edition='三册初稿合订本' if self.volume=='all' else f'{self.volume_name()}初稿'
        scope_note=f'本书根据{DATE}保存的稿件编排，版本为{version}。单册未收录的跨册引用链接至项目仓库。'
        case_count=len(index['entries']) if index else 0
        scene_count=index['counts']['all_fragments'] if index else 0
        middle_count=sum(bool(re.match(r'[A-Z][0-9]{2}-',path.name)) for path in middle_paths)
        notes={
            'upper':'上册收录导论、八章正文、结语与附录A术语辨析表。',
            'middle':f'中册收录引言、{middle_count}篇行业与专业业务方案及附录。',
            'lower':f'下册收录{case_count}个案例入口、{scene_count}个场景与证据片段及行业索引。',
        }
        contents_note=''.join(notes.values()) if self.volume=='all' else notes[self.volume]
        contents_note+='另附问题阅读路径与资料来源说明。过程稿、草稿箱、思维导图编辑数据和历史更新记录不编入正文。'
        extra_paths=[ROOT/'索引/阅读路径.md',ROOT/'索引/资料来源说明.md']
        self.middle_industry_groups=bool(middle_paths)
        paths=upper_paths+middle_paths+lower_paths+extra_paths
        docs={path:self.load(path) for path in paths}
        for path,blocks in docs.items(): self.register(path,blocks)
        self.story.extend([Spacer(1,38*mm),self.para('企业数智化转型<br/>研究报告','cover_title'),
                           Spacer(1,10*mm),self.para('从智力服务到精益经营','cover_subtitle'),Spacer(1,17*mm),
                           self.para(cover_volumes,'cover_meta'),
                           Spacer(1,40*mm),self.para('一芥智能研究院','cover_meta'),
                           Spacer(1,5*mm),self.para(f'{cover_edition}  |  {version}<br/>{DATE}','cover_note'),PageBreak()])
        p=self.para('版本与使用说明','h1')
        p.running_title='版本与使用说明'
        self.story.extend([Anchor(['publication-note']),p])
        self.current=ROOT/'README.md'
        for text in [
            scope_note,
            '本书由一芥智能研究院编写，面向企业经营者、业务负责人和参与组织改造的实践者。上册按问题论证，中册展示行业数字化方案与智力服务应用，下册按行业、公司或项目集中呈现案例。',
            contents_note,
            '正文区分来源事实、一芥分析与待验证判断，并保留使用阶段、效果口径和来源定位。本书未对案例效果作独立审计或完整事实核验。',
            '本书只作经营管理分析与案例整理，不构成法律、财务、税务、医疗或其他专业意见；涉及具体业务操作时，请咨询相应执业者。',
            'Copyright © 2026 一芥智能研究院。MIT许可适用于本仓库有权许可的原创正文、分析与索引；第三方音视频、图书、行业架构原图和资料由相应权利人持有；中册引用图示保留来源与页码，不纳入原创内容的MIT许可。',
            '目录、书签和文内案例引用可跳转；公开出处可点击访问。结构化来源索引与历史更新记录通过项目仓库查阅。',
        ]: self.story.append(self.para(escape(text)))
        self.story.append(self.para('<a href="https://github.com/scottzx/ai-in-organization" color="#1D4ED8">项目仓库与持续更新</a>  ·  <a href="https://github.com/scottzx/ai-in-organization/blob/main/LICENSE" color="#1D4ED8">完整MIT许可证</a>'))
        toc_title=self.para('目录','h1'); toc_title.running_title='目录'
        self.story.extend([PageBreak(),toc_title])
        toc=TableOfContents(); toc.levelStyles=[self.styles[f'toc{i}'] for i in range(3)]
        toc.dotsMinLevel=0
        self.story.append(toc)
        for title,sub,name,part_paths in [
            ('上册  研究报告',f'从智力服务到精益经营  |  初稿 {UPPER_VERSION}','upper-volume',upper_paths),
            ('中册  行业解决方案',f'{middle_count}篇行业与专业业务方案  |  初稿 {MIDDLE_VERSION}','middle-volume',middle_paths),
            ('下册  企业数字化与数智化案例汇编',f'{case_count}个阅读入口 · {scene_count}个场景与证据片段  |  初稿 {LOWER_VERSION}','lower-volume',lower_paths),
            ('阅读与来源索引','按研究问题阅读 · 资料来源说明','source-indexes',extra_paths),
        ]:
            if not part_paths: continue
            self.add_part(title,sub,name)
            current_middle_group=None
            for i,path in enumerate(part_paths):
                if i: self.story.append(PageBreak())
                self.current=path
                if path in middle_paths and re.match(r'[A-Z][0-9]{2}-',path.name):
                    group=path.name[0]
                    if group != current_middle_group:
                        heading=f"{group}-{plan['industry_groups'][group]}"
                        p=self.para(escape(heading),'h1')
                        p.book_entry=(1,heading,f'middle-industry-{group}',True)
                        p.running_title=heading
                        p.keepWithNext=True
                        self.story.append(p)
                        current_middle_group=group
                self.story.append(Anchor([key(path)]))
                self.story.extend(self.blocks(docs[path]))
                self.sources.append({'path':str(path.relative_to(ROOT)),
                                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        pdf=self.output or (PDF if self.volume=='all' else OUT/(TITLE+f'-{self.volume_name()}.pdf'))
        pdf.parent.mkdir(parents=True,exist_ok=True)
        doc=BookDoc(pdf,edition=edition,version=version)
        toc.formatter=doc.page_label
        doc.multiBuild(self.story)
        manifest=pdf.with_suffix('.manifest.json') if self.output or self.volume!='all' else OUT/'build-manifest.json'
        self.verify_and_manifest(doc, pdf, manifest, index=index, volume=self.volume)

    def volume_name(self):
        return {'upper':'上册','middle':'中册','lower':'下册','all':'上中下册合订本'}[self.volume]

    def run_chapter(self, chapter):
        path = (ROOT / chapter).resolve()
        path.relative_to(ROOT)
        if path.is_relative_to(ROOT/'过程稿'):
            raise ValueError(f'Internal process file is not a publication chapter: {chapter}')
        if path.suffix.lower() != '.md' or not path.is_file():
            raise ValueError(f'Chapter must be a repository Markdown file: {chapter}')
        OUT.mkdir(parents=True, exist_ok=True)
        self.publication_note = False
        blocks = self.load(path)
        self.register(path, blocks)
        self.current = path
        self.story.append(Anchor([key(path)]))
        self.story.extend(self.blocks(blocks))
        self.sources.append({'path': str(path.relative_to(ROOT)),
                             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        title = next((plain(b['c'][2]) for b in blocks if b['t'] == 'Header' and b['c'][0] == 1), path.stem)
        filename = re.sub(r'[\s<>:"/\\|?*：]+', '-', title).strip('-')
        pdf = self.output or OUT / f'{filename}-配图版.pdf'
        pdf.parent.mkdir(parents=True,exist_ok=True)
        doc = BookDoc(pdf, edition='上册 · 单章阅读版', outline_offset=1, front_matter=False)
        doc.multiBuild(self.story)
        self.verify_and_manifest(doc, pdf, pdf.with_suffix('.manifest.json'), chapter=path)

    def verify_and_manifest(self, doc, pdf, manifest_path, index=None, chapter=None, volume=None):
        reader=PdfReader(pdf)
        page_texts=[]
        for number,page in enumerate(reader.pages,1):
            lines=(page.extract_text() or '').splitlines()
            # Chrome is drawn after the body; remove only the verified trailing lines.
            chrome=doc.chrome_text[number]
            if chrome:
                if lines[-len(chrome):]!=chrome:
                    raise ValueError(f'Unexpected page header/footer text at page {number}')
                lines=lines[:-len(chrome)]
            page_texts.append('\n'.join(lines))
        extracted=''.join(page_texts)
        if '\x00' in extracted:
            raise ValueError('PDF contains an unmapped font glyph')
        expected_labels=[doc.page_labels[number] or '封面' for number in range(1,len(reader.pages)+1)]
        if reader.page_labels!=expected_labels:
            raise ValueError('PDF viewer page labels disagree with printed page numbers')
        # A full-page PNG is valid body content even though it has no extractable text.
        empty=[i for i,text in enumerate(page_texts,1) if not text.strip() and not reader.pages[i-1].images]
        if empty: raise ValueError(f'Empty PDF body pages: {empty}')
        normalize=lambda s:re.sub(r'\s+','',s)
        compact=normalize(extracted)
        missing=[t for t in self.coverage if normalize(t) not in compact]
        if missing: raise ValueError(f'PDF content check failed ({len(missing)}): {missing[:3]}')
        missing_figures=[t for t in self.figure_text if normalize(t) not in compact]
        if missing_figures: raise ValueError(f'PDF illustration text check failed ({len(missing_figures)}): {missing_figures[:3]}')
        captions=self.figure_captions+[table['caption'] for table in self.tables]
        missing_captions=[title for title in captions if normalize(title) not in compact]
        if missing_captions: raise ValueError(f'PDF caption check failed: {missing_captions[:3]}')
        annotations=Counter()
        page_ids={page.indirect_reference.idnum for page in reader.pages}
        for page in reader.pages:
            for ref in page.get('/Annots',[]):
                a=ref.get_object()
                if a.get('/Subtype')=='/Link':
                    annotations['external' if a.get('/A',{}).get('/URI') else 'internal']+=1
                    destination=a.get('/Dest') or a.get('/A',{}).get('/D')
                    if destination and destination[0].idnum not in page_ids:
                        raise ValueError('PDF internal link points outside this document')
        versions={'upper':UPPER_VERSION,'middle':MIDDLE_VERSION,'lower':LOWER_VERSION}
        if volume in ('upper','middle','lower'):
            versions={volume:versions[volume]}
        manifest={'title':TITLE,'manuscript_date':MANUSCRIPT_DATE,'versions':versions,
                  'pdf':pdf.name,'pages':len(reader.pages),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                  'source_files':self.sources,'section_pages':doc.section_pages,
                  'body_start_page':doc.body_start_page,
                  'section_page_labels':{path:doc.page_labels[page] for path,page in doc.section_pages.items()},
                  'page_labels':reader.page_labels,
                  'typography':{'fonts':self.fonts,'font_indices':self.font_indices,
                                'body_pt':12,'body_leading_pt':28,'paragraph_spacing_pt':0,
                                'headings_pt':[16,15,14,12],'table_pt':10.5,'table_leading_pt':17,
                                'body_bold_font':'BookHeading','body_bold_color':'#000000',
                                'list_first_line_indent_pt':24,'primary_color':'#1D4ED8',
                                'table_header_color':'#3D73C6','table_figure_spacing_pt':6,
                                'caption_pt':10.5,'table_caption_position':'above','figure_caption_position':'below_center'},
                  'content_checks':{'visible_text_fragments':len(self.coverage),'missing':len(missing),'empty_body_pages':empty,
                                    'illustration_text_fragments':len(self.figure_text),'missing_illustration_text':len(missing_figures),
                                    'captions':len(captions),'missing_captions':len(missing_captions)},
                  'figure_count':len(self.figures),
                  'table_count':len(self.tables),'tables':self.tables,'figure_captions':self.figure_captions,
                  'links':dict(self.links),'pdf_link_annotations':dict(annotations)}
        if index is not None:
            manifest.update(case_entries=len(index['entries']), scene_fragments=index['counts']['all_fragments'])
        if volume is not None:
            manifest.update(volume=volume,edition=doc.edition)
        if chapter is not None:
            manifest['chapter'] = str(chapter.relative_to(ROOT))
        if self.figures: manifest['illustrations'] = self.figures
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:v for k,v in manifest.items() if k not in ('source_files','section_pages','section_page_labels','page_labels','illustrations','tables','figure_captions')},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--chapter', help='Build one Markdown chapter and its own PDF manifest')
    scope.add_argument('--volume', choices=('upper','middle','lower','all'), default='all',
                       help='Build one volume or all three in a combined PDF (default: all)')
    parser.add_argument('--output', help='Save a separate preview PDF and manifest at this path')
    args = parser.parse_args()
    builder = Builder(args.output,volume=args.volume)
    if args.chapter: builder.run_chapter(args.chapter)
    else: builder.run()
