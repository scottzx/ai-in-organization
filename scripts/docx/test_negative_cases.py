#!/usr/bin/env python3
"""反例测试：确认排版脚本对以下错误会报错（全部在临时目录里做，不改仓库源稿、不写 output/）。

  1. front 篇目以外出现“表导-N”          -> check_docx 题注编号项不通过
  2. 不编号篇目（label 0，如 09-结语）含图表 -> build_docx 退出 5（否则会生成“图 0-N”）
  3. 只传入册首 front 篇目给 check-case-structure -> 打印跳过提示、结果通过
  4. 附录内题注字母与本附录字母不一致（附录A 内“表 B-1”）、附录外用字母 -> 题注编号项不通过；附录A 内“表 A-1”通过
  5. 源稿含回退白名单外的缺字（⑤ U+2464，朱雀仿宋无此字） -> build_docx 退出 6；docx 中白名单外字符改用回退字体 -> check_docx 白名单项不通过
  6. docDefaults 改回 Times New Roman / 主题字体引用 -> check_docx 显式开源字体项不通过；基准样张该项通过
  7. pdfinfo 无页数输出 -> toc_fill 抛 TocError（不再 AttributeError）；生成的 docx 权限为 0644
  8. 端到端：PATH 上的 pdfinfo 输出为空 -> build_docx 退出 7，且半成品 docx 已删除（需 soffice）
  9. fontTable.xml 列有 Times New Roman / ＭＳ 明朝、settings themeFontLang 为 ja-JP -> 显式字体项不通过；基准样张 fontTable 只有开源字体
  11. 白名单外篇目在来源索引中标 presentation: brief -> check-case-structure 不通过
  12. 白名单内简述篇仍用七节模板 -> check-case-structure 不通过（简述篇正文不得有其他标题）
  16. 一章多目录（下册第三十章“其他行业案例”）：门类按 groups 所列顺序排、各门类前印一次加粗引导行（不作标题），案例连续编 30.Y
  17. groups 列表里有不存在的子目录 -> build_docx 报错退出，指出该目录
  18. 调换 groups 列表顺序 -> 篇目顺序随之改变（顺序以配置为准，不按目录名排序）
修改临时副本里的源稿一律用 try/finally 还原（出版审读 #82 P2④）。

用法：python3 scripts/docx/test_negative_cases.py     （约 1–2 分钟；全部通过退出 0）
"""
import json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
CAP = '图题/表题 编号“图/表 X-Y”（front 篇目为“图/表 导-Y”）'
fails = []

def ok(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{info}]' if info and not cond else ''))
    if not cond: fails.append(name)

def copy_repo(dst):
    for p in REPO.iterdir():
        if p.name in ('.git', 'output', 'web', 'node_modules'): continue
        (shutil.copytree if p.is_dir() else shutil.copy2)(p, dst / p.name)

def build(repo, vol, out, toc=False, path_prefix=None):
    env = dict(os.environ, BOOK_REPO=str(repo))
    if path_prefix: env['PATH'] = str(path_prefix) + os.pathsep + env.get('PATH', '')
    return subprocess.run([sys.executable, str(HERE / 'build_docx.py'), '--repo', str(repo), '--volume', vol] + ([] if toc else ['--no-toc-pages']) + ['-o', str(out)],
                          env=env, capture_output=True, text=True)

def zip_mutate(src, dst, name, fn):
    import zipfile
    with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            b = zi.read(n); zo.writestr(n, fn(b.decode('utf-8')).encode('utf-8') if n == name else b)
    shutil.copy2(Path(src).with_suffix('.build.json'), Path(dst).with_suffix('.build.json'))

def check(repo, docx, md):
    env = dict(os.environ, BOOK_REPO=str(repo))
    subprocess.run([sys.executable, str(HERE / 'check_docx.py'), str(docx), '-o', str(md)], env=env, capture_output=True, text=True)
    rows = {}
    for line in Path(md).read_text('utf-8').splitlines():
        c = [x.strip() for x in line.split('|')]
        if len(c) > 5 and c[1].isdigit(): rows[c[2]] = (c[4].startswith('✅'), c[5])
    return rows

def mutate(src, dst, fn):
    import docx
    d = docx.Document(str(src)); fn(d); d.save(str(dst))
    shutil.copy2(Path(src).with_suffix('.build.json'), Path(dst).with_suffix('.build.json'))

def main():
    tmp = Path(tempfile.mkdtemp(prefix='neg-'))
    repo = tmp / 'repo'; repo.mkdir(); copy_repo(repo)
    try:
        # 2. label 0 含表 -> 退出 5
        end = repo / '上册-研究报告' / '09-结语.md'; orig = end.read_text('utf-8')
        try:
            end.write_text(orig + '\n\n| a | b |\n|---|---|\n| 1 | 2 |\n', 'utf-8')
            r = build(repo, 'upper', tmp / 'l0.docx')
        finally: end.write_text(orig, 'utf-8')
        ok('不编号篇目含表 -> build_docx 退出 5', r.returncode == 5 and '不编号篇目含表' in r.stdout + r.stderr, f'exit {r.returncode}')

        # 基准样张
        base = tmp / 'base.docx'
        r = build(repo, 'upper', base)
        if r.returncode != 0: ok('基准样张构建', False, r.stdout[-300:] + r.stderr[-300:]); return
        rows = check(repo, base, tmp / 'base.md')
        ok('基准样张 题注编号项通过', rows.get(CAP, (False,))[0], rows.get(CAP, ('', ''))[1])

        def caps(d): return [p for p in d.paragraphs if p.style.name == 'Caption' and re.match(r'^[图表] ?\d+-\d+', p.text)]
        def retag(p, new):
            r0 = p.runs[0]; r0.text = re.sub(r'^([图表]) ?\d+-', lambda m: f'{m.group(1)} {new}-', r0.text, count=1)

        # 1. front 以外“表导-N”
        def f1(d): retag(caps(d)[0], '导')
        mutate(base, tmp / 'n1.docx', f1); rows = check(repo, tmp / 'n1.docx', tmp / 'n1.md')
        ok('front 以外“图/表导-N” -> 题注编号项不通过', not rows[CAP][0] and '导-' in rows[CAP][1], rows[CAP][1])

        # 4. 附录字母：把第一个题注所在章的 h1 改成“附录A”
        def into_app(d, letter):
            c = caps(d)[0]; ps = d.paragraphs; i = next(k for k, p in enumerate(ps) if p._p is c._p)
            h = next(p for p in reversed(ps[:i]) if p.style.name == 'Heading 1')
            for r_ in h.runs: r_.text = ''
            h.runs[0].text = '附录A\u3000测试附录'
            n = 0
            for p in ps[i:]:
                if p.style.name == 'Heading 1': break
                if p in caps(d) or (p.style.name == 'Caption' and re.match(r'^[图表] ?\d+-\d+', p.text)): retag(p, letter)
        def has_cap_err(rows, s): return (not rows[CAP][0]) and s in rows[CAP][1]
        mutate(base, tmp / 'a_ok.docx', lambda d: into_app(d, 'A')); rows = check(repo, tmp / 'a_ok.docx', tmp / 'a_ok.md')
        ok('附录A 内“A-N” -> 不报字母错', not has_cap_err(rows, 'A-'), rows[CAP][1])
        mutate(base, tmp / 'a_bad.docx', lambda d: into_app(d, 'B')); rows = check(repo, tmp / 'a_bad.docx', tmp / 'a_bad.md')
        ok('附录A 内“B-N” -> 题注编号项不通过', has_cap_err(rows, 'B-'), rows[CAP][1])
        def f_out(d): retag(caps(d)[0], 'C')
        mutate(base, tmp / 'a_out.docx', f_out); rows = check(repo, tmp / 'a_out.docx', tmp / 'a_out.md')
        ok('附录外用字母“C-N” -> 题注编号项不通过', has_cap_err(rows, 'C-'), rows[CAP][1])

        # 5. 回退白名单
        WL = '缺字回退仅限 style.yaml fonts.glyph_fallback_chars 白名单字符'
        EF = '文档默认/主题/样式/fontTable 字体均为显式开源字体（无主题引用、无 Times New Roman/宋体/Courier 等；themeFontLang zh-CN）'
        ok('基准样张 白名单项、显式字体项通过', rows.get(WL, (False,))[0] and rows.get(EF, (False,))[0], str(rows.get(WL)) + str(rows.get(EF)))
        ok('基准样张 docx 权限 0644', (base.stat().st_mode & 0o777) == 0o644, oct(base.stat().st_mode & 0o777))
        src = repo / '上册-研究报告' / '01-智力即服务.md'; o1 = src.read_text('utf-8')
        try:
            src.write_text(o1 + '\n\n白名单外缺字测试⑤。\n', 'utf-8')
            r = build(repo, 'upper', tmp / 'gf.docx')
        finally: src.write_text(o1, 'utf-8')
        ok('白名单外缺字 -> build_docx 退出 6', r.returncode == 6 and 'U+2464' in r.stdout, f'exit {r.returncode} ' + r.stdout[-200:])
        from docx.oxml.ns import qn
        def f5(d):
            ps = d.paragraphs; h = next(k for k, p in enumerate(ps) if p.style.name == 'Heading 1')
            p = next(p for p in ps[h:] if p.style.name == 'Normal' and len(p.runs) == 1 and len(p.text) > 10)
            r_ = p.runs[0]; r_.text = '⑤'
            r_._r.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), 'Noto Serif SC')
        mutate(base, tmp / 'n5.docx', f5); rows = check(repo, tmp / 'n5.docx', tmp / 'n5.md')
        ok('docx 中白名单外字符走回退 -> 白名单项不通过', not rows[WL][0] and 'U+2464' in rows[WL][1], rows[WL][1])
        # 6. docDefaults 回到 Times New Roman / 主题字体
        def f6(d):
            rf = d.styles.element.find(qn('w:docDefaults') + '/' + qn('w:rPrDefault') + '/' + qn('w:rPr') + '/' + qn('w:rFonts'))
            rf.set(qn('w:ascii'), 'Times New Roman'); rf.set(qn('w:eastAsiaTheme'), 'minorEastAsia')
        mutate(base, tmp / 'n6.docx', f6); rows = check(repo, tmp / 'n6.docx', tmp / 'n6.md')
        ok('docDefaults 用 Times New Roman/主题字体 -> 显式字体项不通过', not rows[EF][0] and 'Times New Roman' in rows[EF][1] and '主题' in rows[EF][1], rows[EF][1])
        # 7. pdfinfo 无输出
        sys.path.insert(0, str(HERE)); import toc_fill
        real = toc_fill.subprocess.run
        def fake(cmd, *k, **kw):   # LibreOffice 照常出 PDF，pdfinfo 返回空输出
            return subprocess.CompletedProcess(cmd, 1, '', '') if cmd[0] == 'pdfinfo' else real(cmd, *k, **kw)
        toc_fill.subprocess.run = fake
        try: toc_fill.pdf_pages(base, str(tmp)); got = 'no error'
        except toc_fill.TocError as e: got = 'TocError'
        except Exception as e: got = type(e).__name__
        finally: toc_fill.subprocess.run = real
        ok('pdfinfo 无页数输出 -> toc_fill 抛 TocError', got == 'TocError', got)
        # 8. 端到端：pdfinfo 空输出 -> 退出 7、半成品已删
        if shutil.which('soffice'):
            fb = tmp / 'fakebin'; fb.mkdir(); pi = fb / 'pdfinfo'
            pi.write_text('#!/bin/sh\nexit 0\n'); pi.chmod(0o755)
            e7 = tmp / 'e7.docx'
            r = build(repo, 'upper', e7, toc=True, path_prefix=fb)
            ok('端到端 pdfinfo 空输出 -> build_docx 退出 7 且半成品已删除', r.returncode == 7 and not e7.exists() and '已删除半成品' in r.stdout, f'exit {r.returncode} exists={e7.exists()} ' + r.stdout[-200:])
        else: ok('端到端 pdfinfo 空输出（需 soffice）', False, '未找到 soffice')
        # 9. fontTable / themeFontLang
        import zipfile
        ftx = zipfile.ZipFile(base).read('word/fontTable.xml').decode('utf-8')
        ok('基准样张 fontTable 只有开源字体', set(re.findall(r'<w:font [^>]*w:name="([^"]*)"', ftx)) <= {'Noto Sans SC', 'Noto Serif SC', 'LXGW WenKai', 'Zhuque Fangsong (technical preview)', 'Source Serif 4'}, ftx[:300])
        for tag, nm, fn, want in (
            ('ft_tnr', 'word/fontTable.xml', lambda x: x.replace('</w:fonts>', '<w:font w:name="Times New Roman"/></w:fonts>'), 'Times New Roman'),
            ('ft_ms', 'word/fontTable.xml', lambda x: x.replace('</w:fonts>', '<w:font w:name="ＭＳ 明朝"/></w:fonts>'), 'ＭＳ 明朝'),
            ('tfl', 'word/settings.xml', lambda x: re.sub(r'<w:themeFontLang [^>]*/>', '<w:themeFontLang w:val="en-US" w:eastAsia="ja-JP"/>', x), 'ja-JP')):
            zip_mutate(base, tmp / f'{tag}.docx', nm, fn); rows = check(repo, tmp / f'{tag}.docx', tmp / f'{tag}.md')
            ok(f'{nm} 改出 {want} -> 显式字体项不通过', not rows[EF][0] and want in rows[EF][1], rows[EF][1])

        # 10. 缺字回退提示：种数与处数分列；无 build.json 时注明“次数仅供参考”
        check(repo, base, tmp / 'gf_bj.md')
        gl = [l for l in (tmp / 'gf_bj.md').read_text('utf-8').splitlines() if l.startswith('### 缺字回退字符')]
        ok('有 build.json -> 缺字回退提示为“共 N 种、合计 M 处”且无参考注记', len(gl) == 1 and re.search(r'共 \d+ 种、合计 \d+ 处$', gl[0]) is not None, str(gl))
        nb = tmp / 'nobj' / 'base.docx'; nb.parent.mkdir(); shutil.copy2(base, nb)
        check(repo, nb, tmp / 'gf_nobj.md')
        gl = [l for l in (tmp / 'gf_nobj.md').read_text('utf-8').splitlines() if l.startswith('### 缺字回退字符')]
        ok('无 build.json -> 缺字回退提示注明“次数仅供参考”', len(gl) == 1 and gl[0].endswith('（无 build.json，次数仅供参考）') and '种、合计' in gl[0], str(gl))

        # 11. 白名单外的篇目标了 presentation: brief -> check-case-structure 不通过
        idx_p = repo / '索引' / '案例来源索引.json'; idx_src = idx_p.read_text('utf-8')
        try:
            idx = json.loads(idx_src)
            victim = next(e for e in idx['entries'] if e.get('presentation') != 'brief' and (repo / e['path']).exists())
            victim['presentation'] = 'brief'
            idx_p.write_text(json.dumps(idx, ensure_ascii=False, indent=2), 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'check-case-structure.py'), victim['path']], cwd=repo, capture_output=True, text=True)
            res = json.loads(r.stdout)
            ok('白名单外篇目标为 brief -> 结构检查不通过', r.returncode == 1 and res['passed'] is False
               and any('简述篇未列入白名单' in e for item in res['results'] for e in item['errors']), r.stdout[-300:])
        finally:
            idx_p.write_text(idx_src, 'utf-8')

        # 12. 白名单内的简述篇仍用七节模板 -> check-case-structure 不通过
        bidx = json.loads(idx_p.read_text('utf-8'))
        bent = next(e for e in bidx['entries'] if e['id'] == 'C01')
        bp = repo / bent['path']; bsrc = bp.read_text('utf-8')
        try:
            req = json.loads((repo / 'templates' / 'case-structure.json').read_text('utf-8'))['required_h2']
            frag = bent['fragments'][0]
            parts = [bsrc.splitlines()[0], '']
            for i, h in enumerate(req):
                parts += [f'## {h}', '']
                if i == 3: parts += [f'<a id="{frag["anchor"]}"></a>', '', f'**阶段：{frag["stage_label"]}。**', '']
                parts += ['本节为反例测试文字。', '']
            bp.write_text('\n'.join(parts), 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'check-case-structure.py'), bent['path']], cwd=repo, capture_output=True, text=True)
            res = json.loads(r.stdout)
            ok('简述篇仍用七节模板 -> 结构检查不通过', r.returncode == 1 and res['passed'] is False
               and any('简述篇正文不得有其他标题' in e for item in res['results'] for e in item['errors']), r.stdout[-300:])
        finally:
            bp.write_text(bsrc, 'utf-8')

        # 13. 白名单内的简述篇正文超过 400 字 -> check-case-structure 不通过
        try:
            bl = bsrc.splitlines()
            at = next(i for i, l in enumerate(bl) if l.strip() == '## 资料来源')
            bl[at:at] = ['反例测试文字' * 70, '']
            bp.write_text('\n'.join(bl) + '\n', 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'check-case-structure.py'), bent['path']], cwd=repo, capture_output=True, text=True)
            res = json.loads(r.stdout)
            ok('白名单内简述篇正文超过 400 字 -> 结构检查不通过', r.returncode == 1 and res['passed'] is False
               and any('简述篇正文超过400字' in e for item in res['results'] for e in item['errors']), r.stdout[-300:])
        finally:
            bp.write_text(bsrc, 'utf-8')

        # 14. 下册参考文献用旧写法（日期后写页码、页码用—、日期后裸“PDF第x—y页”）-> validate-middle 报错
        lp = next((repo / '下册-案例汇编').glob('D-*/D02-*.md')); lsrc = lp.read_text('utf-8')
        try:
            old = lsrc.replace('(2026-03-30): 19-21[2026-10-29].', '(2026-03-30)[2026-10-29]: 19—21.\n[3] 甲. [乙](https://example.com/a.pdf)[EB/OL]. (2026-03-30): 1—2[2026-10-29].\n[4] 甲. [乙](https://example.com/b.pdf)[EB/OL]. (2026-03-30)[2026-10-29]（PDF第19—21页）.')
            assert old != lsrc
            lp.write_text(old, 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'validate-middle.py')], cwd=repo, capture_output=True, text=True)
            errs = [e for e in json.loads(r.stdout)['errors'] if e.startswith('下册/')]
            ok('下册参考文献旧写法 -> validate-middle 报错', r.returncode == 1
               and any('after the access date' in e for e in errs) and any('half-width "-"' in e for e in errs)
               and any('bare page locator' in e for e in errs), str(errs)[-300:])
        finally:
            lp.write_text(lsrc, 'utf-8')

        # 15. 参考文献新规则：日期后裸“第…节”、说明文字以PDF页作主页码、离散页码用中文逗号/顿号、下册条目无链接题名 -> validate-middle 报错
        lp = next((repo / '下册-案例汇编').glob('D-*/D02-*.md')); lsrc = lp.read_text('utf-8')
        try:
            u = 'https://example.com/a.pdf'
            extra = ('\n[3] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30): 1-2[2026-10-29]. 第4.2—4.6节。引用范围：测试。'
                     '\n[4] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30)[2026-10-29]. 某某公司项目，PDF第35—38页。'
                     '\n[5] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30): 3、6-9[2026-10-29].'
                     '\n[6] 甲. 乙[EB/OL]. (2026-03-30): 1-2[2026-10-29].'
                     '\n[7] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30): 1-2[2026-10-29]. 引用范围：附件3（PDF第21—23页）。')
            new = lsrc.replace('(2026-03-30): 19-21[2026-10-29].', '(2026-03-30): 19-21[2026-10-29].' + extra)
            assert new != lsrc
            lp.write_text(new, 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'validate-middle.py')], cwd=repo, capture_output=True, text=True)
            errs = [e for e in json.loads(r.stdout)['errors'] if e.startswith('下册/')]
            want = {'[3]': 'bare section locator', '[4]': 'main page locator', '[5]': 'half-width ", "', '[6]': 'linked title'}
            ok('参考文献新规则（裸节号、PDF主页码、中文分隔、无链接题名）-> validate-middle 报错，附件PDF页定位不误报', r.returncode == 1
               and all(any(n in e and w in e for e in errs) for n, w in want.items())
               and not any('[7]' in e for e in errs), str(errs)[-400:])
        finally:
            lp.write_text(lsrc, 'utf-8')

        # 16–18. 一章多目录（合并章）与门类引导行
        import yaml
        cfg0 = yaml.safe_load((HERE / 'style.yaml').read_text('utf-8'))
        multi = {c: g for c, g in cfg0['volumes']['lower']['groups'].items() if isinstance(g, list)}
        ok('style.yaml 下册存在一章多目录且每个目录配引导行', len(multi) == 1
           and all(d in (cfg0['volumes']['lower'].get('group_leads') or {}) for g in multi.values() for d in g), str(multi))
        mch, mdirs = next(iter(multi.items()))
        out16 = tmp / 'lower16.docx'
        r = build(repo, 'lower', out16)
        if r.returncode == 0:
            import docx as _dx
            ps = [p for p in _dx.Document(str(out16)).paragraphs if p.text.strip()]
            leads = [cfg0['volumes']['lower']['group_leads'][d] for d in mdirs]
            idx = [i for i, p in enumerate(ps) if p.text.strip() in leads]
            got = [ps[i].text.strip() for i in idx]
            bold = all(all(r_.bold for r_ in ps[i].runs if r_.text.strip()) and not ps[i].style.name.startswith('Heading') for i in idx)
            nxt = [ps[i + 1].text.strip() for i in idx]
            want_first = []
            for d in mdirs:
                f = sorted(p for p in (repo / '下册-案例汇编' / d).glob('*.md') if p.name != 'README.md')[0]
                h = next(l for l in f.read_text('utf-8').splitlines() if l.startswith('# '))[2:].strip()
                want_first.append(re.sub(r'^[A-Z]\d{2}[\s　]*', '', h))
            secs = [p.text.strip() for p in ps if re.match(rf'^{mch}\.\d+ ', p.text.strip())]
            ok('一章多目录 -> 门类按配置顺序、各印一次加粗引导行（非标题），引导行后紧接本门类第一篇',
               got == leads and bold and all(n.endswith(w) for n, w in zip(nxt, want_first)), f'{got} {nxt}')
            ok('一章多目录 -> 合并章案例连续编号', [x.split(' ')[0] for x in secs] == [f'{mch}.{k}' for k in range(1, len(secs) + 1)] and len(secs) >= len(mdirs), str(secs))
        else:
            ok('一章多目录 -> 下册构建成功', False, r.stderr[-300:])
        # 17. 不存在的子目录
        bad = yaml.safe_load((HERE / 'style.yaml').read_text('utf-8'))
        bad['volumes']['lower']['groups'][mch] = list(mdirs) + ['Z-不存在的门类']
        st = tmp / 'style-bad.yaml'; st.write_text(yaml.safe_dump(bad, allow_unicode=True), 'utf-8')
        r = subprocess.run([sys.executable, str(HERE / 'build_docx.py'), '--style', str(st), '--repo', str(repo), '--volume', 'lower', '--no-toc-pages', '-o', str(tmp / 'bad.docx')],
                           env=dict(os.environ, BOOK_REPO=str(repo)), capture_output=True, text=True)
        ok('groups 列表含不存在的子目录 -> build_docx 报错退出', r.returncode != 0 and 'Z-不存在的门类' in (r.stderr + r.stdout) and not (tmp / 'bad.docx').exists(), (r.stderr + r.stdout)[-200:])
        # 18. 调换顺序
        sys.path.insert(0, str(HERE)); import build_docx as bd
        rev = yaml.safe_load((HERE / 'style.yaml').read_text('utf-8'))
        rev['volumes']['lower']['groups'][mch] = list(reversed(mdirs))
        def dirs_of(c):
            seen = []
            for p_, ch_ in bd.volume_items(c, repo, 'lower'):
                if ch_ == mch and p_.parent.name not in seen: seen.append(p_.parent.name)
            return seen
        ok('调换 groups 列表顺序 -> 合并章门类顺序随配置改变', dirs_of(cfg0) == list(mdirs) and dirs_of(rev) == list(reversed(mdirs)), f'{dirs_of(cfg0)} {dirs_of(rev)}')

        # 3. 只传 front 篇目
        cfg = __import__('yaml').safe_load((HERE / 'style.yaml').read_text('utf-8'))
        fr = [f"{v['dir']}/{f}" for v in cfg['volumes'].values() if isinstance(v, dict) and v.get('front') for f in v['front']]
        r = subprocess.run([sys.executable, str(REPO / 'scripts' / 'check-case-structure.py'), fr[0]], cwd=REPO, capture_output=True, text=True)
        ok('只传 front 篇目 -> 跳过提示且通过', '跳过册首不编号篇目' in r.stderr and json.loads(r.stdout)['passed'] is True, r.stderr[-200:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == '__main__':
    main()
    print(f'\n共 {len(fails)} 项失败' if fails else '\n全部通过')
    sys.exit(1 if fails else 0)
