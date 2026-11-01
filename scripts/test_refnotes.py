#!/usr/bin/env python3
"""refnotes.py（Word 与网页共用的参考文献条目注文判定）单元测试，及网页端渲染核对。

  1. 标题正则锚定整行：“## 资料来源分级”“## 2026-10-18 更新参考资料说明”、正文中含“参考文献”的行不算参考文献节
  2. 多段脚注（空行 + 缩进 4 格续段）保留分段；网页注文段间用 <br>
  3. 参考文献节内只有列表条目算条目：节内说明段落上的脚注保留为普通脚注
  4. 参考文献节到同级或更高一级标题为止；代码块内不算
用法：/workspace/venv-site/bin/python scripts/test_refnotes.py（无 markdown-it 时跳过网页部分并提示）
"""
import importlib.util, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import refnotes
fails = []
def ok(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f'  [{info}]' if info and not cond else ''))
    if not cond: fails.append(name)

SRC = """# 第一章

正文引用[^a]。

## 资料来源分级

[1] 不是参考文献节里的条目[^b]

## 2026-10-18 更新参考资料说明

[2] 也不是[^c]

本段提到参考文献[^d]，但不是标题。

## 7. 参考文献

以下说明段落带脚注[^e]，不是条目。

[1] 甲：《题名》，2024[^f]
[2] 乙：《题名》，2025[^g]
    懒续行

```
[3] 代码块里的[^h]
```

## 下一节

[4] 节已结束[^i]

[^a]: 正文注。
[^b]: 伪节注B。
[^c]: 伪节注C。
[^d]: d
[^e]: 说明段注。
[^f]: 第一段，
    续行。

    第二段。
[^g]: 单段。
[^h]: h
[^i]: i
"""
L = SRC.splitlines()
defs, used, plan = refnotes.plan(L)
labels = sorted(l for v in plan.values() for l in v)
ok('标题锚定：只有“## 7. 参考文献”成节，条目注文仅 f、g', labels == ['f', 'g'], labels)
for t, want in (('## 资料来源分级', False), ('## 2026-10-18 更新参考资料说明', False), ('本段提到参考文献', False),
                ('## 7. 参考文献', True), ('## 本章参考资料', True), ('# 参考文献 #', True), ('### 资料来源', True),
                ('## <a id="refs"></a>**参考文献**', True), ('## References', True), ('## 参考文献与延伸阅读', False)):
    ok(f'is_reference_heading({t!r}) == {want}', refnotes.is_reference_heading(t) == want)
ok('多段脚注保留分段：f 为两段', defs['f'] == ['第一段，续行。', '第二段。'], defs['f'])
ok('单段脚注：g 为一段', defs['g'] == ['单段。'], defs['g'])
ok('说明段落上的脚注 e 不改为条目注文', 'e' not in labels)
ok('代码块内与节外（同级标题后）的 h、i 不改', 'h' not in labels and 'i' not in labels)
ok('脚注定义行全部识别（9 条）', len(defs) == 9, sorted(defs))
ok('多段脚注 4 种情况之外：空行后非缩进行结束脚注', refnotes.parse_footnotes(['[^x]: a', '', 'b'])[0]['x'] == ['a'])

try:
    import markdown_it, mdit_py_plugins  # noqa
    spec = importlib.util.spec_from_file_location('build_site', HERE / 'build-site.py'); bs = importlib.util.module_from_spec(spec); spec.loader.exec_module(bs)
except ImportError:
    print('SKIP 网页部分：缺 markdown-it-py / mdit-py-plugins（用 /workspace/venv-site/bin/python 运行）'); bs = None
if bs:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'x.md'; p.write_text(SRC, 'utf-8')
        html = bs.render_document(p)
        html = html if isinstance(html, str) else html[0]
        import re
        spans = re.findall(r'<span class="ref-note"[^>]*>(.*?)</span>', html, re.S)
        ok('网页：条目注文 2 处（f、g）', len(spans) == 2, spans)
        ok('网页：多段注文段间保留 <br>', spans and re.sub(r'\s', '', spans[0]).startswith('第一段，续行。<br') and '第二段。' in spans[0], spans[:1])
        ok('网页：说明段注 e 仍在脚注列表', '说明段注。' in html and not any('说明段注' in s for s in spans))
        ok('网页：伪参考文献标题下的 b、c 仍为脚注', '伪节注B。' in html and '伪节注C。' in html and not any('伪节注' in s for s in spans))

print(f'\n共 {len(fails)} 项失败' if fails else '\n全部通过')
sys.exit(1 if fails else 0)
