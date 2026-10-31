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
  10. 缺字回退提示：有 build.json 时为“共 N 种、合计 M 处”；无 build.json 时注明“次数仅供参考”
  11. 白名单外篇目在来源索引中标 presentation: brief -> check-case-structure 不通过
  12. 白名单内简述篇仍用七节模板 -> check-case-structure 不通过（简述篇正文不得有其他标题）
  13. 白名单内简述篇正文超过 400 字 -> check-case-structure 不通过
  14. 下册参考文献旧写法（日期后写页码、页码用—、日期后裸“PDF第x—y页”）-> validate-middle 报错
  15. 参考文献新规则（裸节号、PDF 作主页码、离散页码分隔、无链接题名）-> validate-middle 报错；附件 PDF 页定位不误报
  16. 一章多目录（下册第三十章“其他行业案例”）：门类按 groups 所列顺序排、各门类前印一次加粗引导行（不作标题），案例连续编 30.Y
  17. groups 列表里有不存在的子目录 -> build_docx 报错退出，指出该目录
  18. 调换 groups 列表顺序 -> 篇目顺序随之改变（顺序以配置为准，不按目录名排序）
  19. 成品范围内 Markdown 出现失效 #锚点 / 指向不存在的文件 -> scripts/check-md-links.py 退出 1 并列出该处；仓库现状 0 处
  20. 不给 -o -> 默认输出 {书名}-{册}.docx（如 企业数智化转型思路-上册.docx），文件名不含“样张”
  21. 同一目录在 groups 中列了两次 -> build_docx 报错退出，不留半成品
  22. 某章目录列表为空、或目录里没有可排篇目（只有 README）-> build_docx 报错退出，不留半成品
  23. group_leads 配给单目录章的目录 -> build_docx 报错退出（引导行只用于多目录章）
  24. “见PDF第x—y页”作主页码、离散页码“3,6”缺空格 -> validate-middle 报错
  25. 日期后裸写“第…项/部分” -> validate-middle 报错；“引用范围：第…项”不报
  26. 封面节页眉印书名、页脚有 PAGE 域 -> 封面页眉页码项不通过；目录节页码改阿拉伯数字 -> 目录页码项不通过
  27. 去掉表格 tblHeader、表题/表头 keepNext -> 跨页表各项不通过
  34. 表身行加 cantSplit/keepNext -> 表身不绑定项不通过（出版审读 #108 复审 P1）
  35. 正文节 start=2 -> 正文页码项不通过
  36. 封面节与目录节共用页眉部件 -> 部件不共用项不通过
  37. 书稿出现“本章索引” -> build_docx 退出 8
  28. 包里放回 stylesWithEffects（Courier）、样式出现 themeColor、numbering 出现 Symbol -> 成品包项不通过
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

        # 附录B 图源索引表图号与成品图题不符 -> 对照项不通过
        APPB = '图源索引表图号与成品图题一致（按图题文字对照）'
        def fb(d):
            fc = next(p for p in d.paragraphs if p.style.name == 'Caption' and re.match(r'^图 ?\d+-\d+\u3000', p.text))
            num, title = re.match(r'^图 ?(\d+-\d+)\u3000(.+)$', fc.text.strip()).groups()
            a, b = num.split('-'); t = d.add_table(rows=2, cols=2)
            t.cell(0, 0).text = f'图 {num}'; t.cell(0, 1).text = title              # 一致的一行
            t.cell(1, 0).text = f'图 {a}-{int(b) + 7}'; t.cell(1, 1).text = title   # 错号的一行
        mutate(base, tmp / 'nb.docx', fb); rows = check(repo, tmp / 'nb.docx', tmp / 'nb.md')
        ok('附录B 图号与成品图题不符 -> 图源索引表对照项不通过', APPB in rows and not rows[APPB][0] and '索引表为' in rows[APPB][1], str(rows.get(APPB)))

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

        # 26–33. 出版审读 d7b16e3 预审 P1/P2：封面版权页无页眉页码、目录罗马页码、跨页表头、成品包清理
        cfgL = __import__('yaml').safe_load((HERE / 'style.yaml').read_text('utf-8'))
        COV = '封面、版权页 不印页眉页码（第1节页眉页脚为本节专用空白部件）'
        TOCPG = f'目录节 页码{cfgL["page"]["front_matter_page_format"]}自1起'
        BODYPG = '正文节 阿拉伯页码自1起（自第一篇，上册即导论）'
        TH = '表格 首行为重复表头（tblHeader）'; TK = '表格 表头与下行同页（keepNext）且不跨页（cantSplit）'; TC = '表题 与下段同页（keepNext）'
        PK = '成品包无 stylesWithEffects 部件及引用、无 Courier/Symbol 字体名、样式无主题色（themeColor）'
        rows0 = check(repo, base, tmp / 'base2.md')
        ok('基准样张 封面无页眉页码、目录/正文页码、表头重复、成品包清理各项通过', all(rows0.get(k, (False,))[0] for k in (COV, TOCPG, BODYPG, TH, TK, TC, PK)), str({k: rows0.get(k) for k in (COV, TOCPG, BODYPG, TH, TK, TC, PK)}))
        def f_cov(d): d.sections[0].header.paragraphs[0].text = cfgL['book']['title']
        mutate(base, tmp / 'cov.docx', f_cov); rows = check(repo, tmp / 'cov.docx', tmp / 'cov.md')
        ok('封面节页眉印了书名 -> 封面页眉页码项不通过', not rows[COV][0], str(rows.get(COV)))
        def f_covpg(d):
            from docx.oxml import OxmlElement as OE
            fp = d.sections[0].footer.paragraphs[0]; r_ = OE('w:r'); it = OE('w:instrText'); it.text = ' PAGE '; r_.append(it); fp._p.append(r_)
        mutate(base, tmp / 'covpg.docx', f_covpg); rows = check(repo, tmp / 'covpg.docx', tmp / 'covpg.md')
        ok('封面节页脚有 PAGE 域 -> 封面页眉页码项不通过', not rows[COV][0], str(rows.get(COV)))
        def f_tocpg(d):
            from docx.oxml.ns import qn as Q
            d.sections[1]._sectPr.find(Q('w:pgNumType')).set(Q('w:fmt'), 'decimal')
        mutate(base, tmp / 'tocpg.docx', f_tocpg); rows = check(repo, tmp / 'tocpg.docx', tmp / 'tocpg.md')
        ok('目录节页码改成阿拉伯数字 -> 目录页码项不通过', not rows[TOCPG][0], str(rows.get(TOCPG)))
        def f_th(d):
            from docx.oxml.ns import qn as Q
            tp = d.tables[0].rows[0]._tr.trPr; tp.remove(tp.find(Q('w:tblHeader')))
            next(p for p in d.paragraphs if p.style.name == 'Caption' and p.text.startswith('表')).paragraph_format.keep_with_next = False
            for c in d.tables[1].rows[0].cells:
                for q_ in c.paragraphs: q_.paragraph_format.keep_with_next = False
        mutate(base, tmp / 'th.docx', f_th); rows = check(repo, tmp / 'th.docx', tmp / 'th.md')
        ok('去掉首个表的 tblHeader -> 重复表头项不通过', not rows[TH][0] and '第1个表格' in rows[TH][1], str(rows.get(TH)))
        ok('表题去掉 keepNext -> 表题同页项不通过', not rows[TC][0], str(rows.get(TC)))
        ok('表头行去掉 keepNext -> 表头同页项不通过', not rows[TK][0] and '第2个表格' in rows[TK][1], str(rows.get(TK)))
        def add_swe(src, dst):
            import zipfile
            with zipfile.ZipFile(src) as zi, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zo:
                for n in zi.namelist(): zo.writestr(n, zi.read(n))
                zo.writestr('word/stylesWithEffects.xml', '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Courier"/></w:rPr></w:rPrDefault></w:docDefaults></w:styles>')
            shutil.copy2(Path(src).with_suffix('.build.json'), Path(dst).with_suffix('.build.json'))
        add_swe(base, tmp / 'swe.docx'); rows = check(repo, tmp / 'swe.docx', tmp / 'swe.md')
        ok('包里放回 stylesWithEffects（含 Courier）-> 成品包项不通过', not rows[PK][0] and 'stylesWithEffects' in rows[PK][1] and 'Courier' in rows[PK][1], str(rows.get(PK)))
        zip_mutate(base, tmp / 'theme.docx', 'word/styles.xml', lambda x: x.replace('<w:color w:val="000000"/>', '<w:color w:val="4F81BD" w:themeColor="accent1"/>', 1))
        rows = check(repo, tmp / 'theme.docx', tmp / 'theme.md')
        ok('样式里出现 themeColor 主题蓝 -> 成品包项不通过', not rows[PK][0] and '主题色' in rows[PK][1], str(rows.get(PK)))
        zip_mutate(base, tmp / 'sym.docx', 'word/numbering.xml', lambda x: re.sub(r'\s*/>\s*$', '>', x, count=1).replace('</w:numbering>', '') + '<w:abstractNum w:abstractNumId="9"><w:lvl w:ilvl="0"><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr></w:lvl></w:abstractNum></w:numbering>')
        rows = check(repo, tmp / 'sym.docx', tmp / 'sym.md')
        ok('numbering.xml 出现 Symbol 字体 -> 成品包项不通过', not rows[PK][0] and 'Symbol' in rows[PK][1], str(rows.get(PK)))

        # 34–37. 出版审读 #108 复审：表身不绑定、正文页码自1、封面页眉部件不共用、“本章索引”报错
        TB = '表格 表身各行不加 cantSplit/keepNext（防表题被挤成孤页）'; HP = '封面节页眉部件与后续各节不共用'
        ok('基准样张 表身不绑定、封面页眉部件独立通过', rows0.get(TB, (True,))[0] and rows0.get(HP, (False,))[0], str(rows0.get(TB)) + str(rows0.get(HP)))
        def f_tb(d):
            from docx.oxml import OxmlElement as OE
            t_ = next(t for t in d.tables if len(t.rows) > 2); t_.rows[1]._tr.get_or_add_trPr().append(OE('w:cantSplit'))
        mutate(base, tmp / 'tb.docx', f_tb); rows = check(repo, tmp / 'tb.docx', tmp / 'tb.md')
        ok('表身第 1 行加 cantSplit -> 表身不绑定项不通过', not rows[TB][0], str(rows.get(TB)))
        def f_tbk(d):
            t_ = next(t for t in d.tables if len(t.rows) > 2)
            for c_ in t_.rows[2].cells:
                for q_ in c_.paragraphs: q_.paragraph_format.keep_with_next = True
        mutate(base, tmp / 'tbk.docx', f_tbk); rows = check(repo, tmp / 'tbk.docx', tmp / 'tbk.md')
        ok('表身第 2 行加 keepNext -> 表身不绑定项不通过', not rows[TB][0], str(rows.get(TB)))
        def f_bodypg(d):
            from docx.oxml.ns import qn as Q
            d.sections[2]._sectPr.find(Q('w:pgNumType')).set(Q('w:start'), '2')
        mutate(base, tmp / 'bodypg.docx', f_bodypg); rows = check(repo, tmp / 'bodypg.docx', tmp / 'bodypg.md')
        ok('正文节 pgNumType start=2 -> 正文页码自1项不通过', not rows[BODYPG][0], str(rows.get(BODYPG)))
        def f_share(d):
            from docx.oxml.ns import qn as Q
            r0 = d.sections[0]._sectPr.find(Q('w:headerReference')); r1 = d.sections[1]._sectPr.find(Q('w:headerReference'))
            r0.set(Q('r:id'), r1.get(Q('r:id')))
        mutate(base, tmp / 'share.docx', f_share); rows = check(repo, tmp / 'share.docx', tmp / 'share.md')
        ok('封面节与目录节共用页眉部件 -> 部件不共用项不通过', not rows[HP][0], str(rows.get(HP)))
        src = repo / '上册-研究报告' / '01-智力即服务.md'; o1 = src.read_text('utf-8')
        try:
            src.write_text(o1 + '\n\n本章索引\n\n- [第一节](#x)\n', 'utf-8')
            r = build(repo, 'upper', tmp / 'idx.docx')
        finally: src.write_text(o1, 'utf-8')
        ok('书稿出现“本章索引” -> build_docx 退出 8 且不写出', r.returncode == 8 and '本章索引' in r.stdout and not (tmp / 'idx.docx').exists(), f'exit {r.returncode} ' + r.stdout[-200:])

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

        # 24. “见PDF第x—y页”作主页码、离散页码“3,6”无空格 -> validate-middle 报错
        lp = next((repo / '下册-案例汇编').glob('D-*/D02-*.md')); lsrc = lp.read_text('utf-8')
        try:
            u = 'https://example.com/a.pdf'
            extra = ('\n[3] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30)[2026-10-29]. 某某公司项目，见PDF第35—38页。'
                     '\n[4] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30): 3,6[2026-10-29].')
            new = lsrc.replace('(2026-03-30): 19-21[2026-10-29].', '(2026-03-30): 19-21[2026-10-29].' + extra)
            assert new != lsrc
            lp.write_text(new, 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'validate-middle.py')], cwd=repo, capture_output=True, text=True)
            errs = [e for e in json.loads(r.stdout)['errors'] if e.startswith('下册/')]
            ok('“见PDF第x—y页”作主页码 -> validate-middle 报错', r.returncode == 1 and any('[3]' in e and 'main page locator' in e for e in errs), str(errs)[-300:])
            ok('离散页码“3,6”缺空格 -> validate-middle 报错', r.returncode == 1 and any('[4]' in e and 'half-width ", "' in e for e in errs), str(errs)[-300:])
        finally:
            lp.write_text(lsrc, 'utf-8')

        # 25. 日期后裸写“第…项/部分” -> validate-middle 报错；“引用范围：第…项”不报
        lp = next((repo / '下册-案例汇编').glob('D-*/D02-*.md')); lsrc = lp.read_text('utf-8')
        try:
            u = 'https://example.com/a.pdf'
            extra = ('\n[3] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30)[2026-10-29]. 第十二、十三项。引用范围：某方向。'
                     '\n[4] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30)[2026-10-29]. 第二部分重点任务。引用范围：某方向。'
                     '\n[5] 甲. [乙](' + u + ')[EB/OL]. (2026-03-30)[2026-10-29]. 引用范围：第十二项某方向。')
            new = lsrc.replace('(2026-03-30): 19-21[2026-10-29].', '(2026-03-30): 19-21[2026-10-29].' + extra)
            assert new != lsrc
            lp.write_text(new, 'utf-8')
            r = subprocess.run([sys.executable, str(repo / 'scripts' / 'validate-middle.py')], cwd=repo, capture_output=True, text=True)
            errs = [e for e in json.loads(r.stdout)['errors'] if e.startswith('下册/')]
            ok('日期后裸写“第十二、十三项” -> validate-middle 报错', r.returncode == 1 and any('[3]' in e and 'clause locator' in e for e in errs), str(errs)[-300:])
            ok('日期后裸写“第二部分” -> validate-middle 报错', any('[4]' in e and 'clause locator' in e for e in errs), str(errs)[-300:])
            ok('“引用范围：第十二项” 不误报', not any('[5]' in e for e in errs), str(errs)[-300:])
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

        # 19. 失效锚点 / 失效文件链接 -> check-md-links 报错
        chk = REPO / 'scripts' / 'check-md-links.py'
        r = subprocess.run([sys.executable, str(chk), '--repo', str(repo)], capture_output=True, text=True)
        ok('check-md-links 仓库现状 0 处失效', r.returncode == 0, r.stdout[-300:])
        lk = repo / '索引' / '阅读路径.md'; lsrc0 = lk.read_text('utf-8')
        try:
            lk.write_text(lsrc0 + '\n\n[坏锚点](../上册-研究报告/01-智力即服务.md#section-1-99)\n[坏文件](../上册-研究报告/不存在.md)\n', 'utf-8')
            r = subprocess.run([sys.executable, str(chk), '--repo', str(repo)], capture_output=True, text=True)
        finally: lk.write_text(lsrc0, 'utf-8')
        ok('失效锚点、失效文件 -> check-md-links 退出 1 并列出', r.returncode == 1 and '#section-1-99' in r.stdout and '不存在.md' in r.stdout, r.stdout[-300:])
        # 20. 默认输出文件名
        od = tmp / 'outdef'; od.mkdir()
        r = subprocess.run([sys.executable, str(HERE / 'build_docx.py'), '--repo', str(repo), '--volume', 'upper', '--no-toc-pages'],
                           env=dict(os.environ, BOOK_REPO=str(repo), DOCX_OUT_DIR=str(od)), capture_output=True, text=True)
        names = sorted(x.name for x in od.glob('*.docx'))
        ok('不给 -o -> 默认输出 企业数智化转型思路-上册.docx，不含“样张”', r.returncode == 0 and names == ['企业数智化转型思路-上册.docx'], f'{names} {r.stderr[-200:]}')
        # 21–23. groups 配置防呆
        def bad_build(tag, mut):
            c = yaml.safe_load((HERE / 'style.yaml').read_text('utf-8')); mut(c['volumes']['lower'])
            st_ = tmp / f'style-{tag}.yaml'; st_.write_text(yaml.safe_dump(c, allow_unicode=True), 'utf-8')
            o = tmp / f'{tag}.docx'
            r_ = subprocess.run([sys.executable, str(HERE / 'build_docx.py'), '--style', str(st_), '--repo', str(repo), '--volume', 'lower', '--no-toc-pages', '-o', str(o)],
                                env=dict(os.environ, BOOK_REPO=str(repo)), capture_output=True, text=True)
            return r_.returncode, r_.stderr + r_.stdout, o.exists()
        single = next(c for c, g in cfg0['volumes']['lower']['groups'].items() if isinstance(g, str))
        sdir = cfg0['volumes']['lower']['groups'][single]
        rc, msg, ex = bad_build('dup', lambda v: v['groups'].__setitem__(mch, list(mdirs) + [mdirs[0]]))
        ok('同一目录在合并章里列两次 -> 报错退出', rc != 0 and '重复列出目录' in msg and not ex, msg[-200:])
        rc, msg, ex = bad_build('dup2', lambda v: v['groups'].__setitem__(mch, list(mdirs) + [sdir]))
        ok('同一目录分属两章 -> 报错退出', rc != 0 and '重复列出目录' in msg and not ex, msg[-200:])
        rc, msg, ex = bad_build('emptylist', lambda v: v['groups'].__setitem__(mch, []))
        ok('某章目录列表为空 -> 报错退出', rc != 0 and '没有列任何目录' in msg and not ex, msg[-200:])
        ed = repo / '下册-案例汇编' / 'Z-空门类'; ed.mkdir(); (ed / 'README.md').write_text('# 空门类\n', 'utf-8')
        try:
            rc, msg, ex = bad_build('emptydir', lambda v: v['groups'].__setitem__(mch, list(mdirs) + ['Z-空门类']))
            ok('目录里只有 README、没有篇目 -> 报错退出', rc != 0 and '没有可排的篇目' in msg and 'Z-空门类' in msg and not ex, msg[-200:])
        finally:
            shutil.rmtree(ed, ignore_errors=True)
        rc, msg, ex = bad_build('lead1', lambda v: v['group_leads'].__setitem__(sdir, '测试　单目录引导行'))
        ok('group_leads 配给单目录章 -> 报错退出', rc != 0 and '只能用于多目录章' in msg and sdir in msg and not ex, msg[-200:])

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
