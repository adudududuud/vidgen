# 影速 Windows 视频下载器 V1.1

Windows 10/11 x64 本地程序，不是 SaaS，不需要登录或服务器。

## 这次修复

- Windows DPI 感知在 Tk 启动前开启，改善 125%/150%/200% 缩放下的字形模糊。
- 界面采用可滚动自适应布局：底部任务状态不再被硬性裁切，窄窗口按钮分两排等宽显示。
- 优化下载格式下拉框清晰度，统一输入框与按钮高度。
- 新增智能兼容下载默认选项；只有格式不可用时才自动回退重试一次。
- 403/429/网络超时、来源站点登录与人机验证、DRM 等情况给出可理解的诊断提示，不绕过平台访问控制。

## Windows 安装包（由 GitHub Actions 自动构建）

1. 打开 https://github.com/adudududuud/vidgen/actions/workflows/video-desktop-windows.yml
2. 选择 `video-desktop-v1.1` 分支成功的运行，在 Artifacts 下载 `YingSuVideo-Windows-Setup-v1.1`。
3. 解压得到 `YingSuVideo-Setup-v1.1.exe`，双击安装，可以选择 `D:\AI\Youtube-抖音\video` 目录。
4. 用 `https://youtu.be/ixw8pLpXtYs` 先点「检测链接」，仅在有权下载时尝试下载。

只有 Actions 全部成功后才有有效 EXE；源码 ZIP 不是安装程序。

## 本地开发测试

```powershell
py -3.12 -m pip install -r desktop\requirements.txt
py -3.12 -m pytest -q desktop\tests
py -3.12 -m desktop.gui --gui-self-test
py -3.12 -m desktop.gui
powershell -ExecutionPolicy Bypass -File .\desktop\build_installer.ps1
```

源代码在 `desktop/`。打包使用 PyInstaller + Inno Setup（含 yt-dlp / Node.js / FFmpeg）。

## 注意

- 本地 Python 测试和 GUI 布局冒烟测试通过并不代表 Windows DPI 或视频真实性能已由用户电脑验证。
- 目标视频可能因登录/机器人验证或地区权限无法下载；不支持绕过登录、DRM、平台限制。
- 格式回退时可能输出真正可用的 WebM/MKV，而非强制标称 MP4。
- 软件仅供拥有相应权利且来源平台允许下载的素材。
- 安装包未经商业签名，Windows 可能提示未知发行者。
- V1.0 与之前 SaaS 代码不变，V1.1 为独立分支。
