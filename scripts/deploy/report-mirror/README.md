# GitHub Actions 静态报告镜像发布

公开入口：<https://www.dreammate.work/report/ai-transformation-2026/>。

GitHub Actions 在仓库更新后完成校验和静态构建，通过报告发布专用 SSH 密钥，将完整 `_site` 打包传给腾讯云的 `receive.py`。服务器只接收静态成品并原子发布，不访问 GitHub、不安装构建依赖、不定时拉取源码。

## 服务器文件和权限

```text
/opt/ai-report-mirror/
  receive.py             root 安装的接收器，运行用户不可修改
  receive.lock           reportmirror 可写的并发锁
  .ssh/authorized_keys   仅报告发布专用公钥，restrict + forced command
/var/www/report.dreammate.work/
  releases/<完整 SHA>/    完整静态站和接收器生成的完成标记
  ai-transformation-2026 -> releases/<完整 SHA>
```

接收器只依赖标准库 Python 3.11。使用已有的独立用户 `reportmirror`，不授予 sudo，不授予其他网站目录的写入权限。SSH 为执行 forced command 需要该用户使用 `/bin/sh`；专用公钥必须包含以下限制，禁止它执行自选 shell 命令、分配终端或转发连接：

```text
restrict,command="/usr/bin/python3 -I /opt/ai-report-mirror/receive.py" ssh-ed25519 <报告发布专用公钥> report-publish
```

`/opt/ai-report-mirror`、`receive.py` 和公钥配置由 root 管理。预先创建 `receive.lock`，允许 `reportmirror` 读写；报告 public 根目录和 `releases` 允许 `reportmirror` 写入、Nginx 读取。公钥目录与文件需满足 sshd 的读取与 StrictModes 权限要求；固定 forced command 的配置不可由发布用户修改。私钥仅用于报告发布，存入 GitHub Actions 的专用 secret，不能复用个人 SSH 密钥或服务器管理密钥。

例如，由管理员完成接收器及锁文件的首次安装（部署前确认 Python 版本）：

```sh
install -d -m 0755 -o root -g root /opt/ai-report-mirror
install -m 0644 -o root -g root scripts/deploy/report-mirror/receive.py /opt/ai-report-mirror/receive.py
install -m 0600 -o reportmirror -g reportmirror /dev/null /opt/ai-report-mirror/receive.lock
```

之后不应在发布执行期间替换锁文件。不要递归修改其他站点或已有不明目录的所有权。

## Actions 发送协议

工作流由仓库的 `.github/workflows/` 管理。发送前依次运行通用校验、中册校验和静态构建；构建时设置：

```text
REPORT_SITE_URL=https://www.dreammate.work/report/ai-transformation-2026/
```

将 `_site` 本身的内容打包，不添加额外顶层目录。标准 tar 产生的 `./` 路径可用：

```sh
tar -czf report-site.tar.gz -C _site .
ssh -i <报告发布专用私钥> -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes reportmirror@<服务器地址> "publish <40位小写完整commit SHA>" < report-site.tar.gz
```

工作流应固定服务器 host key，并通过 Actions 的发布并发组串行执行；不要关闭 host key 校验。服务端只接受完全匹配 `publish <40位小写SHA>` 的 `SSH_ORIGINAL_COMMAND`，不会执行任何传入命令。

## 接收与原子发布

接收器持有 `receive.lock` 后，将 stdin 完整保存到 `releases/.incoming-...` 内，只接受 gzip tar。压缩输入和解压后的文件内容分别最多 1 GiB，文件与目录条目合计最多 10,000，tar 元数据与填充也有额外硬上限。路径必须相对；拒绝绝对路径、`..`、重复路径、软硬链接、稀疏文件和其他特殊文件，拒绝上传接收器专用完成标记。

解包后要求非空 `index.html` 和非空对象/数组格式的合法 `search-index.json`。接收器自行写入 `.report-mirror-release.json`，记录仓库、完整 SHA 和固定公开 URL；文件统一为 0644，目录为 0755。只有全部成功后，才将完整目录移到 `releases/<SHA>`，用临时软链和 `os.replace` 原子切换公开入口。

同 SHA 已存在时，只接受完成标记匹配的 release，并仍完整消费和校验上传内容，再幂等发布；不覆盖不明目录。失败返回非零状态并保留线上版本。历史 release 不自动删除，可由管理员核查后处理。日志仅记录固定诊断和 SHA，不打印传入命令、密钥或归档内容。

## Nginx 入口

保留的 `nginx-www-location.conf` 应包含在现有 `www.dreammate.work` 的 HTTPS server 中。它仅为 `/report/` 添加独立 alias，静态文件仍在 `/var/www/report.dreammate.work`，不覆盖官网其他内容。管理员修改后先执行 `nginx -t`，再平滑重载。
