# 影速 Video SaaS MVP V0.2（简体中文）

> 一个基于官方 **yt-dlp** 的中文视频素材处理站点。仅供自有、已授权或法律与来源平台明确允许的视频下载。默认关闭广告。

## 完成范围

- 响应式中文前端：粘贴链接、授权确认、后台任务进度、文件下载、使用条款和隐私页面
- FastAPI 后端：HTTPS 与来源域名白名单、任务队列、单 IP 免费限额、SQLite 持久化、短期文件缓存、随机任务令牌
- 管理后台：密码登录、摘要统计、任务搜索/状态筛选、分页、CSV 导出、删除已完成任务
- V0.2：用户可取消排队/运行中的任务、重试失败或已取消的任务；任务取消请求在 SQLite 中持久化，运行中的下载器通过进度钩子检查取消状态
- V0.2：兼容 V0.1 SQLite 数据库自动迁移，管理统计新增已取消任务数；健康检查返回版本号
- AdSense 广告脚手架（**默认关闭**，需要 Google 审批及政策合规评估）
- Windows 原始 yt-dlp 源码拉取安装、测试脚本、Docker / Caddy / HTTPS 部署配置

## 一、Windows 安装至指定路径

建议 Windows 10/11，Python 3.12、Git、FFmpeg，及 Node.js 22+（当前 YouTube EJS 解析依赖）。`yt-dlp` 源码由安装脚本 `git clone` 到 `D:\AI\Youtube-抖音\video\yt-dlp`。若本机无 FFmpeg，下载合并的部分格式可能失败。若无 Node.js 22+，YouTube 的 EJS 解析能力可能受限。安装脚本会检测并提示。

1. 将 ZIP 解压到任意临时目录。
2. **双击 `install.cmd` 即可安装并打开网页**，不熟悉 PowerShell 的用户采用此方法。
3. 如需手动执行，在 PowerShell 中进入解压目录后输入：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows.ps1
```

脚本会：复制站点到 `D:\AI\Youtube-抖音\video`、拉取 yt-dlp、创建 `.venv`、安装依赖、随机生成 `.env` 中的管理员密码和安全密钥、打开本地站点。请保存 PowerShell 首次显示的管理员密码。

后续双击目标目录内的 `start.cmd`，或手动再次启动：

```powershell
cd 'D:\AI\Youtube-抖音\video'
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1
```

网站：http://127.0.0.1:8000 ；管理后台：http://127.0.0.1:8000/admin

运行测试：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\test_windows.ps1
```

**注意**：本地没有互联网访问 yt-dlp 实际媒体接口时，不能进行真实视频下载测试。各平台的实际能力取决于当时的规则和提取器兼容性。

## 二、Linux 服务器（Ubuntu + Docker Compose）

准备域名、DNS A 记录、云安全组 TCP 80/443、已安装 Docker Engine + Compose 插件的云服务器，在代码目录执行：

```bash
cp .env.example .env
# 编辑 .env：APP_SECRET/ADMIN_PASSWORD 必须换成高熵随机值；SITE_URL=https://你的域名；DOMAIN=你的域名
# 先本地检查
sudo docker compose up -d --build app
curl -fsS http://127.0.0.1:8000/healthz
# 域名 DNS 解析就绪后再启用 Caddy 自动 HTTPS
sudo docker compose --profile production up -d --build
```

Docker 数据与临时媒体默认放在命名卷 `app_data` / `app_downloads`，请规划备份和容量告警。Docker 镜像带 Node.js 22 和 FFmpeg，同时安装 `yt-dlp[default]` 中的 EJS 脚本。

`.env` 文件权限应限制为 `chmod 600 .env`，不可纳入版本控制。Caddy 自动申请证书需要公网 DNS 解析正确并开放 80/443。不要开放 FastAPI 8000 到公网；Compose 默认仅绑定本机 127.0.0.1。

**必须先完成上线加固**：针对容器设置禁止访问内网、云元数据地址、回环、链路本地的网络出口策略，评估 DNS 重绑定和第三方视频重定向风险，完善分布式限流及恶意任务预防措施。仅靠应用层 HTTPS/域名白名单不足以防 SSRF。建议每个任务在隔离容器内运行且设置独立 CPU、磁盘、时间和网络配额。这个 MVP 暂未实现企业级任务隔离，不宜未经加固就向大量匿名用户开放。

## 三、广告与收费

默认 `ADSENSE_ENABLED=false`。运营者需拥有合法内容权利、符合服务平台条款、拥有自己的广告帐号且通过 Google 审核。仅在网站和实际业务符合 [Google Publisher Policies](https://support.google.com/adsense/answer/10502938?hl=zh-Hans) 时配置：

```dotenv
ADSENSE_ENABLED=true
ADSENSE_CLIENT=ca-pub-你的发布商数字ID
ADSENSE_SLOT=你的广告单元数字ID
```

本系统仅预留 AdSense 脚本与 `ads.txt`，不提供 Google 账户开户、网站审核或广告收益保证。Google 政策明确禁止协助下载内容平台禁止下载的流媒体视频的广告页面，所以**不要以未经授权的视频下载为广告变现对象**。

## 四、V0.2 更新说明

- 新增 `POST /api/jobs/{job_id}/cancel` 与 `POST /api/jobs/{job_id}/retry`，仍须提供任务访问令牌并再次确认素材授权。
- 管理接口支持 `status`、`q`、`limit`、`offset` 查询参数；CSV 导出仅管理员可访问。
- 增加 `cancel_requested` 字段的向后兼容迁移；被取消的排队任务不能再被 worker 领取。
- 新增取消、重试、后台筛选与 CSV 导出自动化测试。

## 五、限制与下一版建议

本版本是**单实例/单进程测试 MVP**，无普通用户账号、支付、Google OAuth、真正生产级速率限制、投诉工单、分布式队列、广告同意管理、多租户、计费、运营报表。任务执行使用线程池，重启时未完成任务标记为失败。文件按配置在下次启动/提交时清除，非严格准点删除。管理后台使用单一管理员密码和签名 Cookie，请务必在 HTTPS 下使用。

受保护的视频、DRM、需要登录/Cookie 的内容不在本项目支持承诺内。部署服务还应核查业务所在法域的网络、版权、个人信息和商业运营要求。

版本：0.2.0，方案与代码可供二次开发。原始 yt-dlp 许可证为 Unlicense（`https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE`）。
