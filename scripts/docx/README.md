# Word 导出与格式自检脚本

本目录存放 Word（docx）交付件的导出与自检脚本：

| 文件 | 作用 |
|---|---|
| `build_docx.py` | Markdown → docx 导出（扉页、版权页、目录、页眉页脚、章节重编号、图表编号） |
| `check_docx.py` | 读回 docx 逐项核对格式，可选同时检查导出的 PDF |
| `toc_fill.py` | 用 LibreOffice 回填目录页码（由 `build_docx.py` 自动调用） |
| `style.yaml` | 全部格式参数（字体、字号、行距、缩进、各册章号映射等） |
| `image-manifest.yaml` | 图片取舍清单（电子书保留 / 纸书重绘） |

## 环境要求

- Python 3，依赖：`python-docx`、`pyyaml`（`pip install python-docx pyyaml`）
- 可选：LibreOffice（`soffice`，用于预排目录页码和转 PDF）；`pdftotext`（poppler-utils，用于 `--pdf` 检查）
- 字体：仿宋_GB2312、楷体_GB2312、黑体需在排版/打开 Word 的机器上安装，脚本只在 docx 中写字体名，不引用本地字体路径。

## 路径约定

- 仓库根目录默认取本目录的上两级，可用 `--repo` 或环境变量 `BOOK_REPO` 覆盖。
- 输出默认写到仓库根目录的 `output/docx/`，可用 `-o` 或环境变量 `DOCX_OUT_DIR` 覆盖。该目录已写入 `.gitignore`，生成的 docx/pdf 不入库。

## 导出

```bash
cd scripts/docx
# 电子书版（参考文献只印题名，题名带超链接）
python3 build_docx.py --volume upper -o ../../output/docx/样张-上册.docx
# 印刷版（参考文献、注释、来源行在题名后补印网址）
python3 build_docx.py --volume upper --print -o ../../output/docx/样张-上册-印刷版.docx
# 或：BOOK_EDITION=print python3 build_docx.py ...
```

其他常用参数：`--volume middle`（中册）、`--only N`（只导出第 N 章）、`--no-toc-pages`（不预排目录，在 Word 中按 F9 更新）、`--allow-web-residue`（源稿残留网页导航行时临时放行出样张）。

## 格式自检

```bash
python3 check_docx.py ../../output/docx/样张-上册.docx -o ../../output/docx/检查清单-上册.md
# 同时检查 PDF（版本号、裸链、电子版不补印网址）
python3 check_docx.py 样张-上册.docx --pdf 样张-上册.pdf
# 印刷版 PDF：检查参考文献与来源行是否印出网址
python3 check_docx.py 样张-上册-印刷版.docx --print --pdf 样张-上册-印刷版.pdf
```

结果写入 `-o` 指定的检查清单（Markdown），开头给出“共 N 项，M 项不通过”。

## 格式规范摘要

- 一级标题：黑体三号；二级标题：楷体_GB2312 小三；三级标题：仿宋_GB2312 四号；四级标题：仿宋_GB2312 小四；全部标题加粗，标题不缩进。
- 正文：仿宋_GB2312 小四，固定行距 28 磅，段前段后 0，首行缩进 4 字符。
- 文字全部为黑色；图、表居中。
- 目录独立成页，每章另起一页。
- 标题层级：第一章、2.1、2.1.1 递进。
