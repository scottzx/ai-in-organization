#!/usr/bin/env python3
"""Build the public report reader: python3 scripts/build-site.py.

Only publication folders are rendered; drafts and local research copies stay out.
The build checks every generated internal link, image and fragment before exit.
"""
from pathlib import Path
from html import escape
from html.parser import HTMLParser
from urllib.parse import quote, unquote, urlsplit
from collections import Counter
import hashlib
import json
import os
import re
import shutil

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '_site'
REPO = 'https://github.com/scottzx/ai-in-organization'
SITE = os.environ.get('REPORT_SITE_URL', 'https://research.dreammate.work/report/ai-transformation-2026/').rstrip('/') + '/'
BACKUP_SITE = 'https://scottzx.github.io/ai-in-organization/'
ASSETS = {
    path.name: f'{path.stem}.{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}{path.suffix}'
    for path in (ROOT / 'web').iterdir()
    if path.is_file() and path.suffix in ('.css', '.js', '.svg', '.png')
}
MD = MarkdownIt('commonmark', {'html': True}).enable('table').enable('strikethrough')


def render_text(renderer, tokens, index, options, env):
    # CommonMark leaves CJK labels ending in punctuation unformatted when the
    # closing ** touches the next Chinese word. Preserve the manuscript's intent.
    value = escape(tokens[index].content, quote=False)
    return re.sub(r'\*\*([^*\n]*[：。；！？])\*\*', r'<strong>\1</strong>', value)


MD.add_render_rule('text', render_text)
VOLUMES = (
    ('上册-研究报告', '上册', '研究报告'),
    ('中册-行业解决方案', '中册', '行业方案'),
    ('下册-案例汇编', '下册', '案例汇编'),
)
UPPER = sorted((ROOT / '上册-研究报告').glob('[0-9][0-9]-*.md'))
APPENDICES = [ROOT / '上册-研究报告/附录A-术语辨析表.md']
PROCESS = ROOT / '过程稿'
MIDDLE_PLAN = json.loads((ROOT / 'scripts/data/middle/编写范围.json').read_text())
MIDDLE_GROUP_ENTRIES = {group['from'] for group in MIDDLE_PLAN.get('split_groups', [])}
MIDDLE = sorted(path for path in (ROOT / '中册-行业解决方案').glob('*.md')
                if path.name != 'README.md' and path.name not in MIDDLE_GROUP_ENTRIES)
CASE_INDEX = json.loads((ROOT / '索引/案例来源索引.json').read_text())
CASES = [ROOT / entry['path'] for entry in CASE_INDEX['entries']]
DOCS = {ROOT / name for name in ('README.md', 'CONTRIBUTING.md', 'CHANGELOG.md')}
for folder in ('上册-研究报告', '中册-行业解决方案', '下册-案例汇编', '索引', 'templates'):
    DOCS.update((ROOT / folder).rglob('*.md'))
DOCS = {
    path for path in DOCS
    if '研究记录' not in path.relative_to(ROOT).parts
    and not path.is_relative_to(PROCESS)
    and not (path.parent == ROOT / '上册-研究报告'
             and (path.name.startswith('备份-')
                  or (path.name.startswith('附录') and path not in APPENDICES)))
}
DOCS.update((ROOT / 'output').rglob('*.md'))
TITLES = {path: re.search(r'^#\s+(.+)$', path.read_text(), re.M)[1] for path in DOCS}
COPIED = set()
IMAGE_VERSIONS = {}


def output_path(path):
    relative = path.relative_to(ROOT)
    return relative.with_name('index.html') if path.name == 'README.md' else relative.with_suffix('.html')


def href(source, destination, fragment=''):
    target = output_path(destination) if destination in DOCS else destination.relative_to(ROOT)
    relative = os.path.relpath(target, output_path(source).parent)
    return quote(relative, safe='/.-') + ('#' + quote(fragment) if fragment else '')


def copy_asset(path):
    if path.is_relative_to(PROCESS):
        raise ValueError(f'Internal process file cannot be published: {path.name}')
    if path in COPIED:
        return
    target = OUT / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    COPIED.add(path)


def rewrite_url(source, value):
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return value
    destination = (source.parent / unquote(parsed.path)).resolve()
    if not destination.is_relative_to(ROOT) or not destination.exists():
        raise ValueError(f'Missing or out-of-repository link: {source.name}: {value}')
    if destination.is_relative_to(PROCESS):
        raise ValueError(f'Publication links to internal process file: {source.name}: {value}')
    if destination.parent == ROOT / 'output/pdf' and destination.suffix in ('.pdf', '.json'):
        # Existing exports describe earlier manuscripts and stay in the repository archive.
        return REPO + '/blob/main/' + quote(str(destination.relative_to(ROOT)), safe='/')
    if destination not in DOCS:
        # Drafts, scripts and editorial files can still be consulted on GitHub.
        relative_parts = destination.relative_to(ROOT).parts
        allowed = (relative_parts[0] in ('output', '索引')
                   or relative_parts[:2] == ('中册-行业解决方案', 'assets'))
        if allowed and destination.is_file() and destination.suffix in ('.png', '.svg', '.jpg', '.jpeg', '.webp', '.pdf', '.pptx', '.json', '.csv'):
            copy_asset(destination)
        else:
            return REPO + '/blob/main/' + quote(str(destination.relative_to(ROOT)), safe='/') + ('#' + quote(unquote(parsed.fragment)) if parsed.fragment else '')
    result = href(source, destination, unquote(parsed.fragment))
    query = parsed.query
    if destination in COPIED and destination.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.svg'):
        if destination not in IMAGE_VERSIONS:
            IMAGE_VERSIONS[destination] = hashlib.sha256(destination.read_bytes()).hexdigest()[:12]
        query += ('&' if query else '') + 'v=' + IMAGE_VERSIONS[destination]
    if query:
        result = result.split('#')[0] + '?' + query + ('#' + quote(unquote(parsed.fragment)) if parsed.fragment else '')
    return result


def slug(text):
    return re.sub(r'[^\w\-\s]', '', text.lower()).replace(' ', '-')


def reading_sequence(path):
    if path in MIDDLE:
        return MIDDLE
    if path in UPPER + APPENDICES:
        return UPPER + APPENDICES
    return []


def without_trailing_navigation(path, tokens):
    sequence = reading_sequence(path)
    if not sequence or len(tokens) < 3:
        return tokens
    opening, inline, closing = tokens[-3:]
    if (opening.type != 'paragraph_open' or opening.level != 0
            or inline.type != 'inline' or closing.type != 'paragraph_close'):
        return tokens
    targets = set(sequence) | {ROOT / folder / 'README.md' for folder, _, _ in VOLUMES}
    in_link = False
    links = 0
    for child in inline.children or []:
        if child.type == 'link_open':
            parsed = urlsplit(child.attrGet('href'))
            if (parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path
                    or (path.parent / unquote(parsed.path)).resolve() not in targets):
                return tokens
            in_link = True
            links += 1
        elif child.type == 'link_close':
            in_link = False
        elif not in_link and (child.type != 'text' or child.content.strip(' ·|')):
            return tokens
    if not links:
        return tokens
    tokens = tokens[:-3]
    if tokens and tokens[-1].type == 'hr':
        tokens = tokens[:-1]
    return tokens


def render_document(path):
    tokens = without_trailing_navigation(path, MD.parse(path.read_text()))
    headings = []
    counts = Counter()
    for index, token in enumerate(tokens):
        if token.type == 'heading_open':
            inline = tokens[index + 1]
            title = ''.join(child.content for child in inline.children or [] if child.type in ('text', 'code_inline'))
            anchor = slug(title)
            number = counts[anchor]
            counts[anchor] += 1
            if number:
                anchor += '-' + str(number)
            token.attrSet('id', anchor)
            if token.tag in ('h2', 'h3'):
                headings.append((token.tag[-1], title, anchor))
        for child in token.children or []:
            if child.type in ('link_open', 'image'):
                attr = 'src' if child.type == 'image' else 'href'
                original_url = child.attrGet(attr)
                rewritten_url = rewrite_url(path, original_url)
                if (child.type == 'image' and not urlsplit(original_url).scheme
                        and urlsplit(rewritten_url).scheme):
                    raise ValueError(f'Local publication image not packaged: {path.name}: {original_url}')
                child.attrSet(attr, rewritten_url)
                if child.type == 'image':
                    child.attrSet('loading', 'lazy')
                    child.attrSet('decoding', 'async')
    return MD.renderer.render(tokens, MD.options, {}), headings


def nav_link(current, target, label=None):
    selected = ' class="current" aria-current="page"' if current == target else ''
    return f'<a href="{href(current, target)}"{selected}>{escape(label or TITLES[target])}</a>'


def current_volume(current):
    folder = current.relative_to(ROOT).parts[0]
    return next((volume for volume in VOLUMES if volume[0] == folder), None)


def reading_navigation(current):
    sequence = reading_sequence(current)
    if not sequence:
        return ''
    volume = current_volume(current)
    directory = ROOT / volume[0] / 'README.md'
    links = [f'<a href="{href(current, directory)}">返回本章导航</a>']
    position = sequence.index(current)
    for offset, label, relation in [(-1, '上一章', 'prev'), (1, '下一章', 'next')]:
        neighbor = position + offset
        if 0 <= neighbor < len(sequence):
            target = sequence[neighbor]
            links.append(f'<a href="{href(current, target)}" rel="{relation}" '
                         f'title="{escape(TITLES[target], quote=True)}">{label}</a>')
    separator = '<span aria-hidden="true">·</span>'
    return f'<nav class="page-turn" aria-label="章节导航">{separator.join(links)}</nav>'


def volume_navigation(current):
    active = current_volume(current)
    links = ''
    for volume in VOLUMES:
        folder, number, label = volume
        short_label = {'上册': '报告', '中册': '方案', '下册': '案例'}[number]
        selected = ' class="current" aria-current="true"' if volume == active else ''
        links += (f'<a href="{href(current, ROOT / folder / "README.md")}"{selected}>'
                  f'<span class="volume-full">{number} · {label}</span>'
                  f'<span class="volume-short">{short_label}</span></a>')
    return f'<nav class="volume-nav" aria-label="分册导航">{links}</nav>'


def sidebar(current):
    volume = current_volume(current)
    if volume:
        folder, number, label = volume
        contents = f'<p class="nav-label">{number} · {label}</p>'
        contents += nav_link(current, ROOT / folder / 'README.md', '本册总览')
        if volume == VOLUMES[0]:
            contents += '<p class="nav-label">章节目录</p>'
            for target in UPPER:
                title = TITLES[target]
                for index, numeral in enumerate('一二三四五六七八', 1):
                    title = title.replace(f'第{numeral}章\u3000', f'{index:02d}　')
                contents += nav_link(current, target, title.split('：')[0])
            contents += '<p class="nav-label">附录</p>'
            for target in APPENDICES:
                contents += nav_link(current, target)
        elif volume == VOLUMES[1]:
            contents += '<p class="nav-label">行业方案与附录</p>'
            for target in MIDDLE:
                contents += nav_link(current, target, TITLES[target].split('：')[0])
        else:
            contents += '<p class="nav-label">行业案例与附编</p>'
            for folder in sorted({path.parent for path in CASES}):
                open_attr = ' open' if current.parent == folder else ''
                label = folder.name.replace('-', ' · ', 1)
                contents += f'<details{open_attr}><summary>{escape(label)}</summary>'
                contents += nav_link(current, folder / 'README.md', '查看本类概览')
                for target in CASES:
                    if target.parent == folder:
                        contents += nav_link(current, target)
                contents += '</details>'
    else:
        contents = '<p class="nav-label">全书导航</p>'
        contents += nav_link(current, ROOT / 'README.md', '报告首页')
        for folder, number, label in VOLUMES:
            contents += nav_link(current, ROOT / folder / 'README.md', f'{number} · {label}')
    contents += '<p class="nav-label">阅读指引</p>'
    contents += nav_link(current, ROOT / '索引/阅读路径.md', '按问题阅读')
    contents += '<p class="nav-label">资料与下载</p>'
    for target, label in [('output/pdf/README.md', '历史 PDF 归档'), ('索引/工信部行业数字化转型资料汇总.md', '工信部资料索引'), ('索引/资料来源说明.md', '资料来源与使用'), ('CHANGELOG.md', '修订记录')]:
        contents += nav_link(current, ROOT / target, label)
    nav_label = f'{volume[1]}目录' if volume else '全书导航'
    return (f'<nav class="sidebar-scroll" aria-label="{nav_label}" tabindex="0">{contents}</nav>'
            '<div class="sidebar-contact">'
            '<p class="nav-contact"><strong>联系电话：<a href="tel:13185000425">13185000425</a></strong></p>'
            '<p class="nav-address">联系地址：杭州市西湖区云谷中心</p></div>')


def footer(current):
    page = quote(str(output_path(current)), safe='/')
    prefix = os.path.relpath('.', output_path(current).parent)
    badge = quote(prefix + '/assets/' + ASSETS['cc-by-nc-sa-80x15.png'], safe='/.-')
    deed = 'https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans'
    return (f'<footer class="footer"><span class="footer-license">© 2026 一芥智能研究院 · '
            f'<a rel="license" href="{deed}">本作品采用 知识共享署名-非商业性使用-相同方式共享 4.0 国际许可协议 (CC BY-NC-SA 4.0) 进行许可</a>'
            f'<a rel="license" href="{deed}"><img class="cc-badge" alt="CC BY-NC-SA 4.0" src="{badge}" width="80" height="15"></a></span>'
            f'<span><a href="{SITE + page}">在线阅读</a> · '
            f'<a href="{BACKUP_SITE + page}">GitHub Pages 备用入口</a> · '
            f'<a href="{REPO}">GitHub 源文档 ↗</a></span></footer>')


def page_shell(current, body, description):
    prefix = os.path.relpath('.', output_path(current).parent)
    asset = lambda name: quote(prefix + '/assets/' + ASSETS[name], safe='/.-')
    title = '企业数智化转型研究报告' if current == ROOT / 'README.md' else TITLES[current]
    canonical = SITE + quote(str(output_path(current)), safe='/')
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)} · 一芥智能研究院</title><meta name="description" content="{escape(description, quote=True)}">
<meta name="theme-color" content="#285b4d"><meta property="og:type" content="article"><meta property="og:title" content="{escape(title, quote=True)}">
<meta property="og:description" content="{escape(description, quote=True)}"><meta property="og:url" content="{canonical}">
<link rel="canonical" href="{canonical}"><link rel="icon" href="{asset('favicon.svg')}" type="image/svg+xml"><link rel="stylesheet" href="{asset('site.css')}">
<script src="{asset('site.js')}" data-site defer></script></head><body>
<a class="skip" href="#main">跳到正文</a>
<header class="topbar"><a class="brand" aria-label="一芥智能研究院首页" href="{href(current, ROOT / 'README.md')}"><span class="brand-symbol">芥</span><span class="brand-text"><strong>一芥智能研究院</strong><small>YIJIE INTELLIGENCE INSTITUTE</small></span></a>
<div class="header-actions">{volume_navigation(current)}<button class="search-trigger" data-search aria-haspopup="dialog">搜索内容 <kbd>⌘ K</kbd></button><button id="menu-toggle" class="menu-toggle" aria-expanded="false" aria-controls="sidebar">目录 ☰</button></div></header>
<div class="layout"><aside id="sidebar" class="sidebar" aria-label="阅读导航">{sidebar(current)}</aside><div class="workspace">{body}</div></div>
<dialog id="search-dialog" aria-labelledby="search-label"><div class="search-top"><label id="search-label" for="search-input">搜索报告与案例</label><button id="search-close" aria-label="关闭搜索">×</button></div><input id="search-input" type="search" placeholder="试试：线索、制造业、组织变革…" autocomplete="off"><div id="search-results" aria-live="polite">输入关键词，搜索报告、案例与资料索引。</div></dialog>
</body></html>'''


def home_page(current):
    def link(target):
        return href(current, ROOT / target)
    counts = CASE_INDEX['counts']
    edition = re.search(r'\*\*一芥智能研究院\*\*｜.*?｜(.+?)\n', current.read_text())[1]
    rows = ''
    for number, path in enumerate(UPPER):
        label = TITLES[path].split('\u3000', 1)[-1]
        badge = '序' if number == 0 else ('终' if number == 9 else f'{number:02d}')
        rows += f'<a class="chapter-row" href="{href(current, path)}"><span class="number">{badge}</span><span>{escape(label)}</span><span class="arrow">↗</span></a>'
    return f'''<main id="main" class="home">
<div class="eyebrow">RESEARCH &amp; PRACTICE · 2026</div>
<section class="hero"><div><span class="edition">{escape(edition.replace('·', ' / '))}</span>
<h1>企业数智化转型<br>研究报告</h1><div class="subtitle">从智力服务到精益经营</div>
<p>过去为什么做数字化，建设到了什么程度，遇到了什么问题？由此研究今天为什么进一步推进数智化，以及怎样沿业务诊断、具体举措、跨线融合与组织变革落实改进。</p>
<div class="hero-buttons"><a class="button primary" href="{href(current, UPPER[0])}">开始阅读 <span>→</span></a><a class="button" href="{link('上册-研究报告/README.md')}">查看上册目录 <span>→</span></a><button id="copy-link" class="plain-button">分享本页 ↗</button></div></div>
<div class="book" aria-hidden="true"><small>YIJIE · RESEARCH 2026</small><div><div class="book-title">企业数智化<br>转型研究报告</div><div class="book-line"></div><div class="book-bottom">从智力服务到精益经营</div></div><div class="book-bottom">一芥智能研究院<br>研究报告 / 企业案例汇编</div></div></section>
<div class="stats"><div class="stat"><strong>8</strong><span>章研究</span><small>从经营问题到实施验证</small></div><div class="stat"><strong>{counts['entries']}</strong><span>个案例入口</span><small>按行业、公司与项目组织</small></div><div class="stat"><strong>{counts['all_fragments']}</strong><span>个场景片段</span><small>保留来源、阶段与口径</small></div><div class="stat"><strong>4</strong><span>条业务线</span><small>MTL / LTC / IPD / ITR</small></div></div>
<div class="section-heading"><h2>选择你的阅读路径</h2><a href="{link('索引/阅读路径.md')}">按经营问题查找 →</a></div>
<div class="volume-grid"><article class="volume-card"><span class="card-label">VOLUME 01 / 研究报告</span><h3>从智力服务到精益经营</h3><p>面向企业老板与业务负责人，沿业务现状、分析和改造举措，研究流程协同、组织分工与持续改进。</p><div class="flow-tags"><span>MTL 市场到线索</span><span>LTC 线索到回款</span><span>IPD 产品开发</span><span>ITR 问题到解决</span></div><a class="text-link" href="{link('上册-研究报告/README.md')}">查看上册目录 →</a></article>
<article class="volume-card"><span class="card-label">VOLUME 02 / 行业解决方案</span><h3>沿行业架构增加智力服务</h3><p>引用行业图谱，展开业务功能和应用模块，写清三化怎样协同建设，以及建什么、怎么建、怎样验收。</p><div class="flow-tags"><span>行业架构与模块</span><span>智力服务</span><span>建设与验收</span></div><a class="text-link" href="{link('中册-行业解决方案/README.md')}">查看中册行业方案 →</a></article>
<article class="volume-card"><span class="card-label">VOLUME 03 / 案例汇编</span><h3>在真实业务中看数字化与数智化</h3><p>按行业、公司或项目呈现业务背景、问题、实施过程、效果与启示。区分实际使用、试点、原型和设想。</p><div class="flow-tags"><span>制造业</span><span>批发与零售</span><span>信息技术</span><span>商务服务</span><span>更多行业</span></div><a class="text-link" href="{link('下册-案例汇编/README.md')}">浏览全部 {counts['entries']} 个入口 →</a></article></div>
<div class="section-heading"><h2>沿着问题，逐章展开</h2><span>导论 · 八章正文 · 结语</span></div><div class="chapter-grid">{rows}</div>
<div class="section-heading"><h2>资料与版本</h2><a href="{link('output/pdf/README.md')}">历史 PDF 归档 →</a></div>
<div class="resource-row"><a class="button" href="{link('output/pdf/README.md')}">历史 PDF 归档 <span>→</span></a><a class="button" href="{link('索引/工信部行业数字化转型资料汇总.md')}">工信部资料索引 <span>→</span></a></div>
<p class="evidence-note">本报告为持续修订的初稿。案例入口数不等于独立公司数或成功交付数；资料主要来自公开信息、受访者自述与演示，效果未经独立审计。原始来源、实施阶段和分析边界见各篇正文。中册按行业数字化方案持续扩充，数字化基础和新增服务分别检验。旧PDF作为历史版本保留，现行书稿以在线阅读版为准。</p>
{footer(current)}</main>'''


def volume_directory(current):
    volume = current_volume(current)
    headings = []
    content = f'<h1>{volume[1]} · {volume[2]}</h1>'

    def link(target, label=None, count=None, anchor=None):
        identifier = f' id="{escape(anchor, quote=True)}"' if anchor else ''
        detail = f'{count} 篇 ' if count is not None else ''
        return (f'<a class="directory-link"{identifier} href="{href(current, target)}">'
                f'<span>{escape(label or TITLES[target])}</span>'
                f'<span class="directory-count">{detail}<span aria-hidden="true">→</span></span></a>')

    def section(title, links):
        anchor = slug(title)
        headings.append(('2', title, anchor))
        return (f'<h2 id="{anchor}">{title}</h2>'
                f'<nav class="directory-grid" aria-label="{title}">{"".join(links)}</nav>')

    if volume == VOLUMES[0]:
        content += section('章节目录', [link(path) for path in UPPER])
        content += section('附录', [link(path) for path in APPENDICES])
    elif volume == VOLUMES[1]:
        content += section('引言', [link(path) for path in MIDDLE if path.name.startswith('00-')])
        content += section('分行业阅读', [link(path, TITLES[path].split('：')[0]) for path in MIDDLE
                                       if not path.name.startswith(('00-', '附录'))])
        content += section('选用对照与引用依据', [link(path) for path in MIDDLE if path.name.startswith('附录')])
    else:
        folders = sorted({path.parent for path in CASES})
        for title, groups in [('按行业阅读', [folder for folder in folders if not folder.name.startswith('附编')]),
                              ('附编', [folder for folder in folders if folder.name.startswith('附编')])]:
            content += section(title, [link(folder / 'README.md', folder.name.replace('-', ' · ', 1),
                                            sum(path.parent == folder for path in CASES), slug(folder.name))
                                       for folder in groups])
        content += section('原始出处与研究材料', [
            link(ROOT / '索引/资料来源说明.md', '案例来源与使用说明'),
            link(ROOT / '索引/工信部行业数字化转型资料汇总.md', '行业原文与企业资料'),
        ])
    return content, headings


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.duplicates = set()
        self.links = []
        self.words = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                self.duplicates.add(attrs['id'])
            self.ids.add(attrs['id'])
        for attr in ('href', 'src'):
            if attrs.get(attr):
                self.links.append(attrs[attr])

    def handle_data(self, data):
        self.words.append(data)


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'assets').mkdir(parents=True)
    for name, versioned_name in ASSETS.items():
        shutil.copy2(ROOT / 'web' / name, OUT / 'assets' / versioned_name)
    search_index = []
    for path in sorted(DOCS):
        volume = current_volume(path)
        is_volume_directory = volume and path == ROOT / volume[0] / 'README.md'
        content, headings = volume_directory(path) if is_volume_directory else render_document(path)
        plain = PageParser()
        plain.feed(content)
        text = re.sub(r'\s+', ' ', ' '.join(plain.words)).strip()
        description = text[:160]
        if path == ROOT / 'README.md':
            body = home_page(path)
        else:
            toc = '<p class="toc-title">本页目录</p>' + ''.join(f'<a class="level-{level}" href="#{quote(anchor)}">{escape(title)}</a>' for level, title, anchor in headings)
            volume = current_volume(path)
            label = volume[1] + ' · ' + volume[2] if volume else '阅读资料'
            if volume and path != ROOT / volume[0] / 'README.md':
                label = f'<a href="{href(path, ROOT / volume[0] / "README.md")}">{label}</a>'
            source_url = REPO + '/blob/main/' + quote(str(path.relative_to(ROOT)), safe='/')
            turn = reading_navigation(path)
            body = f'<div class="reading-layout"><main id="main" class="reading-main"><div class="breadcrumb"><a href="{href(path, ROOT / "README.md")}">报告首页</a> / {label}</div><div class="page-tools"><a href="{source_url}">查看 Markdown 源文档 ↗</a><button id="copy-link" class="plain-button">分享本页 ↗</button></div><article class="prose">{content}</article>{turn}{footer(path)}</main><aside class="toc" aria-label="本页目录">{toc}</aside></div>'
        destination = OUT / output_path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(page_shell(path, body, description), encoding='utf-8')
        search_index.append({'title': TITLES[path], 'url': quote(str(output_path(path)), safe='/'), 'text': text})
    (OUT / 'search-index.json').write_text(json.dumps(search_index, ensure_ascii=False), encoding='utf-8')
    # Keep published case URLs usable after a classification migration. Aliases
    # redirect to one live page and never become extra search/case entries.
    redirects = {}
    active_case_folders = {path.parent for path in CASES}
    for entry in CASE_INDEX['entries']:
        for previous_path in entry.get('previous_paths', []):
            source = ROOT / previous_path
            target = ROOT / entry['path']
            if source in redirects or source in DOCS:
                raise ValueError(f'Overlapping migrated case URL: {previous_path}')
            redirects[source] = target
            if source.parent not in active_case_folders:
                redirects[source.parent / 'README.md'] = ROOT / '下册-案例汇编/README.md'
    for source, target in redirects.items():
        relative = href(source, target)
        destination = OUT / output_path(source)
        if destination.exists():
            raise ValueError(f'Migration redirect would overwrite a page: {source}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>案例已更新分类</title><script>location.replace('
            + json.dumps(relative) + '+location.search+location.hash);</script>'
            '<p>案例已更新分类，<a href="' + escape(relative, quote=True)
            + '">前往现行页面</a>。</p></html>', encoding='utf-8')
    (OUT / '.nojekyll').touch()
    (OUT / '404.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>页面未找到</title><body style="font-family:system-ui;padding:10%;background:#f8f7f3;color:#285b4d"><h1>这篇内容可能已经调整</h1><p>请从报告首页重新查找，或使用首页的全文搜索。</p><a href="' + SITE + '">返回报告首页 →</a></body></html>', encoding='utf-8')
    # Validate the deployed paths, including cross-volume case anchors and assets.
    pages = {}
    for path in OUT.rglob('*.html'):
        parser = PageParser()
        parser.feed(path.read_text())
        if parser.duplicates:
            raise ValueError(f'Duplicate IDs: {path}: {parser.duplicates}')
        pages[path.resolve()] = parser
    errors = []
    for path, page in pages.items():
        for link in page.links:
            parsed = urlsplit(link)
            if parsed.scheme or parsed.netloc:
                continue
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not target.is_relative_to(OUT) or not target.exists():
                errors.append(f'{path.relative_to(OUT)}: missing {link}')
            elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
                errors.append(f'{path.relative_to(OUT)}: missing fragment {link}')
    if errors:
        raise ValueError('\n'.join(errors))
    print(json.dumps({'pages': len(pages), 'search_documents': len(search_index), 'case_redirects': len(redirects), 'assets': len(COPIED), 'cases': len(CASES), 'internal_links': 'passed', 'output': '_site'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
