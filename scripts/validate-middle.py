#!/usr/bin/env python3
"""Check middle-volume scope, chapter sections, case links and figure provenance.

This checks publication consistency; factual review remains in the editorial records.
"""
from pathlib import Path
from urllib.parse import unquote,urlsplit
import hashlib
import json
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
MID=ROOT/'中册-行业解决方案'
DATA=ROOT/'scripts/data/middle'

# Middle-volume guide pages retired in PR #13 (deleted; `from` records kept).
RETIRED_GUIDES={
 'A00-农业与养殖导读.md',
 'B00-采矿导读.md',
 'C08-00-建材导读.md',
 'C09-00-电子信息与关键部件导读.md',
 'C10-00-家电与轻工导读.md',
 'C12-00-食品饮料导读.md',
 'C13-00-医药与医疗装备导读.md',
 'D00-能源与公用事业导读.md',
 'F00-批发与零售导读.md',
 'G00-运输仓储与物流导读.md',
 'H00-住宿与餐饮导读.md',
 'I00-软件与信息服务导读.md',
 'J00-金融导读.md',
 'L00-商务服务导读.md',
 'M00-专业技术服务导读.md',
 'R00-文化体育与文旅导读.md',
}

LOWER=ROOT/'下册-案例汇编'

def reference_style_errors(name,number,record):
 """GB/T 7714 page, page-range and document-number rules shared by 中册 and 下册."""
 errs=[]
 if re.search(r'\[\d{4}-\d{2}-\d{2}\]\s*[:：]',record):
  errs.append(name+': reference ['+number+'] places page numbers after the access date; use "年: 页码[引用日期]."')
 if re.search(r': [\d, —–-]*[—–][\d, —–-]*\[\d{4}-\d{2}-\d{2}\]',record):
  errs.append(name+': reference ['+number+'] page range must use half-width "-"')
 if re.search(r'\[[^\]\n]*：[^\]：\n]{1,20}〔\d{4}〕\d+号\]\(',record):
  errs.append(name+': reference ['+number+'] document number inside linked title; use "[题名](URL): 文号"')
 if re.search(r'(?<!〔)[\[（(【](?:19|20)\d{2}[\]）)】]\d+号',record):
  errs.append(name+': reference ['+number+'] document number year must use 〔〕')
 if re.search(r'\[\d{4}-\d{2}-\d{2}\]\s*[.．。]?\s*[（(]?\s*(?:PDF)?第\s*\d+\s*(?:[—–-]\s*\d+\s*)?页',record):
  errs.append(name+': reference ['+number+'] has a bare page locator right after the access date; use "年: 页码[引用日期]."')
 if re.search(r'\[\d{4}-\d{2}-\d{2}\]\s*[.．。]?\s*[（(]?\s*第[^页。；\n]*?节',record):
  errs.append(name+': reference ['+number+'] has a bare section locator right after the access date; fold it into the note, e.g. "引用范围：第x节，…"')
 if re.search(r'\[\d{4}-\d{2}-\d{2}\]\s*[.．。]?\s*[（(]?\s*第[^页节。；\n]*?(?:项|部分)',record):
  errs.append(name+': reference ['+number+'] has a bare clause locator (第…项/部分) right after the access date; write "引用范围：第…项/第…部分，…"')
 if any(re.search(r',(?! )|[，、]',m) for m in re.findall(r': (\d+(?:-\d+)?(?:\s*[,，、]\s*\d+(?:-\d+)?)+)\[\d{4}-\d{2}-\d{2}\]',record)):
  errs.append(name+': reference ['+number+'] discrete page numbers must be separated by half-width ", " (comma plus space)')
 note=re.search(r'\[\d{4}-\d{2}-\d{2}\]\.?\s*([^。；\n]*)',record)
 # 总编辑允许说明文字里用PDF页定位附件、图谱、表格或公报版（如J04、C01、C19、C25、A01）；只报首句即以PDF页作主页码者。
 if note and re.search(r'(?<!\[)PDF第\d+',note.group(1)) and not re.search(r'附件|图谱|表\d|公报',note.group(1)) and not re.search(r': \d+(?:-\d+)?(?:, \d+(?:-\d+)?)*\[\d{4}-',record):
  errs.append(name+': reference ['+number+'] uses "PDF第x—y页" in the note as its main page locator; use "年: 页码[引用日期]."')
 return errs

def lower_reference_errors():
 errs=[]
 for p in sorted(LOWER.rglob('*.md')):
  rel=p.relative_to(LOWER)
  if p.name=='README.md' or '研究记录' in rel.parts: continue
  for number,record in re.findall(r'^(?:- )?\[(\d+)\]\s+(.+)$',p.read_text(),re.M):
   if '/OL]' not in record: continue
   errs.extend(reference_style_errors('下册/'+str(rel),number,record))
   if not re.match(r'(?:[^\[\n]+\. )?\[[^\]\n]+\]\([^)\n]+\)',record):
    errs.append('下册/'+str(rel)+': reference ['+number+'] needs a linked title "[题名](URL)"')
 return errs

def main():
 plan=json.loads((DATA/'编写范围.json').read_text())
 entries=json.loads((ROOT/'索引/案例来源索引.json').read_text())['entries']
 by_path={e['path']:e for e in entries}
 figures=json.loads((MID/'assets/sources.json').read_text())['figures']
 by_asset={r['asset']:r for r in figures}
 figure_rules=json.loads((DATA/'图示裁切规则.json').read_text())
 inline_uses={}
 errors=[]; checks=[]; used_cases=set(); used_figures=set()
 descriptors=[
  '第一节　行业特点、适用企业与业务目标',
  '第二节　行业数字化方案的总体架构',
  '第三节　主要数字化模块、建设内容与业务价值',
  '第四节　在数字化基础上增加智力服务',
  '第五节　适用结论',
  '参考资料',
 ]
 for item in plan['chapters']:
  p=MID/item['file']
  if not p.is_file(): errors.append('Missing planned chapter: '+item['file']); continue
  text=p.read_text()
  for asset in re.findall(r'!\[[^\]\n]*\]\(assets/([^()\n]+\.png)\)',text):
   inline_uses.setdefault(asset,set()).add(p.name)
   # 总编辑定（2026-10-29）：接受 ![图题](assets/…)，不要求外层全尺寸链接。
  edition=item.get('edition',plan['default_chapter_edition'])
  heads=re.findall(r'^##\s+(.+)$',text,re.M)
  if heads!=descriptors:
   errors.append(item['file']+': expected five text sections and standalone references')
  blocks=re.split(r'^##\s+.+$',text,flags=re.M)
  digital=blocks[3] if len(blocks)>3 else ''
  service=blocks[4] if len(blocks)>4 else ''
  references=blocks[6] if len(blocks)>6 else ''
  reference_lines=re.findall(r'^\[(\d+)\]\s+(.+)$',references,re.M)
  if not reference_lines or [int(n) for n,_ in reference_lines]!=list(range(1,len(reference_lines)+1)):
   errors.append(item['file']+': references must be numbered consecutively from [1]')
  for number,record in reference_lines:
   if '．' in record:
    errors.append(item['file']+': reference ['+number+'] uses full-width separator "．"; use half-width ". "')
   if not re.match(r'(?:[^\[\n]+\. )?\[[^\]\n]+\]\([^)\n]+\)(?:: [^\[\]\n]+)?\[(?:EB|R|S|J|M|N|Z|A)/OL\]\. [^\[\]\n]*?(?:\([0-9-]{4,10}[^)\n]*\)|(?:19|20)\d{2})?(?:\(\d+\))?(?:: \d+(?:-\d+)?(?:, \d+(?:-\d+)?)*)?\[\d{4}-\d{2}-\d{2}\]\.(?: |$)',record) or not re.search(r'(?:19|20)\d{2}',record):
    errors.append(item['file']+': reference ['+number+'] lacks institution, linked title or year in the upper-volume format')
   errors.extend(reference_style_errors(item['file'],number,record))
  if not re.search(r'^###\s+',digital,re.M):
   errors.append(item['file']+': missing independently explained digital application modules')
  if '初稿 v' in text or '一芥智能研究院' in text: errors.append(item['file']+': page header or draft edition residue in body text')
  if not re.search(r'https://',text): errors.append(item['file']+': no public original source')
  if len(re.findall(r'[\u4e00-\u9fff]',text))<2200: errors.append(item['file']+': needs substantive editorial review (short)')
  if re.search(r'TODO|FIXME|\{行业\}|\{企业\}',text): errors.append(item['file']+': unreplaced placeholder')
  checks.append({'file':item['file'],'edition':edition,'sections':len(heads),'digital_modules':len(re.findall(r'^###\s+',digital,re.M)),'service_applications':len(re.findall(r'^###\s+',service,re.M)),'reference_entries':len(reference_lines),'digital_han':len(re.findall(r'[\u4e00-\u9fff]',digital)),'service_han':len(re.findall(r'[\u4e00-\u9fff]',service)),'han':len(re.findall(r'[\u4e00-\u9fff]',text))})
 errors.extend(lower_reference_errors())
 for p in MID.glob('*.md'):
  if p.name in ['README.md','附录B-中册图源索引表.md']: continue
  text=p.read_text()
  for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',text):
   if target.startswith('研究记录/'):
    errors.append(p.name+': internal editorial record linked from publication')
   if target.startswith('../下册-案例汇编/') and not target.endswith('README.md'):
    parsed=urlsplit(target)
    key=str((MID/unquote(parsed.path)).relative_to(ROOT)) if not '..' in Path(parsed.path).parts else str((MID/unquote(parsed.path)).resolve().relative_to(ROOT))
    e=by_path.get(key)
    if not e: errors.append(p.name+': case not registered: '+target)
    else: used_cases.add(e['id'])
   if target.startswith('assets/') and target.endswith('.png'):
    asset=Path(target).name
    meta=by_asset.get(asset)
    if not meta: errors.append(p.name+': figure lacks source manifest: '+asset)
    elif not (MID/target).is_file(): errors.append(p.name+': figure missing: '+asset)
    else: used_figures.add(asset)
 for asset in used_figures:
  actual=hashlib.sha256((MID/'assets'/asset).read_bytes()).hexdigest()
  if actual!=by_asset[asset]['asset_sha256']: errors.append('Figure changed after source registration: '+asset)
 planned_files={r['file'] for r in plan['chapters']}
 for group in plan.get('split_groups',[]):
  entry=MID/group['from']
  if group['from'] in planned_files:
   errors.append('Combined entry must not be counted as an industry chapter: '+group['from'])
  if not entry.is_file():
   # The 16 retired guide pages keep their `from` record; only they may be absent.
   if group['from'] in RETIRED_GUIDES: continue
   errors.append('Previous industry URL is missing its reading entry: '+group['from']);continue
  entry_text=entry.read_text()
  if re.search(r'!\[[^\]\n]*\]\(assets/',entry_text):
   errors.append('Combined entry still duplicates industry figures: '+group['from'])
  for target in group['to']:
   if target not in planned_files or ']('+target+')' not in entry_text:
    errors.append('Combined entry lacks its separate industry chapter: '+target)
 for rule in figure_rules['figures']:
  asset=rule['asset'];meta=by_asset.get(asset)
  if not meta:
   errors.append('Reviewed figure missing from source manifest: '+asset);continue
  if inline_uses.get(asset,set())!=set(rule['required_in']):
   errors.append('Figure must be embedded in its planned chapter(s), rather than only linked: '+asset)
  source=figure_rules['sources'][rule['source_id']]
  source_url=source['url']+'#page='+str(rule['pdf_page'])
  if meta['source_sha256']!=source['sha256'] or meta['source_url']!=source_url:
   errors.append('Figure provenance differs from reviewed source: '+asset)
  if meta.get('crop',{}).get('pdf_bbox_points')!=rule['crop_pdf_bbox']:
   errors.append('Figure crop differs from reviewed element bounds: '+asset)
  for chapter in rule['required_in']:
   text=(MID/chapter).read_text()
   if source_url not in text: errors.append(chapter+': figure lacks original PDF page link: '+asset)
 for rule in figure_rules.get('self_drawn',[]):
  asset=rule['asset'];meta=by_asset.get(asset)
  if not meta:
   errors.append('Reviewed self-drawn figure missing from source manifest: '+asset);continue
  if inline_uses.get(asset,set())!=set(rule['required_in']):
   errors.append('Self-drawn figure must be embedded in its planned chapter(s): '+asset)
  if meta.get('generator')!=rule.get('generator') or meta.get('redraws')!=rule.get('redraws'):
   errors.append('Self-drawn figure provenance differs from reviewed inventory: '+asset)
 inventory=[r['asset'] for r in figure_rules['figures']]+[r['asset'] for r in figure_rules.get('self_drawn',[])]
 if len(inventory)!=len(set(inventory)): errors.append('Reviewed figure inventory lists an asset twice')
 if set(by_asset)!=set(inventory):
  errors.append('Figure manifest and reviewed figure inventory differ')
 intake=json.loads((DATA/'新增案例条目.json').read_text())
 for e in intake['entries']:
  for f in e['fragments']:
   for source in f['sources']:
    p=ROOT/source['document']
    if p.exists():
     if hashlib.sha256(p.read_bytes()).hexdigest()!=source['document_sha256']: errors.append(e['id']+': source text hash differs')
     if not 1<=source['line_start']<=source['line_end']<=len(p.read_text().splitlines()): errors.append(e['id']+': source line range invalid')
 report={'passed':not errors,'expected_industry_chapters':len(plan['chapters']),'checked_industry_chapters':len(checks),'referenced_case_entries':len(used_cases),'cited_figure_pages':len(used_figures),'inline_figure_placements':sum(len(chapters) for chapters in inline_uses.values()),'new_cases_with_source_records':len(intake['entries']),'chapters':checks,'errors':errors}
 (MID/'研究记录').mkdir(exist_ok=True)
 (MID/'研究记录/结构与引用核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='chapters'},ensure_ascii=False,indent=2))
 return 0 if not errors else 1

if __name__=='__main__': sys.exit(main())
