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

def main():
 plan=json.loads((DATA/'编写范围.json').read_text())
 entries=json.loads((ROOT/'索引/案例来源索引.json').read_text())['entries']
 by_path={e['path']:e for e in entries}
 figures=json.loads((MID/'assets/sources.json').read_text())['figures']
 by_asset={r['asset']:r for r in figures}
 errors=[]; checks=[]; used_cases=set(); used_figures=set()
 structures={
  'v0.1':[('行业特点、适用企业与业务目标',),('行业数字化方案架构与应用模块',),('企业现状、差距与本轮增强思路',),('围绕应用模块展开具体方案','围绕业务任务展开具体方案'),('跨模块及产业链协同',),('建设实施与运行责任',),('投入、验收与扩展条件',),('适用结论、企业参照与资料来源',)],
  'v0.2':[('行业特点、适用企业与业务目标',),('行业数字化方案的总体架构',),('主要数字化模块、建设内容与业务价值',),('在数字化基础上增加智力服务',),('企业现状、目标与建设蓝图',),('建设计划、交付与运行责任',),('投入、验收与扩展条件',),('适用结论、企业参照与资料来源',)],
  'v0.3':[('行业特点、适用企业与业务目标',),('行业数字化方案的总体架构',),('主要数字化模块、建设内容与业务价值',),('在数字化基础上增加智力服务',),('适用结论',),('参考资料',)],
 }
 for item in plan['chapters']:
  p=MID/item['file']
  if not p.is_file(): errors.append('Missing planned chapter: '+item['file']); continue
  text=p.read_text()
  edition=item.get('edition',plan['default_chapter_edition'])
  descriptors=structures.get(edition)
  if descriptors is None:
   errors.append(item['file']+': unknown chapter edition '+edition)
   continue
  heads=re.findall(r'^##\s+(.+)$',text,re.M)
  if len(heads)!=len(descriptors) or any(not any(label in actual for label in expected) for expected,actual in zip(descriptors,heads)):
   errors.append(item['file']+': section structure differs')
  if '初稿 '+edition not in text: errors.append(item['file']+': edition metadata differs from scope record')
  if not re.search(r'https://',text): errors.append(item['file']+': no public original source')
  if len(re.findall(r'[\u4e00-\u9fff]',text))<2200: errors.append(item['file']+': needs substantive editorial review (short)')
  if re.search(r'TODO|FIXME|\{行业\}|\{企业\}',text): errors.append(item['file']+': unreplaced placeholder')
  checks.append({'file':item['file'],'edition':edition,'sections':len(heads),'han':len(re.findall(r'[\u4e00-\u9fff]',text))})
 for p in MID.glob('*.md'):
  if p.name in ['README.md','附录B-原架构原图与案例对照.md']: continue
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
 intake=json.loads((DATA/'新增案例条目.json').read_text())
 for e in intake['entries']:
  for f in e['fragments']:
   for source in f['sources']:
    p=ROOT/source['document']
    if p.exists():
     if hashlib.sha256(p.read_bytes()).hexdigest()!=source['document_sha256']: errors.append(e['id']+': source text hash differs')
     if not 1<=source['line_start']<=source['line_end']<=len(p.read_text().splitlines()): errors.append(e['id']+': source line range invalid')
 report={'passed':not errors,'expected_industry_chapters':len(plan['chapters']),'checked_industry_chapters':len(checks),'referenced_case_entries':len(used_cases),'cited_figure_pages':len(used_figures),'new_cases_with_source_records':len(intake['entries']),'chapters':checks,'errors':errors}
 (MID/'研究记录').mkdir(exist_ok=True)
 (MID/'研究记录/结构与引用核验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='chapters'},ensure_ascii=False,indent=2))
 return 0 if not errors else 1

if __name__=='__main__': sys.exit(main())
