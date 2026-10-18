#!/usr/bin/env python3
"""Rebuild the middle-volume reading index and source/case cross-reference."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
MIDDLE=ROOT/'中册-行业解决方案'
DATA=ROOT/'scripts/data/middle'
INTRO=['00-导读.md']

def title(p):
 return re.search(r'^#\s+(.+)$',p.read_text(),re.M)[1]

def case_links(text):
 # Keep scene links used in the prose; omit a duplicate unanchored bibliography link.
 links=set(re.findall(r'\]\((\.\./下册-案例汇编/[^)]+)\)',text))
 links={link for link in links if not link.split('#',1)[0].endswith('/README.md')}
 anchored={link.split('#',1)[0] for link in links if '#' in link}
 return sorted(link for link in links if '#' in link or link not in anchored)

def main():
 plan=json.loads((DATA/'编写范围.json').read_text())
 edition=plan['edition']
 planned=plan['chapters']
 chapters=sorted(p for p in MIDDLE.glob('*.md') if re.match(r'[A-Z]\d\d-',p.name))
 lines=['# 中册 行业数智化解决方案','',f'一芥智能研究院｜《企业数智化转型研究报告》中册｜初稿 {edition}｜2026年10月18日','',
 '[全书首页](../README.md) · [上册研究报告](../上册-研究报告/README.md) · [下册企业案例](../下册-案例汇编/README.md)','',
 '本册集中展示各行业解决方案：先充分讲解行业数字化总体架构、主要模块、建设内容与业务价值，再说明智力服务的新增作用。行业数字化建设具有独立价值，方案列出的联网、工业模型及智能应用按其功能与条件展开；企业是否已建需核实。','',
 '通用的“摸清现状—确认目标—画蓝图—制定计划”及建设、验收、反馈方法统一见[上册第八章](../上册-研究报告/08-实施建议-从改造机会到可验证行动.md)。企业可按自身类型与所需专业模块选择建设范围，结合上册方法确定复用、补建和服务增补安排。','',
 '各行业章均采用行业特点、总体架构、数字化模块、智力服务和适用结论五节正文，章末独立列参考资料。','',
 '## 引言','']
 for name in INTRO:
  p=MIDDLE/name
  if p.exists(): lines.append(f'- [{title(p)}]({name})')
 scope=(f'本册覆盖{len(chapters)}个行业主题。' if len(chapters)==len(planned)
        else f'当前可读行业章共{len(chapters)}篇，按大纲与依据成熟度继续编写。')
 lines+=['','## 分行业阅读','',scope+'读者可按企业类型、业务环节和建设目标选择适用章节；各章分别说明行业方案提供的参考能力、企业需要核实的现有条件，以及智力服务可增加的任务与价值。','', '| 行业方案 | 阅读重点 |','| --- | --- |']
 cross=[]
 for p in chapters:
  text=p.read_text()
  focus_text=re.split(r'^##\s+',text,flags=re.M)[3]
  h=re.findall(r'^###\s+(.+)$',focus_text,re.M)
  focus='、'.join(re.sub(r'^\d+[.．、]\s*','',label) for label in h[:3]) if h else '行业架构、数字化应用模块与智力服务'
  lines.append(f'| [{title(p)}]({p.name}) | {focus} |')
  refs=case_links(text)
  figures=sorted(set(re.findall(r'!\[[^\]]*\]\((assets/[^)]+)\)',text)))
  cross.append({'chapter':p.name,'title':title(p),'case_links':refs,'figures':figures})
 for name in INTRO:
  p=MIDDLE/name
  if p.exists():
   refs=case_links(p.read_text())
   cross.append({'chapter':p.name,'title':title(p),'case_links':refs,'figures':[]})
 entries=json.loads((ROOT/'索引/案例来源索引.json').read_text())['entries']
 by_path={e['path']:e for e in entries}
 table=['# 附录B 行业架构、来源图示与企业案例对照','',f'一芥智能研究院｜《企业数智化转型研究报告》中册｜初稿 {edition}｜2026年10月18日','',
        '[中册目录](README.md) · [行业资料库](../索引/工信部行业数字化转型资料汇总.md) · [原图来源](assets/README.md)','',
        '原图给出行业参考架构和模块，企业案例说明实际建设范围，智力服务新增作用按各章的模块说明与服务应用理解。表中只列当前正文已经使用的引用。','',
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
  table.append(f"| [{row['title']}]({row['chapter']}) | {'；'.join(case_labels) or '按本章引用的行业方案展开'} | {'；'.join(figures) or '原文入口见章内来源'} |")
 table+=['',f'当前正文共引用下册{len(unique_cases)}个案例入口。行业方案提供的参考能力、企业已建能力与新增服务各有证据范围；图谱评级及所引案例成效不作为新增服务的实测结果。','']
 (MIDDLE/'附录B-原架构原图与案例对照.md').write_text('\n'.join(table))
 lines+=['','## 选用对照与引用依据','']
 for p in sorted(MIDDLE.glob('附录*.md')): lines.append(f'- [{title(p)}]({p.name})')
 lines+=['- [原图摘引与来源记录](assets/README.md)','- [行业指南、报告与白皮书](../索引/工信部行业数字化转型资料汇总.md)','- [行业解决方案章节模板](../templates/行业解决方案章节模板.md)','- [整体编写大纲](../草稿箱/中册-行业数智化解决方案-编写大纲构思-20261017.md)','',
 '本册为持续编写的初稿。原图内容归属原发布者与编制者，服务应用为方案建议，企业成效按各篇来源与阶段理解。','']
 (MIDDLE/'README.md').write_text('\n'.join(lines))
 (MIDDLE/'研究记录').mkdir(exist_ok=True)
 (MIDDLE/'研究记录/章节引用清单.json').write_text(json.dumps({'updated_on':'2026-10-18','chapters':cross},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'industry_chapters':len(chapters),'case_links':sum(len(r['case_links']) for r in cross),'figure_links':sum(len(r['figures']) for r in cross)},ensure_ascii=False))

if __name__=='__main__': main()
