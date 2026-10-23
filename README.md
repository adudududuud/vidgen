# 影速 Video SaaS — V0.2 工程包

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 的简体中文视频素材处理 SaaS MVP。当前版本保留在 `video-saas-v0.2` 分支，不修改 `main` 分支。

## 下载与源码

- 完整工程 ZIP：`video-saas-MVP-v0.2.zip`
- 源码目录：`video-saas/`
- 详细安装、配置和部署说明：`video-saas/README.md`
- 更新记录：`video-saas/CHANGELOG.md`

## V0.2 新功能

- 取消排队/运行任务，重试失败或已取消的任务。
- 管理后台按任务状态筛选、按来源 URL 搜索、分页、CSV 导出。
- 管理统计增加已取消任务数。
- SQLite V0.1 数据库自动向后兼容迁移。
- 18 项自动化测试通过。

## Windows 安装

1. 下载并解压 ZIP。
2. 进入 `video-saas` 文件夹。
3. 双击 `install.cmd`，按提示完成安装。
4. 访问 `http://127.0.0.1:8000`；管理后台 `http://127.0.0.1:8000/admin`。

## 重要说明

- 仅处理用户拥有权利、获得授权或依法/依平台规则允许下载的内容。
- AdSense 默认关闭，必须自行完成 Google 账号配置、网站审核和政策核查。
- 当前环境只完成模拟任务自动化测试；真实视频下载、Windows D 盘安装、Docker 镜像和云服务器部署仍需实际验收。
- 这是一套持续开发中的 MVP，不是完成生产安全审计的正式商业服务。
