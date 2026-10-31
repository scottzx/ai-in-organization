#!/usr/bin/env python3
"""Tests for scripts/extract-middle-figures.py.

1. ReproduceFigures: checks 图示裁切规则.json covers exactly the 9 B01–B06 figures (A11 rules were
   removed in #89) and re-renders the 6 produced by the pinned pipeline into a temp dir and checks each sha256 against
   中册-行业解决方案/assets/sources.json and width <= 1713 px.
2. ManifestWriting: runs main() on a synthetic PDF in a temp tree and checks the manifest fields it
   writes (asset_sha256, output_size_px, crop.pixel_bbox, 300 dpi, no upscale, no rerender).

Source PDFs are read from each source's local_pdf (gitignored 资料库/ dir). By default the tests
skip when a PDF, pdftoppm or the pinned packages are missing; with REQUIRE_FIGURE_PDFS=1 any of
those is a failure instead (use this in CI/release checks).
Run: python3 scripts/test_extract_middle_figures.py
     REQUIRE_FIGURE_PDFS=1 python3 scripts/test_extract_middle_figures.py
"""
from pathlib import Path
from unittest import mock
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'extract_middle_figures', ROOT / 'scripts/extract-middle-figures.py')
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)

# B01-钢铁-43, B02-工程机械-57, B05-船舶-44 (PR 1/3) and B01-钢铁-41, B03-电力-20, B04-石化-14,
# B06-油气储运-26 (PR 2/3) were redrawn by the book (scripts/figures, fig-*) and left the crop pipeline.
CASES = []  # 中册已无原图裁切（场景图谱均改为精简表）
# Assets produced by the pinned pipeline (PR #83/#85).
REPRODUCIBLE = []


def unavailable(test, reason):
    """Skip, or fail when REQUIRE_FIGURE_PDFS=1."""
    if extract.require_figure_pdfs():
        test.fail(f'REQUIRE_FIGURE_PDFS=1: {reason}')
    test.skipTest(reason)


def check_toolchain(test):
    try:
        extract.check_pins()
    except Exception as error:  # pins missing or different
        unavailable(test, str(error))
    if not shutil.which('pdftoppm'):
        unavailable(test, 'pdftoppm not installed')


def png_info(path):
    data = path.read_bytes()
    return list(struct.unpack('>II', data[16:24]))


class RequireSwitch(unittest.TestCase):
    def test_env_values(self):
        for value, expected in ((None, False), ('0', False), ('', False), ('1', True)):
            env = {k: v for k, v in os.environ.items() if k != 'REQUIRE_FIGURE_PDFS'}
            if value is not None:
                env['REQUIRE_FIGURE_PDFS'] = value
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertIs(extract.require_figure_pdfs(), expected)

    def test_missing_pdf_skips_by_default_fails_when_required(self):
        with mock.patch.dict(os.environ, {'REQUIRE_FIGURE_PDFS': '0'}):
            with self.assertRaises(unittest.SkipTest):
                unavailable(self, 'missing.pdf')
        with mock.patch.dict(os.environ, {'REQUIRE_FIGURE_PDFS': '1'}):
            with self.assertRaises(self.failureException):
                unavailable(self, 'missing.pdf')


class ReproduceFigures(unittest.TestCase):
    def test_rules_cover_cases(self):
        rules = json.loads(extract.RULES.read_text())
        self.assertEqual(sorted(r['asset'] for r in rules['figures']), sorted(CASES))
        used = {r['source_id'] for r in rules['figures']}
        self.assertTrue(used <= set(rules['sources']))

    def test_self_drawn_inventory_matches_manifest(self):
        rules = json.loads(extract.RULES.read_text())
        manifest = json.loads((extract.TARGET / 'sources.json').read_text())
        inventory = [r['asset'] for r in rules['figures']] + [r['asset'] for r in rules['self_drawn']]
        self.assertEqual(len(inventory), len(set(inventory)))
        self.assertEqual(sorted(inventory), sorted(r['asset'] for r in manifest['figures']))

    def test_byte_identical(self):
        check_toolchain(self)
        rules = json.loads(extract.RULES.read_text())
        manifest = json.loads((extract.TARGET / 'sources.json').read_text())
        expected = {r['asset']: r for r in manifest['figures']}
        by_asset = {r['asset']: r for r in rules['figures']}
        with tempfile.TemporaryDirectory() as tmp:
            for asset in REPRODUCIBLE:
                rule = by_asset[asset]
                source = rules['sources'][rule['source_id']]
                pdf = ROOT / source['local_pdf']
                if not pdf.is_file():
                    unavailable(self, f'source PDF not available: {pdf}')
                if extract.sha256(pdf) != source['sha256']:
                    unavailable(self, f'source PDF differs from reviewed version: {pdf}')
                bounds = rule['crop_pdf_bbox']
                crop = ({'page_size_points': rule['page_size_points'],
                         'pdf_bbox_points': bounds} if bounds else None)
                output = Path(tmp) / asset
                extract.render_page(pdf, rule['pdf_page'], output, crop,
                                    rule.get('render_dpi'))
                with self.subTest(asset=asset):
                    self.assertEqual(extract.sha256(output), expected[asset]['asset_sha256'])
                    self.assertEqual(png_info(output), expected[asset]['output_size_px'])
                    self.assertLessEqual(png_info(output)[0], extract.MAX_WIDTH_PX)


class ManifestWriting(unittest.TestCase):
    def setUp(self):
        check_toolchain(self)
        from PIL import Image, ImageDraw
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        pdf = self.tmp / 'src.pdf'
        # A4 page at 72 dpi -> 595x842 pt; draw a box so the render is non-trivial.
        page = Image.new('RGB', (595, 842), 'white')
        ImageDraw.Draw(page).rectangle((100, 100, 495, 400), outline='black', width=3)
        page.save(pdf, 'PDF', resolution=72)
        self.rules = {
            'reviewed_on': '2026-10-30',
            'sources': {'T01': {'title': '测试来源', 'url': 'https://example.invalid/t.pdf',
                                'local_pdf': 'src.pdf', 'sha256': extract.sha256(pdf)}},
            'figures': [
                {'asset': 'T01-wide-1.png', 'source_id': 'T01', 'industry': 't', 'pdf_page': 1,
                 'required_in': ['X.md'], 'page_size_points': [595, 842],
                 'crop_pdf_bbox': [90, 90, 505, 410], 'method': 'test', 'review_note': 'n',
                 'page_number_handling': 'p', 'render_dpi': 400},
                {'asset': 'T01-narrow-1.png', 'source_id': 'T01', 'industry': 't', 'pdf_page': 1,
                 'required_in': ['X.md'], 'page_size_points': [595, 842],
                 'crop_pdf_bbox': [90, 90, 300, 410], 'method': 'test', 'review_note': 'n',
                 'page_number_handling': 'p'},
            ]}
        (self.tmp / 'rules.json').write_text(json.dumps(self.rules, ensure_ascii=False))
        self.target = self.tmp / 'assets'
        self.target.mkdir()
        (self.target / 'redraw-x.png').write_bytes(b'redraw')  # non-extracted entry, left as is
        (self.target / 'sources.json').write_text(json.dumps(
            {'figures': [{'asset': 'redraw-x.png', 'generator': 'kept'}]}))

    def run_main(self, *args):
        with mock.patch.object(extract, 'ROOT', self.tmp), \
                mock.patch.object(extract, 'TARGET', self.target), \
                mock.patch.object(extract, 'RULES', self.tmp / 'rules.json'), \
                mock.patch.object(sys, 'argv', ['extract', *args]), \
                mock.patch('builtins.print'):
            extract.main()
        return json.loads((self.target / 'sources.json').read_text())

    def test_manifest_fields(self):
        from PIL import Image
        manifest = self.run_main()
        by_asset = {r['asset']: r for r in manifest['figures']}
        self.assertEqual(list(by_asset), ['redraw-x.png', 'T01-wide-1.png', 'T01-narrow-1.png'])
        self.assertEqual(by_asset['redraw-x.png'], {'asset': 'redraw-x.png', 'generator': 'kept'})
        for asset in ('T01-wide-1.png', 'T01-narrow-1.png'):
            entry, path = by_asset[asset], self.target / asset
            with self.subTest(asset=asset):
                self.assertEqual(entry['asset_sha256'], extract.sha256(path))
                self.assertEqual(entry['source_sha256'], self.rules['sources']['T01']['sha256'])
                with Image.open(path) as image:
                    self.assertEqual(list(image.size), entry['output_size_px'])
                    self.assertEqual([round(v) for v in image.info['dpi']], [300, 300])
                self.assertLessEqual(entry['output_size_px'][0], extract.MAX_WIDTH_PX)
                self.assertEqual(entry['source_url'], 'https://example.invalid/t.pdf#page=1')
                self.assertTrue(entry['crop']['cropped'])
        # 400 dpi render of a 415 pt wide crop ~ 2306 px, downscaled to exactly 1713.
        wide = by_asset['T01-wide-1.png']
        self.assertEqual(wide['output_size_px'][0], extract.MAX_WIDTH_PX)
        x0, y0, x1, y1 = wide['crop']['pixel_bbox']
        self.assertGreater(x1 - x0, extract.MAX_WIDTH_PX)
        self.assertEqual(wide['output_size_px'][1], round((y1 - y0) * 1713 / (x1 - x0)))
        # Default render (long side 3200 px) of a 210 pt wide crop ~ 798 px: never upscaled.
        narrow = by_asset['T01-narrow-1.png']
        x0, _, x1, _ = narrow['crop']['pixel_bbox']
        self.assertEqual(narrow['output_size_px'][0], x1 - x0)
        self.assertNotIn('render_dpi', narrow)
        self.assertEqual(wide['render_dpi'], 400)

    def test_rerun_is_stable_and_detects_tampering(self):
        first = self.run_main()
        mtime = (self.target / 'T01-wide-1.png').stat().st_mtime_ns
        self.assertEqual(self.run_main(), first)
        self.assertEqual((self.target / 'T01-wide-1.png').stat().st_mtime_ns, mtime)
        (self.target / 'T01-wide-1.png').write_bytes(b'tampered')
        self.assertEqual(self.run_main(), first)  # hash mismatch -> re-rendered identically

    def test_missing_pdf_skips_by_default(self):
        (self.tmp / 'src.pdf').unlink()
        with mock.patch.dict(os.environ, {'REQUIRE_FIGURE_PDFS': '0'}), \
                mock.patch('sys.stderr'):
            manifest = self.run_main()
        self.assertEqual(manifest['figures'], [{'asset': 'redraw-x.png', 'generator': 'kept'}])
        self.assertFalse((self.target / 'T01-wide-1.png').exists())

    def test_missing_pdf_fails_when_required(self):
        before = (self.target / 'sources.json').read_text()
        (self.tmp / 'src.pdf').unlink()
        with mock.patch.dict(os.environ, {'REQUIRE_FIGURE_PDFS': '1'}):
            with self.assertRaises(FileNotFoundError):
                self.run_main()
        self.assertFalse((self.target / 'T01-wide-1.png').exists())
        self.assertEqual((self.target / 'sources.json').read_text(), before)

    def test_changed_pdf_always_fails(self):
        (self.tmp / 'src.pdf').write_bytes(b'%PDF-1.4 changed')
        with mock.patch.dict(os.environ, {'REQUIRE_FIGURE_PDFS': '0'}):
            with self.assertRaises(ValueError):
                self.run_main()

if __name__ == '__main__':
    unittest.main(verbosity=2)
