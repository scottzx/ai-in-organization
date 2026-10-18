# 中册编写配置

本目录保存公开书稿的章节范围、补充来源元数据和新增案例条目，供编辑脚本复用。企业过程见[下册](../../../下册-案例汇编/README.md)，行业正文见[中册](../../../中册-行业解决方案/README.md)。来源的公开链接、页码和校验值用于回查，原PDF全文按原发布者链接查阅。

维护对应配置后，在仓库根目录按需运行：

```sh
python3 scripts/merge-middle-cases.py
python3 scripts/build-middle-sources.py
python3 scripts/build-middle-index.py
python3 scripts/validate.py
python3 scripts/validate-middle.py
python3 scripts/build-site.py
```

新增案例使用稳定编号，已经登记的条目有差异时合并脚本会停止，以免覆盖现有记录。补充书目只列既有行业资料库之外的来源。核验输出保存在已忽略的本地研究记录目录。

原图已经随书稿提供。需要重新渲染时，按行业资料索引取得相同版本的本地PDF，安装Poppler后运行 `python3 scripts/extract-middle-figures.py`；该步骤不属于日常网页发布。逐图来源与版本记录见[中册原图来源](../../../中册-行业解决方案/assets/README.md)。

需要减少页面留白时，安装可选依赖`pdfplumber`，运行 `python3 scripts/extract-middle-figures.py --sources A11 B02 --industries 工程机械 --trim-margins`。脚本定位源PDF的内嵌图形或可见元素边界，保留安全边距；满版内容不强行裁切。裁切框、检测方式、显示倍率和校验值写入来源记录，重建时沿用已确认的裁切范围。裁切后检查图内文字、边框及连线，图题、来源与必要脚注在正文完整保留。
