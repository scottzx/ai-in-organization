# 报告网页维护说明

[国内在线阅读](https://www.dreammate.work/report/ai-transformation-2026/) · [GitHub Pages](https://scottzx.github.io/ai-in-organization/) · [返回仓库首页](../README.md)

网页直接从仓库现有Markdown生成。请在原章节或案例文件修改内容，不必再维护一份网页正文。上册章节、中册行业方案、附录、下册案例、公开索引与PDF发行说明都可直接阅读；过程稿与草稿箱不生成网页；正式内容不得链接到过程稿，草稿箱的既有引用保留为GitHub源文档链接。本地资料库与内部审读底稿保存在本机，不随公开书稿提交。

## 自动发布

推送到main分支后，GitHub Actions执行文档校验、生成静态网页并部署至GitHub Pages。也可以在Actions中的“Publish report website”手动运行。工作流见[pages.yml](../.github/workflows/pages.yml)。旧PDF通过GitHub历史归档查阅，不打包到当前站点；网页发布不重新编排PDF。

国内入口部署在现有腾讯云官网的 `/report/ai-transformation-2026/` 路径，复用官网域名和HTTPS证书，报告文件单独存放。专用系统用户每5分钟通过GitHub公共API检查main分支；有新版本时从官方codeload下载源码，校验、构建后原子切换，失败时保留上次成功版本。首次部署通过Tailscale上传，后续无需保持本机在线。服务配置与维护方法见[腾讯云报告镜像更新器](../scripts/deploy/report-mirror/README.md)。

仓库Pages的发布来源设置为GitHub Actions。每章保留独立网址、本页目录、相邻章节与分享按钮；全文搜索在浏览器本地完成，搜索内容从站点自身加载。

顶部切换上、中、下三册并标出当前册。左侧只显示当前册的章节、行业方案或分类案例，右侧按当前正文生成本页目录；全书首页与公共资料页显示全书入口。左侧目录独立滚动，联系电话与地址固定在侧栏底部，滚动正文或目录均可见。窄屏入口简写为“报告、方案、案例”，与搜索、目录按钮保持在同一行；手机窄屏保留品牌图标，通过“目录”展开左栏，联系信息保留在展开侧栏底部。

三册“本册总览”生成简洁导航页：上册列章节与附录，中册列引言、行业方案与附录，下册列行业分类及附编入口。目录与篇数从现有正文和案例索引生成；各册README中的完整说明保留在源文档中。

## 本地预览

安装依赖并运行：

```sh
python3 -m pip install -r scripts/requirements-site.txt
python3 scripts/validate.py
python3 scripts/validate-middle.py
python3 scripts/build-site.py
python3 -m http.server 8000 --directory _site
```

打开本机8000端口即可预览。构建器检查所有生成页面的站内链接、图片与锚点，输出目录`_site`不提交。首页案例与场景数从现有案例索引读取，版本文字从仓库首页读取；样式和阅读交互分别维护在[site.css](site.css)与[site.js](site.js)。

站内链接使用相对路径。默认构建以GitHub Pages为发布地址；其他域名和目录通过环境变量 `REPORT_SITE_URL` 指定规范链接和404返回入口，例如 `REPORT_SITE_URL=https://www.dreammate.work/report/ai-transformation-2026/ python3 scripts/build-site.py`。更换源码仓库时修改[构建器](../scripts/build-site.py)的REPO；新增公开入口时同步仓库首页和本说明。

中册目录、补充书目和新增案例的编辑配置位于[scripts/data/middle](../scripts/data/middle/README.md)。更新配置后可重新生成相应索引；日常网页发布使用仓库中的已成稿正文、索引和图片，不需要本地PDF全文或审读记录。
