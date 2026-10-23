# 源码核查与版本验证记录

## 上游项目

2026-10-23 通过 GitHub 连接核查了官方仓库 `yt-dlp/yt-dlp`：

- 克隆地址：https://github.com/yt-dlp/yt-dlp.git
- 默认分支：`master`
- 许可证：https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE （Unlicense）
- 官方嵌入接口：https://github.com/yt-dlp/yt-dlp?tab=readme-ov-file#embedding-yt-dlp
- 新版 YouTube/EJS 依赖：https://github.com/yt-dlp/yt-dlp/wiki/EJS

## 本地环境边界

本轮工作环境未进行真实媒体抓取、Windows D 盘安装或云服务器上线。项目的 Windows 安装脚本会在目标电脑具备网络时拉取上游 yt-dlp；Docker 镜像使用 PyPI 发布的 `yt-dlp[default]` 与 Node.js 22。

## V0.2 更新（2026-10-23）

- 新增可取消任务状态机与失败/取消任务重试接口。
- 新增管理后台按状态/来源 URL 搜索、分页、CSV 导出。
- 数据库初始化会为 V0.1 数据库补加 `cancel_requested` 字段。
- 18 项 pytest 自动化测试通过，`compileall` 通过，前端 JavaScript `node --check` 通过。
- 测试任务使用模拟文件，不代表真实视频源下载已通过。

## V0.3 工程更新（2026-10-23）

- 新增可选 Google OAuth/OIDC、用户任务历史、按账号额度及管理端用户停用。
- 增加 users 表和 jobs.user_id 的 SQLite 兼容迁移。
- OAuth 依赖列入 requirements；没有配置 Google Client ID/Secret 时功能保持关闭。
- Google Cloud Console 设置与真实回调流程需要使用运营者自己的凭据完成验收。
- 23 项 pytest 自动化测试通过；`compileall` 与前端 `node --check` 通过。
