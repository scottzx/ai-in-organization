#!/usr/bin/env python3
"""下载并校验书稿用的中文开源字体（Scott 2026-10-30 定，全部 SIL OFL 1.1），放到 fonts/cache/（不入 git）。

  python3 scripts/docx/fonts/fetch_fonts.py        # 已下载且 sha256 相符则跳过

下载地址与 sha256 均固定；sha256 不符即报错退出，不使用。
Noto Sans SC / Noto Serif SC 官方只发可变字体（[wght]），Word 不能可靠嵌入可变字体，
本脚本用 fontTools instancer 按 wght=400/700 生成静态 Regular/Bold（OFL 允许修改；Noto 无保留字体名，名称保持不变）。
西文字体 Source Serif 4 已随仓库放在 fonts/SourceSerif4/，不在此下载。
"""
import hashlib, io, sys, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / 'cache'
GF = 'https://raw.githubusercontent.com/google/fonts'
FONTS = [
    # (缓存文件名, URL, sha256, 处理)
    ('NotoSansSC-VF.ttf', f'{GF}/a85815a42757630ce188fdad368c2dfc444d4773/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf',
     'a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da', ('instance', 'NotoSansSC')),
    ('NotoSerifSC-VF.ttf', f'{GF}/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf',
     '050080d9255a86808f2945bffac582b31ef32bc36411ce29563b4961670c66f9', ('instance', 'NotoSerifSC')),
    ('LXGWWenKai-Regular.ttf', 'https://github.com/lxgw/LxgwWenKai/releases/download/v1.530/LXGWWenKai-Regular.ttf',
     '2d73eea94ad808999d90c0000c239a84a33b09d4bc6ab6c5b8bbf1eda8a7fc8b', None),
    ('ZhuqueFangsong-v0.212.zip', 'https://github.com/TrionesType/zhuque/releases/download/v0.212/ZhuqueFangsong-v0.212.zip',
     'bb8b661a7643d2296a72d9d10530a00949419c4e527fb61783f73c2ba1a8c062', ('unzip', 'ZhuqueFangsong-Regular.ttf')),
]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    CACHE.mkdir(exist_ok=True)
    for name, url, want, post in FONTS:
        p = CACHE / name
        if not (p.exists() and sha(p) == want):
            print('下载', url)
            with urllib.request.urlopen(url) as r: p.write_bytes(r.read())
        got = sha(p)
        if got != want:
            p.unlink(); sys.exit(f'sha256 不符：{name}\n  期望 {want}\n  实得 {got}')
        print('校验通过', name)
        if post and post[0] == 'unzip':
            out = CACHE / post[1]
            if not out.exists(): out.write_bytes(zipfile.ZipFile(p).read(post[1]))
        elif post and post[0] == 'instance':
            from fontTools.ttLib import TTFont
            from fontTools.varLib import instancer
            for w, sub in ((400, 'Regular'), (700, 'Bold')):
                out = CACHE / f'{post[1]}-{sub}.ttf'
                if out.exists(): continue
                f = instancer.instantiateVariableFont(TTFont(str(p)), {'wght': w}, updateFontNames=True)
                f.save(str(out)); print('  生成静态', out.name)
    print('完成：', ', '.join(sorted(x.name for x in CACHE.glob('*.ttf') if 'VF' not in x.name)))

if __name__ == '__main__':
    main()
