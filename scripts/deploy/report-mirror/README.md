# 腾讯云报告镜像更新器

将公共仓库 `scottzx/ai-in-organization` 的 `main` 分支构建为静态站，发布到：

```text
https://www.dreammate.work/report/ai-transformation-2026/
```

这组文件只负责报告更新。当前使用现有官网域名的 `/report/` 入口，避免等待新子域名的 DNS 配置。安装者在该域名现有 Nginx 虚拟主机中添加独立 `location /report/`，通过 `alias /var/www/report.dreammate.work/` 提供文件，并允许跟随本目录内的软链；不改其他 URL 的处理规则。

`REPORT_SITE_URL` 可覆盖构建所用公开地址，service 已设置为上面的官网入口。将来绑定 `report.dreammate.work` 后，可以调整该环境变量；脚本默认地址为 `https://report.dreammate.work/ai-transformation-2026/`。缓存与发布的物理目录不随 URL 变化。

## 目录和权限

```text
/opt/ai-report-mirror/
  update.py              安装的更新器
  venv/                  预先安装的 Python 依赖
  cache/                 更新器自己创建的源码归档缓存和归属标记
  update.lock            flock 并发锁
/var/www/report.dreammate.work/
  releases/<完整 commit>/  完整、已校验的静态网站
  ai-transformation-2026 -> releases/<完整 commit>
```

使用独立系统用户 `reportmirror`，禁止 SSH 登录，不授予 sudo。只允许它写自己的工作目录和新报告站点目录；Nginx 工作进程需要目录遍历和文件读取权限。不要将用户工作区、现有站点目录或已有 Git 仓库放到缓存位置。预先存在但没有正确归属标记的缓存会导致更新停止，更新器不会自行重置或删除它。

## 首次安装与手动更新

以下由有权限的安装者在服务器执行。需要 curl、Python 3.10 及以上、`venv` 和 systemd，不需要 Git 或 GitHub token；先确认 Python 版本也满足仓库构建脚本。`markdown-it-py` 由安装者预装，定时任务不会安装或升级依赖。

```sh
useradd --system --user-group --home-dir /opt/ai-report-mirror --no-create-home --shell /usr/sbin/nologin reportmirror
install -d -m 0755 -o reportmirror -g reportmirror /opt/ai-report-mirror /var/www/report.dreammate.work
python3 -m venv /opt/ai-report-mirror/venv
/opt/ai-report-mirror/venv/bin/pip install 'markdown-it-py==4'
install -m 0644 scripts/deploy/report-mirror/update.py /opt/ai-report-mirror/update.py
runuser -u reportmirror -- env REPORT_SITE_URL=https://www.dreammate.work/report/ai-transformation-2026/ /opt/ai-report-mirror/venv/bin/python /opt/ai-report-mirror/update.py
```

先检查新目录中的软链和网站首页，再启用定时任务。构建器必须支持 `REPORT_SITE_URL` 环境变量，用于站点地图和规范链接。不要把已含其他内容的目录直接交给安装命令或递归修改其所有权。

## 定时更新

```sh
install -m 0644 scripts/deploy/report-mirror/report-mirror-update.service /etc/systemd/system/report-mirror-update.service
install -m 0644 scripts/deploy/report-mirror/report-mirror-update.timer /etc/systemd/system/report-mirror-update.timer
systemctl daemon-reload
systemctl enable --now report-mirror-update.timer
systemctl list-timers report-mirror-update.timer
journalctl -u report-mirror-update.service -n 40 --no-pager
```

开机两分钟后首次检查，随后在上次执行结束五分钟后再次检查。服务以 `reportmirror` 运行，systemd 也将可写位置限制在上述两个目录。也可随时由安装者运行 `systemctl start report-mirror-update.service` 触发检查。

## 更新与失败行为

每次通过 `api.github.com` 的公共分支引用 API 读取 `main` 的完整 commit SHA，仅当版本变化时从 `codeload.github.com/scottzx/ai-in-organization/tar.gz/<SHA>` 下载官方源码归档，不连接 `github.com`、不使用 token。curl 禁用用户配置，连接超时 10 秒、总超时 120 秒。API 限流或网络失败时保留线上版本，等待下次定时检查。

归档缓存带归属标记；下载通过临时文件完整落盘后才保存。解包前检查所有条目，只接受唯一顶层目录下的普通文件和目录，安全剥除该目录前缀，拒绝路径穿越、软/硬链接和特殊文件。源码解到站点根目录以外的独立临时目录，用当前虚拟环境的 Python 依次运行 `scripts/validate.py`、`scripts/validate-middle.py`、`scripts/build-site.py`。各个构建/校验命令均有 120 秒超时；锁被占用或 commit 未变化时跳过。

只有三步成功并生成首页后，才移动完整 `_site` 到新的 release，写入归属标记，并通过临时软链和 `os.replace` 原子切换访问入口。更新失败返回非零状态，保留当前线上软链。更新器不会 reset 用户仓库、删除不明文件或清理历史 release；磁盘空间由管理员定期检查。

release 标记同时记录构建 URL。若调整 `REPORT_SITE_URL`，请配合仓库的一个新 commit 重新构建；对于同一 commit 已存在但 URL 不同的 release，更新器会停止，避免复用旧的站点地图或覆盖不明目录。

日志只记录阶段、commit 简写和结果，不打印网络命令中的凭据或子命令输出。排查构建失败时，可在隔离的临时源码目录中，用同一虚拟环境手动运行对应校验命令；不要使用线上 release 作为构建工作区。
