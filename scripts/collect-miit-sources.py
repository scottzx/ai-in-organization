#!/usr/bin/env python3
"""Download a reviewed URL list of public industry research; audit every PDF.

Usage: python3 scripts/collect-miit-sources.py tmp/miit-research-candidates.json
Originals and full-text extracts stay in the ignored local research directory.
"""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urljoin, urlparse, parse_qs

from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / '资料库/工信部数字化转型原文'
DEST.mkdir(parents=True, exist_ok=True)
(DEST / 'pdf').mkdir(exist_ok=True)
(DEST / 'text').mkdir(exist_ok=True)
(DEST / 'html').mkdir(exist_ok=True)
CACHE = DEST / 'download-audit.json'
previous = {r['url']: r for r in json.loads(CACHE.read_text())} if CACHE.exists() else {}


def fetch(item):
    url = item['url']
    old = previous.get(url)
    if old and old.get('status') == 'downloaded' and (ROOT / old['local_pdf']).exists():
        return old
    record = dict(item)
    record['checked_at'] = '2026-10-17'
    temp = DEST / (item['fetch_id'] + '.download')
    args = ['curl', '-sS', '-L', '--fail', '-A', 'Mozilla/5.0', '--connect-timeout', '12',
            '--max-time', '55', '--max-filesize', '85000000', '-o', str(temp), url]
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        record.update(status='failed', error=result.stderr.strip()[-500:])
        temp.unlink(missing_ok=True)
        return record
    data = temp.read_bytes()
    if not data.startswith(b'%PDF-'):
        soup = BeautifulSoup(data, 'html.parser')
        pdfs = []
        for tag in soup.find_all(['a', 'iframe', 'embed']):
            href = tag.get('href') or tag.get('src') or ''
            resolved = urljoin(url, href)
            query_file = parse_qs(urlparse(resolved).query).get('file', [''])[0]
            if query_file:
                resolved = urljoin(url, query_file)
            if re.search(r'\.pdf(?:[?#]|$)', resolved, re.I):
                pdfs.append({'title': tag.get_text(' ', strip=True), 'url': resolved})
        html_path = DEST / 'html' / (item['fetch_id'] + '.html')
        html_path.write_bytes(data)
        text_path = DEST / 'text' / (item['fetch_id'] + '.txt')
        text_path.write_text(soup.get_text('\n', strip=True))
        record.update(status='html', page_title=soup.title.get_text(strip=True) if soup.title else '',
                      local_html=str(html_path.relative_to(ROOT)), local_text=str(text_path.relative_to(ROOT)),
                      pdf_links=list({v['url']: v for v in pdfs}.values()))
        temp.unlink(missing_ok=True)
        return record
    sha = hashlib.sha256(data).hexdigest()
    target = DEST / 'pdf' / (item['fetch_id'] + '.pdf')
    temp.replace(target)
    try:
        reader = PdfReader(target)
        pages = len(reader.pages)
        excerpt = '\n'.join(p.extract_text() or '' for p in reader.pages[:3])
        out_text = DEST / 'text' / (item['fetch_id'] + '.txt')
        extract = subprocess.run(['pdftotext', '-layout', str(target), str(out_text)],
                                 capture_output=True, text=True)
        if extract.returncode:
            raise RuntimeError(extract.stderr)
        record.update(status='downloaded', pages=pages, bytes=len(data), sha256=sha,
                      local_pdf=str(target.relative_to(ROOT)),
                      local_text=str(out_text.relative_to(ROOT)), cover_excerpt=excerpt[:2200])
    except Exception as error:
        record.update(status='invalid_pdf', error=str(error)[:500])
    return record


items = json.loads((ROOT / sys.argv[1]).read_text())
records = []
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
    for record in pool.map(fetch, items):
        records.append(record)
        print(record['fetch_id'], record['status'], record.get('pages', ''), flush=True)
CACHE.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'downloaded': sum(r['status'] == 'downloaded' for r in records),
                  'total': len(records)}, ensure_ascii=False))
