#!/usr/bin/env python3
"""Build the reviewed research catalogue from source metadata and download audit."""
import csv
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '索引'
BASE = ROOT / '资料库/工信部数字化转型原文'
SOURCE = DEST / '工信部行业数字化转型资料索引.json'
data = json.loads(SOURCE.read_text())
records = data['records']
audit_path = BASE / 'download-audit.json'
audit_list = json.loads(audit_path.read_text())
audit = {r['fetch_id']: r for r in audit_list}
assert len(records) == 57
assert len({r['id'] for r in records}) == len(records)
for r in records:
    original = audit[r['fetch_id']]
    assert original['status'] in ('downloaded', 'html'), (r['id'], original['status'])
    r['source_level'] = ('工信部或联合部门正式资料' if r['id'][0] in 'AD' else
                         '工信部组织发布的行业融合指南' if r['id'][0] == 'B' else
                         '行业联盟发布、信通院官网收录' if r['id'] in ('C11', 'C27') else
                         '中国信通院及其研究所发布或联合发布')
    r['url'] = original['url']
    r['source_page'] = r['source_page'] or r['url']
    r['verification_scope'] = '来源、文件格式、页数、标题／封面已核；全文未逐页精读'
    if original['status'] == 'downloaded':
        old_path = ROOT / original['local_pdf']
        filename = r['id'] + '-' + re.sub(r'[/\\:*?"<>|]', '-', r['title']) + '.pdf'
        new_path = BASE / 'pdf' / filename
        if old_path != new_path:
            assert not new_path.exists(), new_path
            old_path.rename(new_path)
            original['local_pdf'] = str(new_path.relative_to(ROOT))
        assert hashlib.sha256(new_path.read_bytes()).hexdigest() == original['sha256']
        r.update(format='PDF', pages=original['pages'], bytes=original['bytes'],
                 sha256=original['sha256'], local_pdf=original['local_pdf'],
                 local_text=original['local_text'])
    else:
        r.update(format='HTML', pages=None, local_html=original['local_html'],
                 local_text=original['local_text'])
    if r['id'] == 'A05':
        r['companion_html'] = audit['F078']['local_html']
        r['verification_scope'] += '；PDF仅为41项典型场景附件，主文单独为HTML'
pdf_records = [r for r in records if r['format'] == 'PDF']
factories = json.loads((DEST / '工信部5G工厂企业索引.json').read_text())
cases = json.loads((DEST / '工信部典型案例检索索引.json').read_text())
stats = dict(source_count=len(records), pdf_source_count=len(pdf_records),
             unique_catalogue_pdf_files=len({r['sha256'] for r in pdf_records}),
             total_catalogue_pdf_pages=sum(r['pages'] for r in pdf_records),
             html_source_count=len(records)-len(pdf_records), factory_projects=factories['record_count'],
             unique_factory_company_names=factories['unique_company_names'],
             factory_industry_count=factories['industry_count'],
             full_case_entries=cases['full_case_count'], list_case_entries=cases['list_count'])
data.update(stats=stats, verification_note='只核验书目、文件、目录与索引定位；研究阅读深度与案例效果须另行登记。')
SOURCE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
audit_path.write_text(json.dumps(audit_list, ensure_ascii=False, indent=2) + '\n')
fields = ['id','title','published','publisher','source_level','industries','format','pages',
          'source_page','url','local_pdf','local_html','sha256','note']
with (DEST / '工信部行业数字化转型资料索引.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    writer.writeheader()
    writer.writerows(records)

lines = ['# 工信部及相关机构行业数字化转型资料汇总', '',
         '[全书首页](../README.md) · [资料来源说明](资料来源说明.md) · [书目CSV](工信部行业数字化转型资料索引.csv) · [书目JSON](工信部行业数字化转型资料索引.json)', '',
         '检索与核验日期：2026-10-17。优先采用工信部正式发文、工信部组织发布的行业指南，以及中国信息通信研究院发布或联合发布的研究报告；联盟白皮书单独标明发布机构。', '',
         f'本轮汇总 **{len(records)}条资料**：16条指南、方案与评测工具，6条行业融合应用指南，27条研究报告与白皮书，8条企业名录与案例资料。其中 **{len(pdf_records)}份PDF已下载**，共{stats["total_catalogue_pdf_pages"]}页；2条以官方HTML保存。医药实施方案的主文为HTML，所附PDF为41项典型场景。', '',
         f'另建两套可检索索引：**[960条5G工厂项目、958个建设主体名称、50个行业](工信部5G工厂企业索引.md)**；**[100个案例全文入口与235项官方案例名单](工信部典型案例检索索引.md)**。项目、企业名称和案例入口采用不同计数口径；同集团不同子公司、分公司不人为合并，两套案例来源也可能重复。', '',
         '来源、PDF文件头、页数、标题或封面已核，已核对行业附件、场景图谱、企业表格、案例目录与起始页。这里的收录不代表已经精读全部全文，名录入选也不等于投资回报或AI效果得到独立验证。研究素材暂不计入下册现有62个入口、101个片段。', '',
         '## 本地原文与使用方式', '',
         '本地PDF位于 `资料库/工信部数字化转型原文/pdf/`，文件已按资料编号和标题命名；同目录上一级的 `阅读索引.html` 可打开全部本地副本。提取文本、HTML正文、下载记录与SHA256保存在该本地资料目录。公开书稿只保留来源链接和研究索引，原文目录已加入.gitignore。', '',
         '查找行业时先读下方对应指南，再进入企业名录找建设主体；需要改造过程时，进入100项案例全文。拟纳入正文的个案仍需逐篇登记业务问题、动作、前后衔接、投入、结果口径与原文页码。', '',
         '## 资料来源分级', '',
         '| 编号 | 来源范围 | 使用边界 |', '| --- | --- | --- |',
         '| A | 工信部或联合部门发布的指南、方案和工具 | 可作政策与实施框架依据；注意版本和附件范围。 |',
         '| B | 工信部组织发布的分行业工业互联网融合指南 | 可查场景、实施路径、供应商和案例；编制单位以原文为准。 |',
         '| C | 中国信通院等发布或联合发布的研究资料 | 属研究报告；C11、C27是联盟发布、官网收录，均不冒称部委正式发文。 |',
         '| D | 工信部正式名录和案例资料 | 企业与项目研究线索；区分入选名单与案例全文。 |', '']
groups = [('A','指南、实施方案与评测工具'), ('B','分行业工业互联网融合应用指南'),
          ('C','中国信通院及相关机构研究报告与白皮书'), ('D','企业名录与典型案例资料')]
for prefix, title in groups:
    lines += ['## ' + title, '', '| 编号 | 资料与来源 | 发布／封面日期 | 适用行业 | 文件 | 可查内容 |', '| --- | --- | --- | --- | --- | --- |']
    for r in records:
        if r['id'][0] != prefix:
            continue
        file_cell = f'[PDF，{r["pages"]}页]({r["url"]})' if r['format']=='PDF' else '[官方HTML](' + r['url'] + ')'
        institution_note = '（联盟发布，官网收录）' if r['id'] in ('C11','C27') else ''
        lines.append(f'| {r["id"]} | [{r["title"]}]({r["source_page"]}){institution_note} | {r["published"]} | {r["industries"]} | {file_cell} | {r["note"]} |')
    lines += ['']

lines += ['## 同一PDF内的行业指南与场景图谱', '',
          '下表按PDF文件页码定位；这些附件和图谱不另算独立PDF。', '',
          '| 来源 | 行业附件 | PDF页码 |', '| --- | --- | --- |']
by_id={r['id']:r for r in records}
for title,start,end in [('石化化工行业数字化转型实施指南',13,22),('钢铁行业数字化转型实施指南',23,32),
                        ('有色金属行业数字化转型实施指南',33,44),('建材行业数字化转型实施指南',45,53)]:
    lines.append(f'| A03 | {title} | [第{start}—{end}页]({by_id["A03"]["url"]}#page={start}) |')
graphs=[('钢铁',12,14),('石化',15,20),('工程机械',21,23),('新能源汽车',24,27),('机器人',28,30),
        ('医疗装备',31,35),('家电',36,39),('制糖',40,41),('白酒',42,44),('美妆日化',45,47),
        ('锂电池',48,51),('印制板（PCB）',52,54),('智能移动终端',55,57),('民爆',58,62)]
for industry,start,end in graphs:
    lines.append(f'| A11 | {industry}行业数字化转型场景图谱（2025版） | [第{start}—{end}页]({by_id["A11"]["url"]}#page={start}) |')

coverage=[
('农业、畜牧、农村经营','C09、C10','D01、D02；名录中的畜牧企业'),
('煤矿、金属矿、非金属矿','A16、A13','D08；D01、D02采矿项目'),
('石化化工、油气储运','A03、B04、B06','D04；D01、D02化工、燃气项目'),
('钢铁、有色金属','A03、B01','D04；D01、D02冶炼与压延项目'),
('水泥、玻璃、陶瓷、建材、新材料','A03、A16','D04；D01、D02非金属矿物制品项目'),
('通用设备、专用设备、工程机械、机器人','A09、B02、A11','D05；D01、D02机械制造项目'),
('汽车、零部件、新能源汽车','A10、A11','D05；D01、D02汽车项目'),
('船舶、航空装备、轨道交通','B05、A16','D05；D03及D01、D02运输设备项目'),
('纺织、化纤、服装、家纺、印染','A07','D06；D01、D02纺织与服装项目'),
('家电、家具、造纸、皮革、日化、五金等轻工','A04、A11','D06；D01、D02轻工项目'),
('食品、乳品、饮料、制糖、酿酒','A06、A11','D06；D01、D02食品饮料项目'),
('医药、医疗器械、医药研发服务','A05、A11','D06；D03及D01、D02医药项目'),
('电子设备、元器件、光伏、锂电、PCB','A08、A11','D07；D01、D02电子、电气项目'),
('发电、输配电、燃气、能源装备','B03、B06、A09','D08；D01、D02电力燃气项目'),
('运输、港口、仓储、邮政、物流','B06、C04','D08；D01、D02运输仓储项目'),
('水务、环保、土木建筑、批发','A16（相关部分）','D01、D02相应行业；尚无本轮独立细分转型指南'),
('电信、软件、信息技术服务','C03、C17、C25','D02软件服务；相关报告中的行业赋能实践'),
('银行、保险、证券、金融科技','C07、C08','研究报告内的金融机构与应用案例'),
('医院、远程医疗、健康服务','C11、C12','联盟及研究资料，区别于医药制造指南'),
('政务、公共管理、城市运营','C13、C14、C15、C16、C26','数字政府、城市运行与公共服务实践'),
('教育、文旅、娱乐、在线服务','C24及C15相邻场景','跨行业应用参考，未取得本轮独立部委行业指南'),
]
lines += ['', '## 按行业查资料与企业', '', '| 行业／研究方向 | 优先阅读资料编号 | 企业与案例入口 |', '| --- | --- | --- | --- |']
lines += [f'| {industry} | {sources} | {entry} |' for industry,sources,entry in coverage]
lines += ['', '## 检索范围、版本与后续补充', '',
          '网上检索覆盖工信部官网及司局、通信管理局，中国信通院官网与其报告栏目，中国政府网及地方政府转载附件，并核查了中国工业互联网研究院、中国电子技术标准化研究院、行业联盟等入口。本地检索覆盖当前项目及Documents、Downloads、Desktop中的相关文件名，也检查了下载目录中的无语义命名PDF；未发现可直接复用的完整官方行业指南库。', '',
          '只将成功核验的资料纳入57条书目；来源页不能下载PDF、仅有商业报告站转载、只有征集通知或标题提及的候选不计入已取得PDF。轻工业2024年征求意见稿未混入2025年正式版。相同报告的镜像副本、同一附件的多条下载链接均去重。', '',
          '两套工厂名录按560／400条校核，行业跨页断裂已经修复，原始行业值保留在CSV和JSON中。建设主体按名称精确去重为958个；该数不代表958个独立法人或集团。235项案例名单保留应用企业、申报企业、服务商及工具产品字段；100项案例全文已逐项核对目录标题和PDF起始页。', '',
          '本轮未取得可核验的住宿餐饮、零售、法律、招聘等行业独立工信部转型指南，不以通用报告替代专门指南。后续可按业务需要补充其他主管部门或行业协会材料，并保持发布机构分级。', '',
          '## 与本书的衔接', '',
          'A01、A11和A14适合支持“从具体场景拆解改造”的资料研究；分行业指南帮助确认业务环节、数据、工具和人员条件；D类资料为下册扩充提供企业线索。引用前仍按现有研究要求追踪上下游衔接、责任、验收和经营结果，不能把5G联网、设备数控化或自动化成效直接写成大模型AI成效。', '']
(DEST / '工信部行业数字化转型资料汇总.md').write_text('\n'.join(lines))

# A local-only convenience page, without making published Markdown depend on originals.
local_lines=['<!doctype html><meta charset="utf-8"><title>工信部资料本地原文</title>',
             '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:40px auto;padding:0 24px}li{margin:8px 0}</style>',
             '<h1>工信部及相关机构资料：本地原文</h1><p>采集日期：2026-10-17。共57条资料，55份PDF，2条官方HTML；医药主文另存。</p><ul>']
for r in records:
    key='local_pdf' if r['format']=='PDF' else 'local_html'
    rel=Path(r[key]).relative_to(BASE.relative_to(ROOT))
    local_lines.append('<li><a href="' + html.escape(str(rel), quote=True) + '">' + html.escape(r['id']+' '+r['title']) + '</a></li>')
local_lines += ['</ul>']
(BASE / '阅读索引.html').write_text('\n'.join(local_lines))
print(json.dumps(stats, ensure_ascii=False))
