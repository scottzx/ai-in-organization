"""缺字回退：某个字符在本段落所用的中文字体里没有字形时，把它单独拆成一个 run，改用 style.yaml fonts.glyph_fallback 中第一个有该字形的开源字体（均已嵌入）。
避免 LibreOffice/Word 临时借用本机未嵌入的字体（如 GothicA1、DejaVuSans）。"""
import copy
from docx.oxml.ns import qn
from fontTools.ttLib import TTFont
import fonts_embed

class GlyphError(Exception):
    """白名单（style.yaml fonts.glyph_fallback_chars）外的字符缺字形，或回退字体也没有该字形。"""

CTRL = {'\u2060'}   # WORD JOINER：零宽排版控制符（宽表防断词），不绘字形，无需字体收录

def whitelist(cfg):
    return set(cfg.get('fonts', {}).get('glyph_fallback_chars') or [])

def fix(doc, cfg, parts=None):
    order = (cfg.get('fonts', {}).get('glyph_fallback') or [])
    names = set(order) | set((cfg.get('fonts', {}).get('embed') or {}).get('files', {}))
    found = fonts_embed.find_fonts(sorted(names), cfg)
    cmaps = {n: set(TTFont(str(v['regular']), lazy=True).getBestCmap()) for n, v in found.items()}
    log = {}; allow = whitelist(cfg); bad = {}
    roots = [doc.element] + [p for p in (parts or [])]
    for root in roots:
        for r in list(root.iter(qn('w:r'))):
            t = r.find(qn('w:t'))
            if t is None or not t.text: continue
            rf = r.find(qn('w:rPr') + '/' + qn('w:rFonts'))
            east = rf.get(qn('w:eastAsia')) if rf is not None else None
            if east not in cmaps: continue
            cm = cmaps[east]
            if all(ord(c) < 0x80 or c in CTRL or ord(c) in cm for c in t.text): continue
            # 按“有字/缺字”切段
            segs, cur, curf = [], '', None
            for c in t.text:
                f = None
                if ord(c) >= 0x80 and c not in CTRL and ord(c) not in cm:
                    f = next((n for n in order if n in cmaps and ord(c) in cmaps[n]), None) if c in allow else None
                    if not f:
                        k = f'U+{ord(c):04X} {c}（{east}缺字，' + ('回退字体也无此字）' if c in allow else '不在 fonts.glyph_fallback_chars 白名单）')
                        bad[k] = bad.get(k, 0) + 1
                    else: log.setdefault(f'U+{ord(c):04X} {c}', {'from': east, 'to': f, 'count': 0}); log[f'U+{ord(c):04X} {c}']['count'] += 1
                if f != curf and cur: segs.append((cur, curf)); cur = ''
                cur += c; curf = f
            if cur: segs.append((cur, curf))
            if len(segs) == 1 and segs[0][1] is None: continue
            parent = r.getparent(); idx = parent.index(r)
            for i, (s, f) in enumerate(segs):
                nr = copy.deepcopy(r); nt = nr.find(qn('w:t')); nt.text = s
                nt.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                if f:
                    nrf = nr.find(qn('w:rPr') + '/' + qn('w:rFonts'))
                    nrf.set(qn('w:eastAsia'), f)   # 只换中文字体槽；西文槽仍是 Source Serif 4
                parent.insert(idx + i, nr)
            parent.remove(r)
    if bad:
        raise GlyphError('；'.join(f'{k} {n} 处' for k, n in bad.items()))
    return log
