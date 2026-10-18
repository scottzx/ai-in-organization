#!/usr/bin/env python3
"""Render cited official industry figures from the indexed local PDF copies."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '中册-行业解决方案/assets'
GROUPS = [
 ('A11','钢铁',[13,14]), ('A11','石化',[16,17,18,19,20]),
 ('A11','工程机械',[22,23]), ('A11','新能源汽车',[25,26,27]),
 ('A11','机器人',[29,30]), ('A11','医疗装备',[32,33,34,35]),
 ('A11','家电',[37,38,39]), ('A11','制糖',[41]), ('A11','白酒',[43,44]),
 ('A11','美妆日化',[46,47]), ('A11','锂电池',[49,50,51]),
 ('A11','印制板',[53,54]), ('A11','智能移动终端',[56,57]), ('A11','民爆',[59,60,61,62]),
 ('B01','钢铁',[41,43]), ('B02','工程机械',[57]),
 ('B04','石化',[14,16]), ('B05','船舶',[17,44]),
 ('B03','电力',[20]), ('B06','油气储运',[26]),
 ('C09','智慧农业',[9]), ('C10','数字乡村',[11]),
 ('C17','智能云',[41]), ('C25','电信',[23]), ('C07','数字金融',[9,34,35]),
]

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--sources',nargs='*',help='Source IDs to render; default: all planned figures')
 args=parser.parse_args()
 records={r['id']:r for r in json.loads((ROOT/'索引/工信部行业数字化转型资料索引.json').read_text())['records']}
 TARGET.mkdir(parents=True,exist_ok=True)
 tasks=[]
 for source,industry,pages in GROUPS:
  if args.sources and source not in args.sources: continue
  for page in pages: tasks.append((records[source],industry,page))
 def render(task):
  record,industry,page=task
  pdf=ROOT/record['local_pdf']
  if not pdf.is_file(): raise FileNotFoundError(pdf)
  output=TARGET/f"{record['id']}-{industry}-{page}.png"
  if not output.is_file():
   subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-scale-to','3200','-png','-singlefile',str(pdf),str(output.with_suffix(''))],check=True,capture_output=True)
  return {'asset':output.name,'source_id':record['id'],'source_title':record['title'],
          'pdf_page':page,'source_url':record['url']+f'#page={page}',
          'source_sha256':record['sha256'],'asset_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
          'use':'原图摘引；保留原内容和来源，不计入本书原创内容的MIT许可'}
 with ThreadPoolExecutor(max_workers=3) as pool: rendered=list(pool.map(render,tasks))
 manifest=TARGET/'sources.json'
 prior=json.loads(manifest.read_text()) if manifest.exists() else {'figures':[]}
 combined={r['asset']:r for r in prior['figures']}
 combined.update({r['asset']:r for r in rendered})
 manifest.write_text(json.dumps({'title':'中册原图摘引来源','updated_on':'2026-10-18','figures':sorted(combined.values(),key=lambda r:(r['source_id'],r['pdf_page']))},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'rendered':len(rendered),'total_figures':len(combined),'bytes':sum((TARGET/r['asset']).stat().st_size for r in combined.values())},ensure_ascii=False))

if __name__=='__main__': main()
