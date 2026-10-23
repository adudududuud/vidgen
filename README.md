# 影速 Video SaaS — V0.3 工程包

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 的简体中文视频素材处理 SaaS MVP。版本分别保存在 `video-saas-v0.1`、`video-saas-v0.2`、`video-saas-v0.3` 分支，不修改 `main` 分支。

## 当前版本 V0.3

- 可选 Google OpenID Connect 登录；未配置凭据时默认关闭。
- 登录用户可以查看自己的最近任务、取消/重试自己的任务、下载自己的完成文件。
- 登录用户按账号计算每日额度；匿名用户按 IP 摘要计算每日额度。
- 管理后台增加 Google 用户列表、账号启用/停用。
- 保留 V0.2 的任务取消/重试、状态筛选、来源链接搜索、分页与 CSV 导出。
- 自动迁移 V0.2 SQLite 数据库。

## 下载与源码

- 完整工程 ZIP：`video-saas-MVP-v0.3.zip`
- 源码目录：`video-saas/`
- 安装说明：`video-saas/README.md`
- 更新日志：`video-saas/CHANGELOG.md`

## Windows 安装

1. 下载并解压 ZIP。
2. 进入 `video-saas` 文件夹。
3. 双击 `install.cmd`，按提示完成安装。
4. 访问 `http://127.0.0.1:8000`；管理后台访问 `http://127.0.0.1:8000/admin`。

## Google 登录启用

请先在 Google Cloud Console 创建 OAuth 2.0 Web Client，并把 `https://你的域名/auth/google/callback` 加入授权重定向 URI。随后在服务器 `.env` 配置 `GOOGLE_CLIENT_ID`、`GOOGLE_CLIENT_SECRET`、`GOOGLE_REDIRECT_URI` 与 `SITE_URL`，再重启服务。不要把真实密钥提交到 GitHub。

## 重要说明

- 仅处理用户拥有权利、获得授权或依法/依平台规则允许下载的内容。
- AdSense 默认关闭；Google 登录、AdSense 审核与收费账户均需运营者自行配置。
- 23 项自动化测试通过；真实 Google OAuth 回调、真实视频下载、Windows D 盘安装及云服务器部署仍需实际验收。
- 这是一套持续开发中的 MVP，不是完成生产安全审计的正式商业服务。
