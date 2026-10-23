# 源码核查与限制

2026-10-23 通过 GitHub 连接核查了官方仓库 `yt-dlp/yt-dlp`：

- 克隆地址：https://github.com/yt-dlp/yt-dlp.git
- 默认分支：`master`
- 许可证：https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE （Unlicense）
- 官方嵌入接口：https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#embedding-yt-dlp
- 新版 YouTube/EJS 依赖：https://github.com/yt-dlp/yt-dlp/wiki/EJS

当前打包环境无法解析 github.com，所以**压缩包不包含 yt-dlp 原仓库源码**。`install.cmd` / `scripts/install_windows.ps1` 在您的 Windows 电脑上执行 `git clone` 到指定 D 盘目录。Docker 使用 PyPI 发布的 `yt-dlp[default]` 与 Node.js 22，不以 GitHub 源码副本构建。

本轮完成 15 个离线自动化测试，另完成独立本机 HTTP 首页/管理/健康接口烟雾测试；未测试任何真实媒体抓取、Windows D 盘安装或云服务器上线。
