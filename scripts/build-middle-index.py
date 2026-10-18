#!/usr/bin/env python3
"""Rebuild the middle-volume reading index and source/case cross-reference."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
MIDDLE=ROOT/'中册-行业解决方案'
DATA=ROOT/'scripts/data/middle'
COMMON=['00-导读.md','01-既有行业方案与智力服务.md','02-建设实施与验收.md']

def title(p):
 return re.search(r'^#\s+(.+)$',p.read_text(),re.M)[1]

def main():
 chapters=sorted(p for p in MIDDLE.glob('*.md') if re.match(r'[A-Z]\d\d-',p.name))
 lines=['# 中册 行业数智化解决方案','','一芥智能研究院｜《企业数智化转型研究报告》中册｜初稿 v0.1｜2026年10月18日','',
 '[全书首页](../README.md) · [上册研究报告](../上册-研究报告/README.md) · [下册企业案例](../下册-案例汇编/README.md)','',
 '本册沿已有行业指南、方案架构与应用模块展开，在其基础上增加智力服务的建设、协调和运行安排。数字化基础继续建设，网络化与智能化按业务需要同步设计和验证；智力服务的价格与供给方式为降低部分开发和试验投入提供新的机会。','',
 '原架构、企业实际建设和编者增补分别表达。各行业章写清建什么、怎么建、怎样验收，引用的企业过程在下册独立维护；数字化、自动化和未披露AI的建设案例同样可以提供基础参照。','',
 '## 导读与共用方法','']
 for name in COMMON:
  p=MIDDLE/name
  if p.exists(): lines.append(f'- [{title(p)}]({name})')
 planned=json.loads((DATA/'编写范围.json').read_text())['chapters']
 scope=(f'本轮已覆盖大纲所列{len(chapters)}个行业主题。' if len(chapters)==len(planned)
        else f'当前可读行业章共{len(chapters)}篇，按大纲与依据成熟度继续编写。')
 lines+=['','## 分行业阅读','',scope+'各章注明资料适用范围，沿原模块及企业类型展开；只有政策方向或案例流程的领域，分别标明依据性质和编者设计。','', '| 行业方案 | 阅读重点 |','| --- | --- |']
 cross=[]
 for p in chapters:
  text=p.read_text()
  h=re.findall(r'^###\s+(.+)$',text,re.M)
  focus='、'.join(h[:3]) if h else '原架构、模块增强、建设实施与验收'
  if len(focus)>65: focus=focus[:65]+'等'
  lines.append(f'| [{title(p)}]({p.name}) | {focus} |')
  refs=sorted(link for link in set(re.findall(r'\]\((\.\./下册-案例汇编/[^)]+)\)',text)) if not link.split('#',1)[0].endswith('/README.md'))
  figures=sorted(set(re.findall(r'!\[[^\]]*\]\((assets/[^)]+)\)',text)))
  cross.append({'chapter':p.name,'title':title(p),'case_links':refs,'figures':figures})
 for name in COMMON:
  p=MIDDLE/name
  if p.exists():
   refs=sorted(link for link in set(re.findall(r'\]\((\.\./下册-案例汇编/[^)]+)\)',p.read_text())) if not link.split('#',1)[0].endswith('/README.md'))
   cross.append({'chapter':p.name,'title':title(p),'case_links':refs,'figures':[]})
 entries=json.loads((ROOT/'索引/案例来源索引.json').read_text())['entries']
 by_path={e['path']:e for e in entries}
 table=['# 附录B 原架构、原图与企业案例对照','','一芥智能研究院｜《企业数智化转型研究报告》中册｜初稿 v0.1｜2026年10月18日','',
        '[中册目录](README.md) · [行业资料库](../索引/工信部行业数字化转型资料汇总.md) · [原图来源](assets/README.md)','',
        '原图给出行业参考架构和模块，企业案例说明实际建设范围，智力服务增补按各章的方案设计与验收安排理解。表中只列当前正文已经使用的引用。','',
        '| 章节 | 下册企业参照 | 原图摘引 |','| --- | --- | --- |']
 unique_cases=set()
 for row in sorted(cross,key=lambda row:row['chapter']):
  case_labels=[]
  for link in row['case_links']:
   path=link.split('#',1)[0].removeprefix('../')
   entry=by_path.get(path)
   if entry:
    unique_cases.add(entry['id'])
    label=f"{entry['id']} {entry['title']}"
   else: label=Path(path).stem
   case_labels.append(f'[{label}]({link})')
  figures=[f'[{Path(link).stem}]({link})' for link in row['figures']]
  table.append(f"| [{row['title']}]({row['chapter']}) | {'；'.join(case_labels) or '按本章原方案依据展开'} | {'；'.join(figures) or '原文入口见章内来源'} |")
 table+=['',f'当前正文共引用下册{len(unique_cases)}个案例入口。数字化基础、原有智能应用及新增服务各有证据范围，原图评级或原案例成效不作为新增服务的实测结果。','']
 (MIDDLE/'附录B-原架构原图与案例对照.md').write_text('\n'.join(table))
 lines+=['','## 工作表与引用依据','']
 for p in sorted(MIDDLE.glob('附录*.md')): lines.append(f'- [{title(p)}]({p.name})')
 lines+=['- [原图摘引与来源记录](assets/README.md)','- [行业指南、报告与白皮书](../索引/工信部行业数字化转型资料汇总.md)','- [整体大纲与行业章节模板](../草稿箱/中册-行业数智化解决方案-编写大纲构思-20261017.md)','',
 '本册为持续编写的初稿。原图内容归属原发布者与编制者，正文新增方案按编者设计表达，企业成效按各篇来源与阶段理解。','']
 (MIDDLE/'README.md').write_text('\n'.join(lines))
 (MIDDLE/'研究记录').mkdir(exist_ok=True)
 (MIDDLE/'研究记录/章节引用清单.json').write_text(json.dumps({'updated_on':'2026-10-18','chapters':cross},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'industry_chapters':len(chapters),'case_links':sum(len(r['case_links']) for r in cross),'figure_links':sum(len(r['figures']) for r in cross)},ensure_ascii=False))

if __name__=='__main__': main()
