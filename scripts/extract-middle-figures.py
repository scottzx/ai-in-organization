#!/usr/bin/env python3
"""Render cited official industry figures from the indexed local PDF copies."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import math
import struct
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

def detect_content_box(pdf, page_number, padding=2):
 """Locate PDF elements, retaining diagram geometry rather than editing pixels."""
 import pdfplumber
 with pdfplumber.open(pdf) as document:
  page=document.pages[page_number-1]
  width,height=float(page.width),float(page.height)
  media=page.page_obj.attrs.get('MediaBox',[0,0,width,height])
  # Some landscape source pages use a reversed MediaBox y axis. pdfminer
  # reports their top coordinates one page-height below the visible page.
  offset=height if float(media[1])>float(media[3]) else 0
  def box(obj):
   return [float(obj['x0']),float(obj['top'])-offset,float(obj['x1']),float(obj['bottom'])-offset]
  images=[(obj,box(obj)) for obj in page.images]
  substantial=[(obj,b) for obj,b in images if (b[2]-b[0])*(b[3]-b[1])>=width*height*.18]
  if len(substantial)==1:
   obj,bounds=substantial[0]
   method='largest-embedded-diagram-bounds'
   object_name=obj.get('name')
  else:
   boxes=[]
   for kind in ('char','image','line','curve','rect'):
    for obj in page.objects.get(kind,[]):
     b=box(obj)
     if b[2]<0 or b[0]>width or b[3]<0 or b[1]>height: continue
     if kind=='rect' and obj.get('fill') and not obj.get('stroke'):
      color=obj.get('non_stroking_color')
      if color==1 or isinstance(color,(tuple,list)) and all(float(v)>.98 for v in color):continue
     boxes.append([max(0,b[0]),max(0,b[1]),min(width,b[2]),min(height,b[3])])
   if not boxes: raise ValueError(f'No visible PDF elements on page {page_number}')
   bounds=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
   method='visible-pdf-element-union'
   object_name=None
  bounds=[max(0,bounds[0]-padding),max(0,bounds[1]-padding),min(width,bounds[2]+padding),min(height,bounds[3]+padding)]
  gain=width/(bounds[2]-bounds[0])
  analysis={'method':method,'pdf_bbox_points':[round(v,4) for v in bounds],
            'page_size_points':[width,height],'same_width_display_gain':round(gain,3),
            'cropped':gain>=1.05,'image_object':object_name}
  if analysis['cropped'] and object_name:
   analysis['page_text_outside_diagram']=[w['text'] for w in page.extract_words()
     if w['x0']<bounds[0] or w['x1']>bounds[2] or w['top']-offset<bounds[1] or w['bottom']-offset>bounds[3]]
  return analysis

def render_page(pdf,page,output,crop=None):
 command=['pdftoppm','-f',str(page),'-l',str(page),'-scale-to','3200','-png','-singlefile']
 if crop:
  width,height=crop['page_size_points']; scale=3200/max(width,height)
  left,top,right,bottom=crop['pdf_bbox_points']
  x,y=math.floor(left*scale),math.floor(top*scale)
  right,bottom=math.ceil(right*scale),math.ceil(bottom*scale)
  command+=['-x',str(x),'-y',str(y),'-W',str(right-x),'-H',str(bottom-y)]
  crop['pixel_bbox']=[x,y,right,bottom]
 command +=[str(pdf),str(output.with_suffix(''))]
 subprocess.run(command,check=True,capture_output=True)

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--sources',nargs='*',help='Source IDs to render; default: all planned figures')
 parser.add_argument('--industries',nargs='*',help='Industry labels to render; default: all')
 parser.add_argument('--trim-margins',action='store_true',help='Locate PDF elements and trim external page margins (requires pdfplumber)')
 args=parser.parse_args()
 records={r['id']:r for r in json.loads((ROOT/'索引/工信部行业数字化转型资料索引.json').read_text())['records']}
 TARGET.mkdir(parents=True,exist_ok=True)
 manifest=TARGET/'sources.json'
 prior=json.loads(manifest.read_text()) if manifest.exists() else {'figures':[]}
 previous={r['asset']:r for r in prior['figures']}
 tasks=[]
 for source,industry,pages in GROUPS:
  if args.sources and source not in args.sources: continue
  if args.industries and industry not in args.industries: continue
  for page in pages: tasks.append((records[source],industry,page))
 def render(task):
  record,industry,page=task
  pdf=ROOT/record['local_pdf']
  if not pdf.is_file(): raise FileNotFoundError(pdf)
  if args.trim_margins and hashlib.sha256(pdf.read_bytes()).hexdigest()!=record['sha256']:
   raise ValueError(f"Source PDF differs from registered version: {record['id']}")
  output=TARGET/f"{record['id']}-{industry}-{page}.png"
  existing=previous.get(output.name,{})
  analysis=detect_content_box(pdf,page) if args.trim_margins else existing.get('content_detection')
  crop=analysis if analysis and analysis.get('cropped') else existing.get('crop')
  before_hash=hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None
  if not output.is_file() or args.trim_margins and crop:
   render_page(pdf,page,output,crop)
  result={**existing,'asset':output.name,'source_id':record['id'],'source_title':record['title'],
          'pdf_page':page,'source_url':record['url']+f'#page={page}',
          'source_sha256':record['sha256'],'asset_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
          'use':'原图摘引；保留原内容和来源，不计入本书原创内容的MIT许可'}
  if analysis: result['content_detection']=analysis
  if crop:
   result['crop']=crop
   result['uncropped_asset_sha256']=existing.get('uncropped_asset_sha256',before_hash)
   result['output_size_px']=list(struct.unpack('>II',output.read_bytes()[16:24]))
   result['use']='图示摘引；按PDF图形边界裁去页面留白，图内文字、连线与模块保持；图题与来源在正文注明，不计入本书原创内容的MIT许可'
  return result
 with ThreadPoolExecutor(max_workers=3) as pool: rendered=list(pool.map(render,tasks))
 combined={r['asset']:r for r in prior['figures']}
 combined.update({r['asset']:r for r in rendered})
 manifest.write_text(json.dumps({**prior,'title':'中册原图摘引来源','updated_on':'2026-10-18','figures':sorted(combined.values(),key=lambda r:(r['source_id'],r['pdf_page']))},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'rendered':len(rendered),'cropped':sum(bool(r.get('crop')) for r in rendered),'total_figures':len(combined),'bytes':sum((TARGET/r['asset']).stat().st_size for r in combined.values())},ensure_ascii=False))

if __name__=='__main__': main()
