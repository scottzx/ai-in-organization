#!/usr/bin/env python3
"""Merge reviewed middle-volume case intake and rebuild lower-volume indexes."""
from collections import Counter
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
INDEX=ROOT/'索引/案例来源索引.json'
INTAKE=ROOT/'scripts/data/middle/新增案例条目.json'

def main():
 data=json.loads(INDEX.read_text())
 incoming=json.loads(INTAKE.read_text())['entries']
 by_id={e['id']:e for e in data['entries']}
 added=[]
 for e in incoming:
  if not (ROOT/e['path']).is_file(): raise FileNotFoundError(e['path'])
  if e['id'] in by_id:
   if by_id[e['id']] != e: raise ValueError('Existing entry differs: '+e['id'])
   continue
  by_id[e['id']]=e; added.append(e['id'])
 entries=sorted(by_id.values(),key=lambda e:(2 if e['id'].startswith('附') else 1 if e['id'].startswith('待') else 0,e['id']))
 data['entries']=entries
 data['version']='v9.0'; data['updated_on']='2026-10-18'
 fragments=[f for e in entries for f in e['fragments']]
 data['counts']={
  'entries':len(entries),
  'industry_and_pending_entries':sum(e['entry_type'] not in ('reference','method') for e in entries),
  'methods':sum(e['entry_type']=='method' for e in entries),
  'references':sum(e['entry_type']=='reference' for e in entries),
  'source_records_main_fragment':len({e['source_record_id'] for e in entries if e['entry_type']!='reference'}),
  'practice_fragments':sum(len(e['fragments']) for e in entries if e['entry_type']!='reference'),
  'reference_fragments':sum(len(e['fragments']) for e in entries if e['entry_type']=='reference'),
  'all_fragments':len(fragments)}
 INDEX.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 c=data['counts']
 classified=[e for e in entries if e['classification_status'] in ('supported','provisional')]
 pending=[e for e in entries if e['classification_status']=='pending']
 industry_count=len({e['industry_code'] for e in classified})
 home=ROOT/'README.md'
 home_text=home.read_text()
 case_label='行业与待定案例入口' if pending else '行业案例入口'
 summary=f"下册现有{c['entries']}个阅读入口：{c['industry_and_pending_entries']}个{case_label}、{c['methods']}项跨行业方法、{c['references']}项原型或演示参考，共{c['all_fragments']}个场景与证据片段。"
 home_text=re.sub(r'下册现有\d+个阅读入口：\d+个行业(?:与待定)?案例入口、\d+项跨行业方法、\d+项原型或演示参考，共\d+个场景与证据片段。',summary,home_text)
 home.write_text(home_text)
 lines=['# 下册 企业数字化与数智化案例汇编','',
 '[全书首页](../README.md) · [上册研究报告](../上册-研究报告/README.md) · [中册行业解决方案](../中册-行业解决方案/README.md)','',
 '本册按行业、公司或项目集中呈现已审读的建设与应用。数字化、网络化、智能化的案例均可收录，基础系统、设备、数据与协作建设具有独立价值；未披露AI的材料按实际范围表达。上册和中册按论证及模块需要引用具体场景，企业过程在本册独立维护。','',
 '每篇采用统一七节结构：企业介绍、业务背景与改造目标、面临的问题、解决方案与实施过程、实施效果、分析与启示、资料来源。原建设、服务增补、实绩与预计分别表达；案例事实与编者方案分清。写法见[企业案例模板](../templates/企业案例模板.md)。','',
 f"现有{c['entries']}个阅读入口：{c['industry_and_pending_entries']}个{case_label}、{c['methods']}项跨行业方法、{c['references']}项原型或演示参考，共{c['all_fragments']}个场景与证据片段。入口数不等于独立公司数或成功交付数。新增官方项目材料属于汇编中的项目建设及成效披露，不视为独立投资回报审计。",'',
 f'行业按GB/T 4754—2017门类组织，现有{len(classified)}个案例归入{industry_count}个门类'+(f'，另有{len(pending)}个主体因主营活动证据不足保留待核。' if pending else '。')+'每个案例只设一个主行业，AI任务、客户行业及供应链环节作为场景信息；同主体的新场景优先补入原篇。分类迁移保留旧编号与旧路径，来源片段和锚点保持稳定。复核依据及编号对照见[资料来源说明](../索引/资料来源说明.md#案例行业分类复核与编号迁移)。','',
 '## 从数字化基础读起','',
 '- [消防维保企业的工具与采购取舍](M-科学研究与技术服务业/M02-消防维保企业数字化项目取舍.md)：既有工具与小模块已经使用，AI辅助描述仍为方向。',
 '- [3C外贸企业的业务系统](F-批发与零售业/F09-3C外贸企业AI自建业务系统.md)：AI参与开发，日常单据由已建系统、资料和规则支持。',
 '- [北海电厂的三维会检与共享](D-电力热力燃气及水生产和供应业/D01-国能广投北海电厂5G工程与运行管理.md)：该场景已有数字模型用途，进一步融合AI另按未来方向表达。','',
 '这些片段帮助观察数据、工具和协作怎样先形成可用基础；AI是否参与建设、是否参与运行及未来计划分别判断。','',
 '## 按行业阅读','']
 groups={}
 for e in entries: groups.setdefault(Path(e['path']).parent,[]).append(e)
 for folder,es in groups.items():
  short=folder.name
  lines += [f'### [{short}]({short}/README.md)','', '| 编号 | 公司或项目 | 场景数 |','| --- | --- | --- |']
  ilines=[f'# {short}','','[下册总索引](../README.md) · [中册行业方案](../../中册-行业解决方案/README.md) · [全书首页](../../README.md)','',
   '以下各篇按稳定编号排列。数字化基础、已使用、试点、原型和设想分别保留，效果按来源的对象、阶段与口径理解。','', '| 编号 | 公司或项目 | 本篇覆盖 |','| --- | --- | --- |']
  for e in es:
   file=Path(e['path']).name
   lines.append(f"| {e['id']} | [{e['title']}]({short}/{file}) | {len(e['fragments'])} |")
   stages='、'.join(dict.fromkeys(f['stage_label'] for f in e['fragments']))
   ilines.append(f"| {e['id']} | [{e['title']}]({file}) | {len(e['fragments'])}项；{stages} |")
  (ROOT/folder/'README.md').write_text('\n'.join(ilines)+'\n')
  if es[0]['classification_status']=='pending':
   reasons=['','## 已复核的行业边界','',
    '以下案例只在本区列一次。内部采购、仓储、研发或包装任务不足以替代主体的主营活动；有可靠依据后再迁入唯一行业，保留编号对照。','']
   for e in es:
    reasons.append(f"- **{e['id']} {e['title']}：**{e.get('classification_review',{}).get('basis','主营活动证据不足，保留待核。')}")
   reasons+=['','[分类复核与编号迁移](../../索引/资料来源说明.md#案例行业分类复核与编号迁移)','']
   with (ROOT/folder/'README.md').open('a') as handle: handle.write('\n'.join(reasons))
  lines.append('')
 lines += ['## 原始出处与研究材料','', '[案例来源、阶段及定位](../索引/案例来源索引.json) · [行业原文与企业资料](../索引/工信部行业数字化转型资料汇总.md)','']
 (ROOT/'下册-案例汇编/README.md').write_text('\n'.join(lines))
 print(json.dumps({'added':added,**c},ensure_ascii=False))

if __name__=='__main__': main()
