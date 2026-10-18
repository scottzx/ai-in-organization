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
paths = [e['path'] for e in entries]
if len(paths) != len(set(paths)):
    errors.append('Duplicate publication case path')

# Industry is a single, mutually exclusive placement of the case subject.
# Scene topics and the customer's industry do not create extra placements.
industry_names = {
    'A': '农、林、牧、渔业', 'B': '采矿业', 'C': '制造业',
    'D': '电力、热力、燃气及水生产和供应业', 'E': '建筑业',
    'F': '批发和零售业', 'G': '交通运输、仓储和邮政业',
    'H': '住宿和餐饮业', 'I': '信息传输、软件和信息技术服务业',
    'J': '金融业', 'K': '房地产业', 'L': '租赁和商务服务业',
    'M': '科学研究和技术服务业', 'N': '水利、环境和公共设施管理业',
    'O': '居民服务、修理和其他服务业', 'P': '教育',
    'Q': '卫生和社会工作', 'R': '文化、体育和娱乐业',
    'S': '公共管理、社会保障和社会组织', 'T': '国际组织',
}
industry_folders = {
    'A': '农林牧渔业', 'B': '采矿业', 'C': '制造业',
    'D': '电力热力燃气及水生产和供应业', 'E': '建筑业',
    'F': '批发与零售业', 'G': '交通运输仓储与邮政业',
    'H': '住宿与餐饮业', 'I': '信息传输软件与信息技术服务业',
    'J': '金融业', 'K': '房地产业', 'L': '租赁与商务服务业',
    'M': '科学研究与技术服务业', 'N': '水利环境与公共设施管理业',
    'O': '居民服务修理与其他服务业', 'P': '教育',
    'Q': '卫生与社会工作', 'R': '文化体育与娱乐业',
    'S': '公共管理社会保障与社会组织', 'T': '国际组织',
}
for e in entries:
    case_id = e['id']
    code = e.get('industry_code')
    status = e.get('classification_status')
    entry_type = e.get('entry_type')
    path = Path(e['path'])
    if status in ('supported', 'provisional'):
        if code not in industry_names:
            errors.append(case_id+': classified case needs one valid industry code')
            continue
        if e.get('industry_name') != industry_names[code]:
            errors.append(case_id+': industry name does not match its code')
        if not re.fullmatch(re.escape(code)+r'\d{2}', case_id):
            errors.append(case_id+': publication ID does not match its industry code')
        expected_folder = code+'-'+industry_folders[code]
        if entry_type in ('method', 'reference'):
            errors.append(case_id+': method/reference must use not_applicable classification')
    elif status == 'pending':
        expected_folder = '待定-行业待核'
        if code is not None or not re.fullmatch(r'待\d{2}', case_id):
            errors.append(case_id+': pending case needs a temporary ID and null industry code')
        if e.get('industry_name') != '待定分类（非国标门类）':
            errors.append(case_id+': pending industry name mismatch')
        if entry_type in ('method', 'reference'):
            errors.append(case_id+': method/reference cannot be a pending industry case')
    elif status == 'not_applicable':
        appendix = {
            'method': ('附A', '附编A-跨行业方法', '跨行业方法附编'),
            'reference': ('附B', '附编B-原型与演示参考', '方法与探索参考附录'),
        }.get(entry_type)
        if appendix is None:
            errors.append(case_id+': not_applicable is only valid for method/reference entries')
            continue
        prefix, expected_folder, expected_name = appendix
        if code is not None or not re.fullmatch(re.escape(prefix)+r'\d{2}', case_id):
            errors.append(case_id+': appendix needs the matching ID prefix and null industry code')
        if e.get('industry_name') != expected_name:
            errors.append(case_id+': appendix industry name mismatch')
    else:
        errors.append(case_id+': invalid classification status '+str(status))
        continue
    if path.parent != Path('下册-案例汇编')/expected_folder:
        errors.append(case_id+': case directory does not match its classification')
    if path.name != case_id+'-'+e['title']+'.md':
        errors.append(case_id+': case filename does not match its ID and title')

# Old identifiers remain traceable without creating a second live placement.
previous_ids = []
previous_paths = []
for e in entries:
    aliases = e.get('previous_ids', [])
    old_paths = e.get('previous_paths', [])
    if len(aliases) != len(old_paths):
        errors.append(e['id']+': migration ID/path counts differ')
    previous_ids.extend(aliases)
    previous_paths.extend(old_paths)
    for old_path in old_paths:
        resolved = (ROOT/old_path).resolve()
        if not resolved.is_relative_to(ROOT/'下册-案例汇编') or resolved.suffix != '.md':
            errors.append(e['id']+': migration path must be a lower-volume Markdown path')
        if resolved.exists():
            errors.append(e['id']+': migrated case still exists at old path '+old_path)
    if aliases and not e.get('classification_review', {}).get('basis'):
        errors.append(e['id']+': migrated case needs a classification review')
if len(previous_ids) != len(set(previous_ids)) or set(previous_ids).intersection(ids):
    errors.append('A previous case ID is duplicated or overlaps a current case ID')
if len(previous_paths) != len(set(previous_paths)) or set(previous_paths).intersection(paths):
    errors.append('A previous case path is duplicated or overlaps a current case path')

# Editable manuscripts, including drafts and backups, use current filenames and
# citation labels. Explicit migration records can still name the old identifier.
old_filenames = {Path(old_path).name for old_path in previous_paths}
for path, text in texts.items():
    if path.name in old_filenames:
        errors.append(f'{path.relative_to(ROOT)}: case file still uses its previous name')
    for old_filename in old_filenames:
        if old_filename in unquote(text):
            errors.append(f'{path.relative_to(ROOT)}: reference uses previous filename {old_filename}')
    for old_id in previous_ids:
        escaped = re.escape(old_id)
        if re.search(r'^#\s+'+escaped+r'\s|\['+escaped+r'\s|（'+escaped+r'）|\('+escaped+r'\)', text, re.M):
            errors.append(f'{path.relative_to(ROOT)}: title or citation uses previous case ID {old_id}')

# Each case has one table row in the book index and its own industry index.
# Other navigation links are deliberately excluded from row counting.
case_row = re.compile(
    r'^\|\s*((?:附[A-B]|[A-T]|待)\d{2})\s*\|\s*'
    r'\[([^\]\n]+)\]\(([^)\n]+)\)\s*\|', re.M)
def check_case_index(index_path, expected_entries):
    rows = case_row.findall(texts.get(index_path, ''))
    row_counts = Counter(row[0] for row in rows)
    expected = {e['id']: e for e in expected_entries}
    for case_id, entry in expected.items():
        if row_counts[case_id] != 1:
            errors.append(f'{index_path.relative_to(ROOT)}: expected one row for {case_id}; found {row_counts[case_id]}')
    for case_id, title, target in rows:
        if case_id not in expected:
            errors.append(f'{index_path.relative_to(ROOT)}: unexpected case row {case_id}')
            continue
        parsed = urlsplit(target.strip().strip('<>'))
        dest = (index_path.parent/unquote(parsed.path)).resolve()
        if parsed.scheme or parsed.netloc or parsed.fragment or dest != (ROOT/expected[case_id]['path']).resolve():
            errors.append(f'{index_path.relative_to(ROOT)}: wrong case target for {case_id}')
        if title != expected[case_id]['title']:
            errors.append(f'{index_path.relative_to(ROOT)}: wrong case title for {case_id}')

check_case_index(ROOT/'下册-案例汇编/README.md', entries)
by_folder = {}
for e in entries:
    by_folder.setdefault(Path(e['path']).parent, []).append(e)
for folder, folder_entries in by_folder.items():
    check_case_index(ROOT/folder/'README.md', folder_entries)
# Also catch stale rows left behind in a now-empty industry directory.
for index_path in (ROOT/'下册-案例汇编').glob('*/README.md'):
    if index_path.parent.relative_to(ROOT) not in by_folder:
        check_case_index(index_path, [])

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
expected_counts = {
    'entries': len(entries),
    'industry_and_pending_entries': sum(e['entry_type'] not in ('reference', 'method') for e in entries),
    'methods': sum(e['entry_type'] == 'method' for e in entries),
    'references': sum(e['entry_type'] == 'reference' for e in entries),
    'source_records_main_fragment': len(source_records),
    'practice_fragments': sum(len(e['fragments']) for e in entries if e['entry_type'] != 'reference'),
    'reference_fragments': sum(len(e['fragments']) for e in entries if e['entry_type'] == 'reference'),
    'all_fragments': len(fragments),
}
for name, count in expected_counts.items():
    if index['counts'].get(name) != count:
        errors.append(f'Case index count mismatch: {name} expected {count}, found {index["counts"].get(name)}')
case_paths = {ROOT/e['path'] for e in entries}
unindexed = [str(p.relative_to(ROOT)) for p in texts if '下册-案例汇编' in p.parts and p.name!='README.md' and p not in case_paths]
if unindexed:
    errors.append('Unindexed case documents: '+str(unindexed))
upper_documents = sorted((ROOT/'上册-研究报告').glob('[0-9][0-9]-*.md'))
expected_numbers = [f'{number:02d}' for number in range(10)]
actual_numbers = [path.name[:2] for path in upper_documents]
if actual_numbers != expected_numbers:
    errors.append('Expected one upper-volume document for each number 00–09 '
                  '(导论, eight chapters and 结语); found '+', '.join(actual_numbers))
chapters = [path for path in upper_documents if path.name[:2] not in ('00', '09')]
appendices = {path.name for path in (ROOT/'上册-研究报告').glob('附录*.md')}
if appendices != {'附录A-术语辨析表.md'}:
    errors.append('Only appendix A belongs in the published upper volume; found '+str(sorted(appendices)))
if len((ROOT/'LICENSE').read_text().splitlines()) < 15:
    errors.append('Missing complete license')
summary = {'passed':not errors,'markdown_documents':len(documents),'upper_chapters':len(chapters),'upper_documents':len(upper_documents),'case_documents':len(entries),'case_structures_checked':len(entries),'scene_fragments':len(fragments),'local_links_checked':link_count,'errors':errors}
print(json.dumps(summary, ensure_ascii=False, indent=2))
sys.exit(0 if not errors else 1)
