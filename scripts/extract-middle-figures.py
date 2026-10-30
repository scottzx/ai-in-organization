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
import io
import os
import subprocess
import sys
from importlib.metadata import version

# Output pipeline is pinned so assets reproduce byte for byte (PR #83 hashes).
# Install: python3 -m pip install -r scripts/requirements-figures.txt
PINNED = {'pillow': '12.3.0', 'pyoxipng': '9.1.1'}
MAX_WIDTH_PX = 1713  # 14.5 cm text width at 300 ppi
OUTPUT_DPI = 300
OXIPNG_LEVEL = 4


def check_pins():
    found = {name: version(name) for name in PINNED}
    if found != PINNED:
        raise RuntimeError(f'Figure pipeline needs {PINNED}, found {found}; '
                           'see scripts/requirements-figures.txt')

def require_figure_pdfs():
    """REQUIRE_FIGURE_PDFS=1: a missing source PDF is an error, never a skip (tests: also pdftoppm/pins)."""
    return os.environ.get('REQUIRE_FIGURE_PDFS') == '1'


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '中册-行业解决方案/assets'
RULES = ROOT / 'scripts/data/middle/图示裁切规则.json'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize_png(path):
    """Downscale to MAX_WIDTH_PX with LANCZOS (never upscale), tag 300 dpi, oxipng -o4."""
    from PIL import Image
    import oxipng
    with Image.open(path) as image:
        image = image.convert('RGB')
        width, height = image.size
        if width > MAX_WIDTH_PX:
            image = image.resize((MAX_WIDTH_PX, round(height * MAX_WIDTH_PX / width)),
                                 Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, 'PNG', dpi=(OUTPUT_DPI, OUTPUT_DPI))
    path.write_bytes(oxipng.optimize_from_memory(
        buffer.getvalue(), level=OXIPNG_LEVEL, strip=oxipng.StripChunks.safe()))


def render_page(pdf, page, output, crop=None, render_dpi=None):
    """Render with pdftoppm; default long side 3200 px, or render_dpi for native-resolution pages."""
    command = ['pdftoppm', '-f', str(page), '-l', str(page), '-png', '-singlefile']
    command += ['-r', str(render_dpi)] if render_dpi else ['-scale-to', '3200']
    if crop:
        width, height = crop['page_size_points']
        scale = render_dpi / 72 if render_dpi else 3200 / max(width, height)
        left, top, right, bottom = crop['pdf_bbox_points']
        x, y = math.floor(left * scale), math.floor(top * scale)
        right, bottom = math.ceil(right * scale), math.ceil(bottom * scale)
        command += ['-x', str(x), '-y', str(y), '-W', str(right-x), '-H', str(bottom-y)]
        crop['pixel_bbox'] = [x, y, right, bottom]
    command += [str(pdf), str(output.with_suffix(''))]
    subprocess.run(command, check=True, capture_output=True)
    finalize_png(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', nargs='*', help='Source IDs; default: all')
    parser.add_argument('--industries', nargs='*', help='Industry labels; default: all')
    parser.add_argument('--trim-margins', action='store_true',
                        help='Reapply reviewed element bounds to existing cropped figures')
    parser.add_argument('--force', action='store_true', help='Rerender all selected figures')
    args = parser.parse_args()
    check_pins()
    rules = json.loads(RULES.read_text())
    tasks = [r for r in rules['figures']
             if (not args.sources or r['source_id'] in args.sources)
             and (not args.industries or r['industry'] in args.industries)]
    if not tasks:
        parser.error('No figures match the selected sources/industries')
    # Verify once per source before rendering; geometry is tied to these PDF versions.
    # Missing PDFs (资料库/ is gitignored) skip their figures, keeping existing assets and manifest
    # entries; REQUIRE_FIGURE_PDFS=1 makes a missing PDF a hard failure. A changed PDF always fails.
    missing = []
    for source_id in sorted({r['source_id'] for r in tasks}):
        source = rules['sources'][source_id]
        pdf = ROOT / source['local_pdf']
        if not pdf.is_file():
            if require_figure_pdfs():
                raise FileNotFoundError(f'Source PDF missing for {source_id}: {pdf}')
            print(f'skip {source_id}: source PDF missing ({pdf}); set REQUIRE_FIGURE_PDFS=1 to fail',
                  file=sys.stderr)
            missing.append(source_id)
            continue
        if sha256(pdf) != source['sha256']:
            raise ValueError(f'Source PDF differs from reviewed version: {source_id}')
    tasks = [r for r in tasks if r['source_id'] not in missing]
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
        changed = (old_crop != bounds
                   or existing.get('render_dpi') != rule.get('render_dpi'))
        before_hash = sha256(output) if output.is_file() else None
        if (args.force or not output.is_file() or changed
                or before_hash != existing.get('asset_sha256')
                or args.trim_margins and bounds):
            render_page(ROOT/source['local_pdf'], rule['pdf_page'], output, crop,
                        rule.get('render_dpi'))
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
        for key in ('printed_page', 'figure_titles', 'render_dpi'):
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
        'updated_on': max(prior.get('updated_on', ''), rules['reviewed_on']),
        'crop_rules': '../../scripts/data/middle/图示裁切规则.json',
        # Keep manifest order; redraw entries have no source_id/pdf_page, so do not re-sort.
        'figures': list(combined.values())
    }, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'rendered_or_verified': len(rendered),
        'cropped': sum(bool(r.get('crop')) for r in rendered),
        'total_figures': len(combined),
        'bytes': sum((TARGET/r['asset']).stat().st_size for r in combined.values())
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
