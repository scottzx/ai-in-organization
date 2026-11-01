# Word 导出与格式自检脚本

本目录存放 Word（docx）交付件的导出与自检脚本：

| 文件 | 作用 |
|---|---|
| `build_docx.py` | Markdown → docx 导出（扉页、版权页、目录、页眉页脚、章节重编号、图表编号） |
| `check_docx.py` | 读回 docx 逐项核对格式，可选同时检查导出的 PDF |
| `fonts_embed.py` | 把所用字体按 ECMA-376 混淆为 `.odttf` 嵌入 docx（由 `build_docx.py` 在回填目录后自动调用），并供 `check_docx.py` 核对 |
| `package_volumes.py` | 分册交付包：逐册导出（`--build`）上、中、下三册，PDF 实测页数，生成一页「索引说明」docx，四个文件打成一个 zip |
| `ref_notes_report.py` | 参考文献条目注文清单（供文字编辑核对），并核对 Word／网页注文与源稿一致 |
| `../refnotes.py` | Word 与网页共用的参考文献条目注文判定 |
| `toc_fill.py` | 用 LibreOffice 回填目录页码（由 `build_docx.py` 自动调用） |
| `style.yaml` | 全部格式参数（字体、字号、行距、缩进、各册章号映射等） |
| `image-manifest.yaml` | 图片取舍清单（电子书保留 / 纸书重绘） |

## 环境要求

- Python 3，依赖：`python-docx`、`pyyaml`、`fonttools`（`pip install python-docx pyyaml fonttools`）
- 可选：LibreOffice（`soffice`，用于预排目录页码和转 PDF）；`pdftotext`（poppler-utils，用于 `--pdf` 检查）
- 字体（Scott 2026-10-30 定，全部改用开源字体，SIL OFL 1.1）：思源黑体 Noto Sans SC（替代黑体）、思源宋体 Noto Serif SC（替代宋体）、霞鹜文楷 LXGW WenKai（替代楷体_GB2312）、朱雀仿宋 Zhuque Fangsong（替代仿宋_GB2312），西文 Source Serif 4。字号、行距、缩进不变。
- 字体文件：构建前先运行 `python3 fonts/fetch_fonts.py`，按固定 URL 下载中文字体并校验 sha256，放到 `fonts/cache/`（不入 git；Noto 可变字体自动生成静态 Regular/Bold）。Source Serif 4 已随仓库放在 `fonts/SourceSerif4/`。各字体授权原文在 `fonts/licenses/` 和 `fonts/SourceSerif4/LICENSE.md`。
- 字体嵌入：构建时按 `style.yaml` 的 `fonts.embed` 查找上述字体（`.ttf`/`.otf`，跳过 `.ttc` 和可变字体；也可用 `BOOK_FONT_DIR` 指定目录），按本书实际用字子集化后嵌入 docx，并打开 `embedTrueTypeFonts`、`saveSubsetFonts`。找不到的字体如实列出，不以其他字体替代，此时 `check_docx.py` 的“Word 嵌入字体”项不通过。子集只含本书已有的字，在 Word 中新增生僻字时可能回退到本机字体。
- 字号：图题、表题、表格文字均为五号（10.5pt），`check_docx.py` 逐段核对。

## 路径约定

- 仓库根目录默认取本目录的上两级，可用 `--repo` 或环境变量 `BOOK_REPO` 覆盖。
- 输出默认写到仓库根目录的 `output/docx/`，可用 `-o` 或环境变量 `DOCX_OUT_DIR` 覆盖。该目录已写入 `.gitignore`，生成的 docx/pdf 不入库。

## 导出

```bash
cd scripts/docx
# 电子书版（参考文献只印题名，题名带超链接）
python3 build_docx.py --volume upper -o ../../output/docx/企业数智化转型思路-上册.docx
# 印刷版（参考文献、注释、来源行在题名后补印网址）
python3 build_docx.py --volume upper --print -o ../../output/docx/企业数智化转型思路-上册-印刷版.docx
# 或：BOOK_EDITION=print python3 build_docx.py ...
```

四册均可导出：`--volume upper`（上册，第一至八章）、`--volume middle`（中册，第九至二十章）、`--volume lower`（下册，第二十一至三十章，篇目较多的行业门类各成一章，A、H、M、Q、S 五个门类合为第三十章“其他行业案例”（各门类前印加粗引导行，不编号），案例为 X.Y，附编A/B 为附录A/B）、`--volume all`（合订本，三册合排、一个目录，章号与各册单独导出时相同，附录字母全书连续：上册A、中册B/C、下册D/E）。配置见 `style.yaml` 的 `volumes`（`files` / `chapters` / `groups` / `include`；`groups` 的一章可列多个子目录，配 `group_leads` 印门类引导行）；下册 `front` 列册首不编号篇目（`00-导言.md`），排在第二十一章之前。

```bash
python3 build_docx.py --volume lower -o ../../output/docx/企业数智化转型思路-下册.docx
python3 build_docx.py --volume all -o ../../output/docx/企业数智化转型思路-合订本.docx
```

**下册不做导航页判定：** `style.yaml` 的 `exclude.nav_page_detect_exempt_dirs: [下册-案例汇编]` 使整个下册目录都不按“导航页”特征（短正文＋多链接）自动剔除，否则附编B 等短篇案例会被误删。下册各门类的 `README.md`（门类索引页）由文件名规则 `exclude.patterns` 中的 `README.md` 剔除，不靠导航页判定。因此，今后若在下册新增其他导航/索引页（文件名不是 `README.md`），构建不会自动识别，会当作案例排入正文；需改名为 `README.md`，或加入 `exclude.files`。

不给 `-o` 时按 `--volume` 自动命名，写到 `output/docx/`：`企业数智化转型思路-上册.docx`、`企业数智化转型思路-中册.docx`、`企业数智化转型思路-下册.docx`、`企业数智化转型思路-合订本.docx`（`--print` 时加“-印刷版”，如 `企业数智化转型思路-中册-印刷版.docx`），各册互不覆盖。

其他常用参数：`--only N`（只导出第 N 章）、`--no-toc-pages`（不预排目录，在 Word 中按 F9 更新）、`--allow-web-residue`（源稿残留网页导航行时临时放行出样张）。

## 分册交付（默认交付件）

Scott 2026-11-01 定：默认只交上、中、下三册，外加一页「索引说明」，打成一个 zip；合订本不再作为交付件（`--volume all` 仍可导出自查）。各册均按目录→正文→附录排。

```bash
python3 package_volumes.py --build -o ../../output/split-volumes   # 一次导出一册，三册依次导出后打包
python3 package_volumes.py -o ../../output/split-volumes           # 三册已导出时，只生成索引说明并打包
```

索引说明逐册列内容简介、页数（LibreOffice 渲染 PDF 后实测，含封面、版权页和目录）、章节范围和附录（从成品一级标题读出）；渲染不是 1 页即报错。配置见 `style.yaml` 的 `delivery`。

## 参考文献条目注文

参考文献条目上的脚注不再作为脚注，原注文以五号（10.5pt）黑色字接在条目后（多段注文保留分段）；正文脚注照常保留，Word 自动按剩余引用重排编号。判定由 `scripts/refnotes.py` 统一给出，`build_docx.py` 与 `scripts/build-site.py` 共用：只认整行为“参考文献／参考资料／资料来源”等的标题行，节到同级或更高一级标题为止，节内只有列表条目（`[n]`、`1.`、`-` 开头）算条目。单元测试：`/workspace/venv-site/bin/python ../test_refnotes.py`（需 markdown-it-py、mdit-py-plugins）。

```bash
python3 ref_notes_report.py --docx upper=…上册.docx middle=…中册.docx lower=…下册.docx --site ../../_site -o ref-notes-list.md
```

## 格式自检

```bash
python3 check_docx.py ../../output/docx/企业数智化转型思路-上册.docx -o ../../output/docx/检查清单-上册.md
# 同时检查 PDF（版本号、裸链、电子版不补印网址）
python3 check_docx.py 企业数智化转型思路-上册.docx --pdf 企业数智化转型思路-上册.pdf
# 印刷版 PDF：检查参考文献与来源行是否印出网址
python3 check_docx.py 企业数智化转型思路-上册-印刷版.docx --print --pdf 企业数智化转型思路-上册-印刷版.pdf
```

结果写入 `-o` 指定的检查清单（Markdown），开头给出“共 N 项，M 项不通过”。

**版权页网址放行（总编辑定）：** “PDF 正文无裸链”一项把版权页列为允许出现网址的范围，CC 许可协议网址和项目仓库地址不算裸链。PDF 某页只要含 `style.yaml` 中 `checks.copyright_page_markers` 列出的任一标记（默认：版权页（含“版权页”标题）、版权所有、著作权人；单独出现的“CC BY”“知识共享”不算标记，避免中册附录B 图源索引表等正文页被误放行），就按版权页处理，该页网址放行，清单里会注明放行处数。其他页出现的裸链仍判为不通过。

## 格式规范摘要

- 一级标题：黑体三号；二级标题：楷体_GB2312 小三；三级标题：仿宋_GB2312 四号；四级标题：仿宋_GB2312 小四；全部标题加粗，标题不缩进。
- 正文：仿宋_GB2312 小四，固定行距 28 磅，段前段后 0，首行缩进 2 个中文字符（＝4 个英文字符，firstLineChars=200，小四时 24 磅）；标题不缩进。
- 表格文字：五号，单倍行距（w:line=240、lineRule=auto），段前段后 0（Scott 2026-11-01）；正文仍为固定 28 磅。
- 参考文献条目注文：五号，不加粗，黑色，接在条目后。
- 文字全部为黑色；图、表居中。
- 目录独立成页，每章另起一页。
- 标题层级：第一章、2.1、2.1.1 递进。
