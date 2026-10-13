#!/usr/bin/env python3
"""Validate the book's files, links, case IDs and scene coverage (stdlib only)."""
from pathlib import Path
from collections import Counter
from urllib.parse import unquote, urlsplit
import importlib.util
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []
documents = sorted(ROOT.rglob('*.md'))
texts = {p: p.read_text(encoding='utf-8') for p in documents}
anchors = {}
link_count = 0

for path, text in texts.items():
    explicit = re.findall(r'<a\s+id="([^"]+)"\s*>', text)
    duplicates = [k for k,v in Counter(explicit).items() if v > 1]
    if duplicates:
        errors.append(f'{path.relative_to(ROOT)}: duplicate anchors {duplicates}')
    anchors[path] = set(explicit)
    for heading in re.findall(r'^#{1,6}\s+(.+)$', text, re.M):
        slug = re.sub(r'[^\w\-\s]', '', heading.lower()).replace(' ', '-')
        anchors[path].add(slug)
    if re.search(r'/Users/|/private/tmp/|chatgpt-conversation:|app://|file://', text):
        errors.append(f'{path.relative_to(ROOT)}: non-portable/private path or conversation link')

def check_link(path, target):
    global link_count
    target = target.strip().strip('<>')
    if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I):
        if not target.startswith(('https://','http://','mailto:')):
            errors.append(f'{path.relative_to(ROOT)}: unsupported external link {target}')
        return
    link_count += 1
    parsed = urlsplit(target)
    dest = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
    if not dest.is_relative_to(ROOT):
        errors.append(f'{path.relative_to(ROOT)}: link leaves repository: {target}')
    elif not dest.exists():
        errors.append(f'{path.relative_to(ROOT)}: missing link target: {target}')
    elif parsed.fragment and dest.suffix == '.md':
        if unquote(parsed.fragment) not in anchors.get(dest, set()):
            errors.append(f'{path.relative_to(ROOT)}: missing anchor: {target}')

for path, text in texts.items():
    # Exclude code blocks from link parsing.
    text = re.sub(r'```[\s\S]*?```', '', text)
    for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', text):
        check_link(path, target)
    defs = dict(re.findall(r'^\[([^\]\n]+)\]:\s*(\S+)', text, re.M))
    uses = re.findall(r'(?<!!)\[[^\]\n]+\]\[([^\]\n]+)\]', text)
    for name in uses:
        if name not in defs:
            errors.append(f'{path.relative_to(ROOT)}: undefined reference [{name}]')
    for target in defs.values():
        check_link(path, target)

index = json.loads((ROOT/'索引/案例来源索引.json').read_text())
entries = index['entries']
structure_spec = importlib.util.spec_from_file_location('case_structure', ROOT/'scripts/check-case-structure.py')
structure_checker = importlib.util.module_from_spec(structure_spec)
structure_spec.loader.exec_module(structure_checker)
for e in entries:
    result = structure_checker.check_case(ROOT/e['path'])
    errors.extend(e['id']+': '+message for message in result['errors'])
ids = [e['id'] for e in entries]
if len(ids) != len(set(ids)):
    errors.append('Duplicate publication case ID')
fragments = []
source_records = set()
for e in entries:
    path = ROOT / e['path']
    text = texts.get(path, '')
    if not text.startswith('# '+e['id']+' '+e['title']):
        errors.append(e['id']+': title or case document missing')
    if e['entry_type'] != 'reference':
        source_records.add(e['source_record_id'])
    if not e['fragments']:
        errors.append(e['id']+': empty case')
    for f in e['fragments']:
        fragments.append(f['source_fragment_id'])
        if f['anchor'] not in anchors.get(path, set()):
            errors.append(e['id']+': missing scene '+f['source_fragment_id'])
        scene_anchor = re.search(r'<a\s+id="'+re.escape(f['anchor'])+r'"\s*>', text)
        if scene_anchor:
            following_anchor = re.search(r'<a\s+id="[^"]+"\s*>', text[scene_anchor.end():])
            end = scene_anchor.end()+following_anchor.start() if following_anchor else len(text)
            scene_text = text[scene_anchor.end():end]
            if '**阶段：'+f['stage_label']+'。**' not in scene_text:
                errors.append(e['id']+': scene stage mismatch '+f['source_fragment_id'])
        if not f['sources']:
            errors.append(e['id']+': no source '+f['source_fragment_id'])
        for s in f['sources']:
            if not s.get('url','').startswith('https://'):
                errors.append(e['id']+': missing public source URL')
            if s['line_end'] < s['line_start'] or s['line_start'] < 1:
                errors.append(e['id']+': invalid source line range')
            if not re.fullmatch(r'[0-9a-f]{64}',s['document_sha256']):
                errors.append(e['id']+': invalid source version hash')

if len(fragments)!=len(set(fragments)):
    errors.append('A source scene is duplicated across case documents')
if len(source_records)!=index['counts']['source_records_main_fragment']:
    errors.append('Practice source-record count mismatch')
if len(entries)!=index['counts']['entries'] or len(fragments)!=index['counts']['all_fragments']:
    errors.append('Entry/scene totals mismatch')
case_paths = {ROOT/e['path'] for e in entries}
unindexed = [str(p.relative_to(ROOT)) for p in texts if '下册-案例汇编' in p.parts and p.name!='README.md' and p not in case_paths]
if unindexed:
    errors.append('Unindexed case documents: '+str(unindexed))
chapters = list((ROOT/'上册-研究报告').glob('0[1-6]-*.md'))
if len(chapters)!=6:
    errors.append('Expected five upper-volume chapters plus 结语')
if len((ROOT/'LICENSE').read_text().splitlines()) < 15:
    errors.append('Missing complete license')
summary = {'passed':not errors,'markdown_documents':len(documents),'upper_chapters':len(chapters),'case_documents':len(entries),'case_structures_checked':len(entries),'scene_fragments':len(fragments),'local_links_checked':link_count,'errors':errors}
print(json.dumps(summary, ensure_ascii=False, indent=2))
sys.exit(0 if not errors else 1)
