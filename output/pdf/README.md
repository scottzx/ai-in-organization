# PDF生成说明

成品PDF在交付时由`scripts/build-pdf.py`根据当前Markdown现场生成，不随仓库保存；本目录下的`*.pdf`及构建清单、检查记录等`*.json`均已加入`.gitignore`。此前提交的PDF已从仓库移除，如需回查可从Git历史获取。现行书稿以[在线阅读版](https://research.dreammate.work/report/ai-transformation-2026/)、[GitHub Pages备用入口](https://scottzx.github.io/ai-in-organization/)及各册Markdown为准，采用[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)许可。

## 生成方法

生成器覆盖上、中、下三册。`--volume upper`、`--volume middle`、`--volume lower`分别导出单册，默认`--volume all`按上、中、下顺序生成三册合订本。每次生成会在同目录写出构建清单（`*.manifest.json`），记录源文档SHA256、章节起页、字体配置、图表标题、PDF校验值和内容检查结果。

先维护Markdown正文，再用[`scripts/requirements-pdf.txt`](../../scripts/requirements-pdf.txt)安装Python依赖（`python3 -m pip install -r scripts/requirements-pdf.txt`）后运行生成器；另需Pandoc。交付环境须锁定ReportLab 5.1.0，更换版本可能改变分页与页码。渲染检查使用Poppler的`pdftoppm`、`pdftotext`及`pdfinfo`。

```bash
python3 scripts/build-pdf.py --volume upper --output output/pdf/企业数智化转型研究报告-上册.pdf
python3 scripts/build-pdf.py --volume middle --output output/pdf/企业数智化转型研究报告-中册.pdf
python3 scripts/build-pdf.py --volume lower --output output/pdf/企业数智化转型研究报告-下册.pdf
python3 scripts/build-pdf.py --volume all --output output/pdf/企业数智化转型研究报告-上中下册合订本.pdf
python3 scripts/validate.py
```

生成器仍支持`--chapter`单章导出，例如`python3 scripts/build-pdf.py --chapter 上册-研究报告/02-MTL-从市场到有效线索.md`。其他环境可通过`BOOK_BODY_FONT`、`BOOK_HEADING_FONT`、`BOOK_KAI_FONT`、`BOOK_DIAGRAM_FONT`与`BOOK_DIAGRAM_HEADING_FONT`指定覆盖中文的TrueType字体；不同字体可能改变分页，应重新检查并更新页数。

## 排版设计

A4竖版。正文小四（12磅），固定行距28磅，段前、段后0磅，首行缩进两个汉字并两端对齐。一级标题三号（16磅），二级标题小三（15磅），三级标题四号（14磅），四级标题小四（12磅）；标题均为28磅行距、段前后0磅。表格统一五号（10.5磅）、17磅行距，来源注释9磅、16磅行距。

生成器默认字体配置：正文为WPS仿宋，一级标题与强调文字为系统黑体，二级标题为楷体，插图为简体中文黑体。具体字体文件、TTC索引、字号及行距保存在各构建清单中。

正文强调使用纯黑色黑体；项目符号与编号条目的首行同样缩进24磅。链接与配图采用蓝色主调（#1D4ED8），表头为蓝底（#3D73C6）白字，表格隔行使用浅蓝底。

表格与图表段前、段后均为6磅。合订本71张表格统一在上方显示加粗表题，跨页重复表题和表头；名称维护在[表题清单](../../scripts/pdf-table-captions.json)。13张MTL插图和1张知识网络矢量图的图题在下方居中，并随图整体分页。SVG插图内的主标题移为外部图题，原图稿保持原样；优先保留矢量图形与可检索文字。

封面单独设置字号，且不显示页眉页脚。页眉显示报告名与当前章节，页脚居中显示页码。前置页使用罗马页码；上册和合订本从导论开始第1页，下册单独版从下册索引开始第1页。目录列出上册章、节及下册行业、案例，书签保留进一步阅读入口。
