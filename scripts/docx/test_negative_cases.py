#!/usr/bin/env python3
"""反例测试：确认排版脚本对以下错误会报错（全部在临时目录里做，不改仓库源稿、不写 output/）。

  1. front 篇目以外出现“表导-N”          -> check_docx 题注编号项不通过
  2. 不编号篇目（label 0，如 09-结语）含图表 -> build_docx 退出 5（否则会生成“图 0-N”）
  3. 只传入册首 front 篇目给 check-case-structure -> 打印跳过提示、结果通过
  4. 附录内题注字母与本附录字母不一致（附录A 内“表 B-1”）、附录外用字母 -> 题注编号项不通过；附录A 内“表 A-1”通过

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

def build(repo, vol, out):
    env = dict(os.environ, BOOK_REPO=str(repo))
    return subprocess.run([sys.executable, str(HERE / 'build_docx.py'), '--repo', str(repo), '--volume', vol, '--no-toc-pages', '-o', str(out)],
                          env=env, capture_output=True, text=True)

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
        end.write_text(orig + '\n\n| a | b |\n|---|---|\n| 1 | 2 |\n', 'utf-8')
        r = build(repo, 'upper', tmp / 'l0.docx')
        ok('不编号篇目含表 -> build_docx 退出 5', r.returncode == 5 and '不编号篇目含表' in r.stdout + r.stderr, f'exit {r.returncode}')
        end.write_text(orig, 'utf-8')

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
