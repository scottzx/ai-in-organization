#!/usr/bin/env python3
"""Index official case names, preserving whether evidence is a list or full case."""
import csv
import json
from pathlib import Path
import re

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '索引'
BASE = ROOT / '资料库/工信部数字化转型原文'
audit = {r['fetch_id']: r for r in json.loads((BASE / 'download-audit.json').read_text())}
records = []
category = ''
family = ''
header = []
norm = lambda s: re.sub(r'\s+', '', s or '')
with pdfplumber.open(ROOT / audit['F050']['local_pdf']) as pdf:
    for page_no, page in enumerate(pdf.pages, 1):
        for table in page.extract_tables():
            for row in table:
                values = list(map(norm, row))
                seq = values[0]
                if seq == '序号':
                    header = values
                    if len(values) == 3:
                        family = '数字领航企业实践' if page_no <= 2 else '数字化供应链'
                    elif '服务商名称' in header:
                        family = '工业互联网平台创新应用'
                    elif '工具产品名称' in header:
                        family = '数字化转型通用工具产品应用'
                    else:
                        raise ValueError((page_no, header))
                    continue
                if not seq.isdigit():
                    if seq and not any(values[1:]):
                        category = seq
                        continue
                    raise ValueError((page_no, row))
                cells = dict(zip(header, values))
                title = cells['案例名称']
                company = cells.get('应用企业名称') or cells.get('申报企业名称')
                assert title and company and category, (page_no, row)
                records.append(dict(source_id='D03', category=family + '／' + category, sequence=int(seq),
                                    title=title, company=company, pdf_page=page_no,
                                    company_role='应用企业' if '应用企业名称' in header else '申报企业',
                                    provider=cells.get('服务商名称', ''), product=cells.get('工具产品名称', ''),
                                    evidence_type='官方案例名单',
                                    pdf_url=audit['F050']['url'] + '#page=' + str(page_no)))
assert len(records) == 235, len(records)
print('official list', len(records), flush=True)

sources = [('D04', 'F045', 23), ('D05', 'F046', 25), ('D06', 'F047', 24),
           ('D07', 'F048', 19), ('D08', 'F049', 9)]
for source_id, fid, expected in sources:
    pages = (ROOT / audit[fid]['local_text']).read_text().split('\f')
    toc_pages = [(i + 1, p) for i, p in enumerate(pages[:6]) if '目录' in norm(p)]
    assert toc_pages, fid
    offset = toc_pages[-1][0]
    category = ''
    cases = []
    for _, page in toc_pages:
        for line in page.replace('\b', '').splitlines():
            # OCR/text extraction sometimes separates the digits in 10/11.
            match = re.match(r'^\s*([0-9](?:\s*[0-9])?)\s*[.．]?\s+(.+?)\s+(\d+)\s*$', line)
            if match:
                seq, title, printed = match.groups()
                printed = int(printed)
                title = re.sub(r'\s+', ' ', title).strip()
                page_no = printed + offset
                assert norm(title) in norm(pages[page_no - 1]), (fid, title, page_no)
                cases.append(dict(source_id=source_id, category=category,
                                  sequence=int(norm(seq)), title=title, company='',
                                  printed_page=printed, pdf_page=page_no,
                                  evidence_type='官方案例全文（目录及起始页已核）',
                                  pdf_url=audit[fid]['url'] + '#page=' + str(page_no)))
            else:
                section = re.match(r'^\s*([^\d]+?)\s+(\d+)\s*$', line)
                if section and '工厂' not in section[1]:
                    category = section[1].strip()
    assert len(cases) == expected, (fid, len(cases), expected)
    assert [r['sequence'] for r in cases] == list(range(1, expected + 1)), fid
    records.extend(cases)
    print(fid, len(cases), flush=True)

data = {'collected_at': '2026-10-17', 'record_count': len(records),
        'list_count': 235, 'full_case_count': 100,
        'note': '两套来源之间可能重复；335为案例入口数，不能当作企业数。案例全文已核目录与起始页，尚未逐篇审读结果。',
        'records': records}
(DEST / '工信部典型案例检索索引.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
fields = ['source_id', 'category', 'sequence', 'title', 'company', 'company_role', 'provider', 'product', 'printed_page',
          'pdf_page', 'evidence_type', 'pdf_url']
with (DEST / '工信部典型案例检索索引.csv').open('w', newline='', encoding='utf-8-sig') as stream:
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
lines = ['# 工信部典型案例检索索引', '',
         '[返回资料汇总](工信部行业数字化转型资料汇总.md) · [CSV](工信部典型案例检索索引.csv) · [JSON](工信部典型案例检索索引.json)', '',
         '采集日期：2026-10-17。收录235项官方案例名单和100项官方案例全文入口，合计335个入口。两套来源可能重复，不据此计算企业总数；名单只证明入选，全文已核目录和起始页，尚未逐篇审读过程、投入和结果。', '',
         '五册《2025年5G工厂典型应用实践》由工信部于2026年3月30日发布，书名年份与网页发布日期分别保留。原材料23项、装备25项、消费品24项、电子信息19项、能源交通9项。全文目录的印刷页码已转换为PDF文件页码。', '',
         '## 100项可直接阅读全文的案例', '', '| 分册／来源 | 行业 | 案例／工厂名称 | 原文定位 |', '| --- | --- | --- | --- |']
for r in records[235:]:
    lines.append(f'| {r["source_id"]} | {r["category"]} | {r["title"]} | [PDF第{r["pdf_page"]}页]({r["pdf_url"]}) |')
lines += ['', '## 235项实数融合典型案例名单', '',
          '原文区分申报企业、应用企业和服务商；工具产品类的申报企业可能是产品供给方。以下按原表列名保留角色。', '',
          '| 类别 | 企业角色与名称 | 服务商（原文明示） | 案例名称 | 原文定位 |', '| --- | --- | --- | --- | --- |']
for r in records[:235]:
    lines.append(f'| {r["category"]} | {r["company_role"]}：{r["company"]} | {r["provider"] or "—"} | {r["title"]} | [D03 PDF第{r["pdf_page"]}页]({r["pdf_url"]}) |')
(DEST / '工信部典型案例检索索引.md').write_text('\n'.join(lines) + '\n')
