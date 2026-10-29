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

APPENDIX_B='附录B-中册图源索引表.md'
NOTE_RE=re.compile(r'^(.*?)（(.+)正文引用此图）$')

def _cells(line):
 return [c.strip() for c in line.strip().strip('|').split('|')]

def dedupe_figure_index(text,order):
 """Collapse repeated figure rows in 附录B: keep the row of the chapter that comes first
 in book order (成书章序.json), note the other chapters in 原篇目, and recount the summary line.
 Deleted rows (图号 —) are left as they are. Idempotent on an already collapsed table."""
 rank={name:i for i,name in enumerate(order)}
 lines=text.split('\n')
 rows=[(i,_cells(l)) for i,l in enumerate(lines) if l.startswith('| ') and not l.startswith('| 图号 |') and not l.startswith('| ---')]
 groups={}
 for i,c in rows:
  if c[0]=='—': continue
  m=NOTE_RE.match(c[6]); home=m[1] if m else c[6]
  others=m[2].split('、') if m else []
  groups.setdefault((c[1],c[2]),[]).append((i,home,others))
 drop=set(); notes={}
 for members in groups.values():
  if len(members)<2 and not members[0][2]: continue
  members.sort(key=lambda m:rank.get(m[1],len(rank)))
  keep=members[0]; cited=list(keep[2])
  for i,home,others in members[1:]:
   drop.add(i); cited+=[home]+others
  cited=sorted(dict.fromkeys(cited),key=lambda n:rank.get(n,len(rank)))
  notes[keep[0]]=f"{keep[1]}（{'、'.join(cited)}正文引用此图）" if cited else keep[1]
 out=[]
 for i,l in enumerate(lines):
  if i in drop: continue
  if i in notes:
   c=_cells(l); c[6]=notes[i]; l='| '+' | '.join(c)+' |'
  out.append(l)
 kept=[_cells(l) for i,l in enumerate(lines) if i not in drop and (i,_cells(l)) in rows]
 count=lambda word:sum(1 for c in kept if c[3].startswith(word))
 summary=re.compile(r'^统计（按引用处）：保留\d+处，重绘\d+处，删除\d+处。')
 out=[summary.sub(f'统计（按引用处）：保留{count("保留")}处，重绘{count("重绘")}处，删除{count("删除")}处。',l) for l in out]
 return '\n'.join(out)

def main():
 plan=json.loads((DATA/'编写范围.json').read_text())
 edition=plan['edition']
 planned=plan['chapters']
 chapters=[MIDDLE/item['file'] for item in planned]
 lines=['# 中册 行业数智化解决方案','',
 '[全书首页](../README.md) · [上册研究报告](../上册-研究报告/README.md) · [下册企业案例](../下册-案例汇编/README.md)','',
 '本册集中展示各行业解决方案：先充分讲解行业数字化总体架构、主要模块、建设内容与业务价值，再说明智力服务的新增作用。行业数字化建设具有独立价值，方案列出的联网、工业模型及智能应用按其功能与条件展开；企业是否已建需核实。','',
 '通用的“摸清现状—确认目标—画蓝图—制定计划”及建设、验收、反馈方法统一见[上册第八章](../上册-研究报告/08-实施建议-从改造机会到可验证行动.md)。企业可按自身类型与所需专业模块选择建设范围，结合上册方法确定复用、补建和服务增补安排。','',
 '各行业章均采用行业特点、总体架构、数字化模块、智力服务和适用结论五节正文，章末独立列参考资料。','',
 '架构图与场景图谱直接嵌入行业正文，点击图片可查看原尺寸；相邻图注保留完整PDF源页及页码。图示仅裁页面外围留白，图内文字、连线、图题和来源保持完整。','',
 '## 引言','']
 for name in INTRO:
  p=MIDDLE/name
  if p.exists(): lines.append(f'- [{title(p)}]({name})')
 scope=(f'本册提供{len(chapters)}篇行业与专业业务方案。' if len(chapters)==len(planned)
        else f'当前可读行业章共{len(chapters)}篇，按大纲与依据成熟度继续编写。')
 lines+=['','## 分行业阅读','',scope+'读者可按企业类型、业务环节和建设目标选择适用章节；各章分别说明行业方案提供的参考能力、企业需要核实的现有条件，以及智力服务可增加的任务与价值。','',
 '住宿与餐饮、农林牧渔等按独立经营对象分篇；同一产业链的整机与配套角色在章内说明。旧合并网址保留为分篇入口，具体调整和当前覆盖范围见[行业分篇说明](../索引/中册行业分篇说明.md)。','']
 cross=[]
 current_group=None
 for p in chapters:
  group=p.name[0]
  if group != current_group:
   lines+=['',f"### {group}-{plan['industry_groups'][group]}",'', '| 行业方案 | 阅读重点 |','| --- | --- |']
   current_group=group
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
 appendix=MIDDLE/APPENDIX_B
 book=json.loads((DATA/'成书章序.json').read_text())['chapters']
 book_order=[f.removesuffix('.md') for k in sorted(book,key=int) for f in book[k]]
 appendix.write_text(dedupe_figure_index(appendix.read_text(),book_order))
 lines+=['','## 选用对照与引用依据','']
 for p in sorted(MIDDLE.glob('附录*.md')): lines.append(f'- [{title(p)}]({p.name})')
 lines+=['- [原图摘引与来源记录](assets/README.md)','- [行业指南、报告与白皮书](../索引/工信部行业数字化转型资料汇总.md)','- [行业解决方案章节模板](../templates/行业解决方案章节模板.md)','- [整体编写大纲](../草稿箱/中册-行业数智化解决方案-编写大纲构思-20261017.md)','',
 '原图内容归属原发布者与编制者，服务应用为方案建议，企业成效按各篇来源与阶段理解。','']
 (MIDDLE/'README.md').write_text('\n'.join(lines))
 (MIDDLE/'研究记录').mkdir(exist_ok=True)
 (MIDDLE/'研究记录/章节引用清单.json').write_text(json.dumps({'updated_on':'2026-10-18','chapters':cross},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'industry_chapters':len(chapters),'case_links':sum(len(r['case_links']) for r in cross),'figure_links':sum(len(r['figures']) for r in cross)},ensure_ascii=False))

if __name__=='__main__': main()
