#!/usr/bin/env python3
"""Reproducibility test for scripts/extract-middle-figures.py.

Re-renders the 27 figures recompressed in PR #83 plus B05-船舶-17 into a temp
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

# PR #83 (merge 2af0bc8): 27 figures downscaled to 1713 px + oxipng -o4.
PR83 = ['A11-制糖-41', 'A11-医疗装备-32', 'A11-医疗装备-33', 'A11-医疗装备-34',
        'A11-医疗装备-35', 'A11-印制板-53', 'A11-印制板-54', 'A11-家电-37',
        'A11-工程机械-22', 'A11-工程机械-23', 'A11-新能源汽车-25',
        'A11-新能源汽车-26', 'A11-新能源汽车-27', 'A11-智能移动终端-56',
        'A11-机器人-29', 'A11-机器人-30', 'A11-白酒-44', 'A11-石化-16',
        'A11-石化-17', 'A11-石化-18', 'A11-美妆日化-46', 'A11-钢铁-13',
        'A11-钢铁-14', 'A11-锂电池-49', 'A11-锂电池-50', 'A11-锂电池-51',
        'B01-钢铁-43']
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
        self.assertEqual(len(CASES), 28)
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
