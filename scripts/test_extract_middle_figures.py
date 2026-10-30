#!/usr/bin/env python3
"""Reproducibility test for scripts/extract-middle-figures.py.

Re-renders the PR #83 figure still in the book (B01-钢铁-43; the A11 ones were removed by #87/#89) plus B05-船舶-17 into a temp
dir and checks each PNG's sha256 against 中册-行业解决方案/assets/sources.json.
Source PDFs are read from each source's local_pdf (gitignored 资料库/ dir);
the test skips cleanly when a PDF, pdftoppm or the pinned packages are missing.
Run: python3 scripts/test_extract_middle_figures.py
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'extract_middle_figures', ROOT / 'scripts/extract-middle-figures.py')
extract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extract)

# PR #83 (merge 2af0bc8) figures still in the book after #89 removed the A11 ones.
PR83 = ['B01-钢铁-43']
CASES = [name + '.png' for name in PR83] + ['B05-船舶-17.png']


class ReproduceFigures(unittest.TestCase):
    def test_byte_identical(self):
        try:
            extract.check_pins()
        except Exception as error:  # pins missing or different
            self.skipTest(str(error))
        if not shutil.which('pdftoppm'):
            self.skipTest('pdftoppm not installed')
        rules = json.loads(extract.RULES.read_text())
        manifest = json.loads((extract.TARGET / 'sources.json').read_text())
        expected = {r['asset']: r['asset_sha256'] for r in manifest['figures']}
        by_asset = {r['asset']: r for r in rules['figures']}
        self.assertEqual(len(CASES), 2)
        with tempfile.TemporaryDirectory() as tmp:
            for asset in CASES:
                rule = by_asset[asset]
                source = rules['sources'][rule['source_id']]
                pdf = ROOT / source['local_pdf']
                if not pdf.is_file():
                    self.skipTest(f'source PDF not available: {pdf}')
                if extract.sha256(pdf) != source['sha256']:
                    self.skipTest(f'source PDF differs from reviewed version: {pdf}')
                bounds = rule['crop_pdf_bbox']
                crop = ({'page_size_points': rule['page_size_points'],
                         'pdf_bbox_points': bounds} if bounds else None)
                output = Path(tmp) / asset
                extract.render_page(pdf, rule['pdf_page'], output, crop,
                                    rule.get('render_dpi'))
                with self.subTest(asset=asset):
                    self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),
                                     expected[asset])
                    self.assertLessEqual(
                        int.from_bytes(output.read_bytes()[16:20], 'big'),
                        extract.MAX_WIDTH_PX)


if __name__ == '__main__':
    unittest.main(verbosity=2)
