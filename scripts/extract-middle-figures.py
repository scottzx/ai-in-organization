#!/usr/bin/env python3
"""Render official figures with source-bound, visually reviewed PDF element bounds.

Always render the native page, including its watermarks, then crop its exterior.
Never select the largest embedded image: in several reports it is a watermark,
and figure captions/source lines are separate PDF text objects.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '中册-行业解决方案/assets'
RULES = ROOT / 'scripts/data/middle/图示裁切规则.json'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_page(pdf, page, output, crop=None):
    command = ['pdftoppm', '-f', str(page), '-l', str(page),
               '-scale-to', '3200', '-png', '-singlefile']
    if crop:
        width, height = crop['page_size_points']
        scale = 3200 / max(width, height)
        left, top, right, bottom = crop['pdf_bbox_points']
        x, y = math.floor(left * scale), math.floor(top * scale)
        right, bottom = math.ceil(right * scale), math.ceil(bottom * scale)
        command += ['-x', str(x), '-y', str(y), '-W', str(right-x), '-H', str(bottom-y)]
        crop['pixel_bbox'] = [x, y, right, bottom]
    command += [str(pdf), str(output.with_suffix(''))]
    subprocess.run(command, check=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs='*', help='Source IDs; default: all')
    parser.add_argument('--industries', nargs='*', help='Industry labels; default: all')
    parser.add_argument('--trim-margins', action='store_true',
                        help='Reapply reviewed element bounds to existing cropped figures')
    parser.add_argument('--force', action='store_true', help='Rerender all selected figures')
    args = parser.parse_args()
    rules = json.loads(RULES.read_text())
    tasks = [r for r in rules['figures']
             if (not args.sources or r['source_id'] in args.sources)
             and (not args.industries or r['industry'] in args.industries)]
    if not tasks:
        parser.error('No figures match the selected sources/industries')
    # Verify once per source before rendering; geometry is tied to these PDF versions.
    for source_id in {r['source_id'] for r in tasks}:
        source = rules['sources'][source_id]
        pdf = ROOT / source['local_pdf']
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        if sha256(pdf) != source['sha256']:
            raise ValueError(f'Source PDF differs from reviewed version: {source_id}')
    TARGET.mkdir(parents=True, exist_ok=True)
    manifest = TARGET / 'sources.json'
    prior = json.loads(manifest.read_text()) if manifest.exists() else {'figures': []}
    previous = {r['asset']: r for r in prior['figures']}

    def render(rule):
        source = rules['sources'][rule['source_id']]
        output = TARGET / rule['asset']
        existing = previous.get(rule['asset'], {})
        bounds = rule['crop_pdf_bbox']
        width, height = rule['page_size_points']
        if bounds and not (0 <= bounds[0] < bounds[2] <= width
                           and 0 <= bounds[1] < bounds[3] <= height):
            raise ValueError('Invalid reviewed crop: ' + rule['asset'])
        analysis = {
            'method': rule['method'], 'reviewed_on': rules['reviewed_on'],
            'page_size_points': rule['page_size_points'],
            'pdf_bbox_points': bounds or [0, 0, width, height],
            'cropped': bounds is not None,
            'same_width_display_gain': round(width/(bounds[2]-bounds[0]), 3) if bounds else 1,
            'page_height_removed_fraction': round(1-(bounds[3]-bounds[1])/height, 4) if bounds else 0,
            'review_note': rule['review_note'],
        }
        crop = dict(analysis) if bounds else None
        old_crop = existing.get('crop', {}).get('pdf_bbox_points')
        changed = old_crop != bounds
        before_hash = sha256(output) if output.is_file() else None
        if (args.force or not output.is_file() or changed
                or before_hash != existing.get('asset_sha256')
                or args.trim_margins and bounds):
            render_page(ROOT/source['local_pdf'], rule['pdf_page'], output, crop)
        elif crop and existing.get('crop', {}).get('pixel_bbox'):
            crop['pixel_bbox'] = existing['crop']['pixel_bbox']
        result = {**existing,
            'asset': rule['asset'], 'source_id': rule['source_id'],
            'source_title': source['title'], 'pdf_page': rule['pdf_page'],
            'source_url': source['url'] + f"#page={rule['pdf_page']}",
            'source_sha256': source['sha256'], 'asset_sha256': sha256(output),
            'output_size_px': list(struct.unpack('>II', output.read_bytes()[16:24])),
            'content_detection': analysis, 'required_in': rule['required_in'],
            'page_number_handling': rule['page_number_handling'],
            'use': '图示摘引；仅裁页面外围，保留图内文字、连线、图题、来源、脚注及水印；正文注明来源页码，不计入本书原创内容的 CC BY-NC-SA 4.0 许可',
        }
        for key in ('printed_page', 'figure_titles'):
            if key in rule:
                result[key] = rule[key]
        if crop:
            result['crop'] = crop
            # Preserve historical whole-page hashes; a crop's predecessor may itself be a crop.
            if not existing.get('crop') and before_hash:
                result['uncropped_asset_sha256'] = before_hash
        else:
            result.pop('crop', None)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        rendered = list(pool.map(render, tasks))
    combined = dict(previous)
    combined.update({r['asset']: r for r in rendered})
    manifest.write_text(json.dumps({**prior, 'title': '中册行业图示摘引来源',
        'updated_on': rules['reviewed_on'],
        'crop_rules': '../../scripts/data/middle/图示裁切规则.json',
        'figures': sorted(combined.values(), key=lambda r: (r['source_id'], r['pdf_page']))
    }, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'rendered_or_verified': len(rendered),
        'cropped': sum(bool(r.get('crop')) for r in rendered),
        'total_figures': len(combined),
        'bytes': sum((TARGET/r['asset']).stat().st_size for r in combined.values())
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
