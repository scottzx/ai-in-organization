#!/usr/bin/env python3
"""Publish supplementary source references without internal authoring notes."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
MID=ROOT/'中册-行业解决方案'
DATA=ROOT/'scripts/data/middle'

def main():
 original={r['url'] for r in json.loads((ROOT/'索引/工信部行业数字化转型资料索引.json').read_text())['records']}
 records=[]
 for p in sorted(DATA.glob('补充来源-*.json')):
  value=json.loads(p.read_text())
  if isinstance(value,list): records.extend(value)
  else: records.extend(value.get('records',value.get('sources',[])))
 intake=json.loads((DATA/'新增案例条目.json').read_text())
 records.extend(intake.get('supplementary_sources',[]))
 by_url={}
 for record in records:
  url=record.get('url') or record.get('source_url')
  if not url or url in original: continue
  if url not in by_url: by_url[url]=dict(record,url=url)
  else:
   earlier=by_url[url]
   earlier['used_in']=sorted(set(earlier.get('used_in',[])+record.get('used_in',[])))
 lines=['# 中册补充行业资料','',
 '本表列出中册在既有57条行业资料之外核读的补充来源。文件性质、适用范围和对应章节分别注明；政策任务、研究框架和企业实际建设按各自证据使用。既有书目见[工信部及相关机构资料库](工信部行业数字化转型资料汇总.md)，正式正文见[中册目录](../中册-行业解决方案/README.md)。','',
 '| 资料 | 发布者与性质 | 版本或日期 | 使用位置与范围 |','| --- | --- | --- | --- |']
 for r in by_url.values():
  loc=[]
  for part in r.get('locators',[]):
   if isinstance(part,str): loc.append(part)
   else:
    label=('PDF第'+str(part['pdf_pages'])+'页：') if part.get('pdf_pages') else ''
    loc.append(label+(part.get('section') or part.get('figure') or part.get('content','')))
  if not loc and r.get('locator'): loc=[str(r['locator'])]
  used=r.get('used_in',[])
  if isinstance(used,str): used=[used]
  where=[]
  for name in used:
   file=Path(name).name
   where.append(f'[{file.removesuffix(".md")}]（../中册-行业解决方案/{file}）'.replace(']（','](').replace('）',')') if (MID/file).exists() else name)
  scope=r.get('scope','')
  if isinstance(scope,list): scope='；'.join(scope)
  description='；'.join(where+loc+([scope] if scope else []))
  publisher=r.get('publisher',r.get('issuer','原发布者见文件'))
  kind=r.get('source_type',r.get('type',''))
  date=next((r[k] for k in ('issued_date','publication_date','published_date','date','published','published_month') if r.get(k)),'见原文版本')
  title=r.get('title',r['url'])
  attribution=publisher+('；'+kind if kind else '')
  lines.append(f"| [{title}]({r['url']}) | {attribution} | {date} | {description} |")
 lines+=['','行业方案中的软件接入、任务分工和验收安排，除来源明确披露的内容外，按各章的编者设计表达。上述资料不计作下册企业案例；具体企业过程仍按[案例来源索引](案例来源索引.json)登记。','']
 (ROOT/'索引/中册补充行业资料.md').write_text('\n'.join(lines))
 for p in MID.glob('*.md'):
  before=p.read_text()
  import re
  text=re.sub(r'\]\(研究记录/补充来源-[^)]+\.json\)','](../索引/中册补充行业资料.md)',before)
  if text!=before: p.write_text(text)
 print(json.dumps({'supplementary_sources':len(by_url)},ensure_ascii=False))

if __name__=='__main__': main()
