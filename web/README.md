# 报告网页维护说明

[在线阅读与分享](https://scottzx.github.io/ai-in-organization/) · [返回仓库首页](../README.md)

网页直接从仓库现有Markdown生成。请在原章节或案例文件修改内容，不必再维护一份网页正文。上册章节、附录、下册案例、公开索引与PDF发行说明都可直接阅读；草稿箱与本地资料库不生成网页，其已有引用保留为GitHub源文档链接。

## 自动发布

推送到main分支后，GitHub Actions执行文档校验、生成静态网页并部署至GitHub Pages。也可以在Actions中的“Publish report website”手动运行。工作流见[pages.yml](../.github/workflows/pages.yml)。PDF沿用仓库现有文件，网页发布不重新编排PDF。

仓库Pages的发布来源设置为GitHub Actions。每章保留独立网址、本页目录、相邻章节与分享按钮；全文搜索在浏览器本地完成，搜索内容从站点自身加载。

## 本地预览

安装依赖并运行：

```sh
python3 -m pip install -r scripts/requirements-site.txt
python3 scripts/validate.py
python3 scripts/build-site.py
python3 -m http.server 8000 --directory _site
```

打开本机8000端口即可预览。构建器检查所有生成页面的站内链接、图片与锚点，输出目录`_site`不提交。首页案例与场景数从现有案例索引读取，版本文字从仓库首页读取；样式和阅读交互分别维护在[site.css](site.css)与[site.js](site.js)。

发布地址采用GitHub项目路径，站内链接使用相对路径，无需单独配置根路径。更换GitHub仓库或域名时，同步修改[构建器](../scripts/build-site.py)内的REPO与SITE常量、仓库首页和本说明中的公开链接。
