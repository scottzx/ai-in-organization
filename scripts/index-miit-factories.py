#!/usr/bin/env python3
"""Extract the complete 2024/2025 official 5G factory tables with page locators.
Run with the bundled Python runtime providing pdfplumber.
"""
import collections
import csv
import json
from pathlib import Path
import re

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '索引'
audit = {r['fetch_id']: r for r in json.loads((ROOT / '资料库/工信部数字化转型原文/download-audit.json').read_text())}
rows = []
normalize = lambda text: re.sub(r'\s+', '', text or '')
sources = [
    ('D01', 2025, 'F072', 560,
     'https://www.miit.gov.cn/cms_files/filemanager/1226211233/attach/20258/d329e22c513e4f63a54bb1cc1f1ca577.pdf'),
    ('D02', 2024, 'F071', 400,
     'https://www.miit.gov.cn/cms_files/filemanager/1226211233/attach/202411/a730e76a59ba4ec8b4d63ab184d8c753.pdf'),
]
industry_repairs = {
    '化学原料和化': '化学原料和化学制品制造业',
    '学制品制造业': '化学原料和化学制品制造业',
    '石油、煤炭': '石油、煤炭及其他燃料加工业',
    '及其他燃料加工业': '石油、煤炭及其他燃料加工业',
    '有色金属冶炼和压延': '有色金属冶炼和压延加工业',
    '加工业': '有色金属冶炼和压延加工业',
    '酒、饮料和精制茶制造业': '酒、饮料及精制茶制造业',
}
for source_id, year, fetch_id, expected, source_url in sources:
    before = len(rows)
    last_industry = ''
    path = ROOT / audit[fetch_id]['local_pdf']
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            for table in page.extract_tables():
                for row in table:
                    if len(row) != 5:
                        raise ValueError((fetch_id, page_no, 'column count', row))
                    industry, project, company, operator, region = map(normalize, row)
                    if project == '名称' or company == '建设主体':
                        continue
                    if not project and not company:
                        continue
                    if industry:
                        last_industry = industry
                    assert last_industry and project and company and operator and region, (page_no, row)
                    rows.append(dict(source_id=source_id, year=year,
                                     industry=industry_repairs.get(last_industry, last_industry),
                                     industry_raw=last_industry,
                                     project=project, company=company, operator=operator,
                                     region=region, pdf_page=page_no,
                                     pdf_url=source_url + '#page=' + str(page_no)))
    count = len(rows) - before
    assert count == expected, (fetch_id, 'row count mismatch', count, expected)
    industry_count = len({r['industry'] for r in rows if r['year'] == year})
    assert industry_count == {2025: 48, 2024: 39}[year], (year, industry_count)
    print(year, count, flush=True)

data = {'collected_at': '2026-10-17', 'record_count': len(rows),
        'unique_company_names': len({r['company'] for r in rows}),
        'industry_count': len({r['industry'] for r in rows}),
        'counting_note': '按原文建设主体名称去空白后精确去重；未作集团、法人或企业关系合并。',
        'records': rows}
(DEST / '工信部5G工厂企业索引.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
with (DEST / '工信部5G工厂企业索引.csv').open('w', newline='', encoding='utf-8-sig') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
counts = collections.Counter(r['industry'] for r in rows)
lines = ['# 工信部5G工厂企业检索索引', '',
         '[返回资料汇总](工信部行业数字化转型资料汇总.md) · [CSV](工信部5G工厂企业索引.csv) · [JSON](工信部5G工厂企业索引.json)', '',
         f'采集日期：2026-10-17。汇总2025年560个、2024年400个名录项目，共{len(rows)}条，覆盖{len(counts)}个原文行业类别。按建设主体名称精确去重为{data["unique_company_names"]}个名称；同集团不同子公司、分公司与项目不作人为合并。', '',
         '本表是企业研究线索。名录证明项目入选，不能据此断言投资回报、人工智能应用效果或全企业转型完成。两份名录均采用工信部正式通知所附PDF。行业填充合并单元格并修复跨页断裂名称；2024年的“酒、饮料和精制茶制造业”归并到“酒、饮料及精制茶制造业”，原始提取值保留在CSV／JSON的industry_raw列。页码为PDF文件页码。年度条数和行业数分别核对为560／48与400／39。', '',
         '## 行业分布', '', '| 行业 | 项目数（跨年度，未去重） |', '| --- | ---: |']
lines += [f'| {k} | {v} |' for k, v in counts.items()]
for industry in counts:
    lines += ['', '## ' + industry, '', '| 年度 | 建设主体 | 工厂／项目 | 所在地 | 原文定位 |', '| --- | --- | --- | --- | --- |']
    for row in rows:
        if row['industry'] == industry:
            lines.append(f'| {row["year"]} | {row["company"]} | {row["project"]} | {row["region"]} | [{row["source_id"]} PDF第{row["pdf_page"]}页]({row["pdf_url"]}) |')
(DEST / '工信部5G工厂企业索引.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({k: v for k, v in data.items() if k != 'records'}, ensure_ascii=False))
