# 影速 Windows 视频下载器 V1.0

> 这是 **Windows 桌面软件**，不是 SaaS。不会启动网页、FastAPI 或服务器，不需要账号、Google OAuth 或广告。

## 适合用户

- Windows 10/11 64 位
- 双击 `YingSuVideo-Setup-v1.0.exe` 安装
- 打开 **影速视频下载器**，粘贴有权使用的视频链接，选择保存位置和格式
- 支持 YouTube、抖音白名单 HTTPS 地址；是否成功取决于视频权限、网络环境及平台规则

## 最新版入口

- 源码位置：`desktop/`
- 构建脚本：`desktop/build_installer.ps1`
- GitHub Actions：`Actions > Build Windows Video Desktop Installer`
- 完成构建后在该运行页面的 **Artifacts** 下载 `YingSuVideo-Windows-Setup-v1.0`，解压得到安装程序 `.exe`
- 如果 Action 还没成功，请勿将仓库源码 ZIP 误认为 Windows EXE。

## 试验地址

`https://youtu.be/ixw8pLpXtYs`

程序有“填写测试链接”及“检测链接（不下载）”按钮。检测只读取媒体元信息，**不等于证明真实下载成功**。只有确认拥有必要权利/授权时才执行实际下载。

## 软件功能

1. 简体中文桌面窗口、粘贴链接
2. 一键检测链接（无媒体下载）
3. 下载为 MP4 720p、高清 MP4、最佳原始格式或 MP3
4. 选择 Windows 保存目录、下载进度、取消、打开文件夹
5. 临时任务目录隔离、避免覆盖同名文件
6. 打包 Node.js 22+、FFmpeg、yt-dlp 与 yt-dlp-ejs，不要求用户自行安装 Python 或 Node

**注意：** MP4 720p 模式优先使用单文件流以减少合并失败，视频真实分辨率取决于源站的可用格式。选择 MP3 时需要音视频转码。部分 YouTube 视频需要登录、地区授权或无公开可提取格式，工具不绕过 DRM 或平台访问控制。

## 开发和本地测试

Windows 上先安装 Python 3.12、Node.js 22，随后：

```powershell
cd <克隆仓库的目录>
py -3.12 -m pip install -r desktop\requirements.txt
py -3.12 -m pytest -q desktop\tests
py -3.12 -m desktop.gui
```

完整 EXE 安装程序必须在 Windows 上构建：

```powershell
powershell -ExecutionPolicy Bypass -File .\desktop\build_installer.ps1
```

输出在 `dist\installer\YingSuVideo-Setup-v1.0.exe`。CI 自动运行测试并在成功后上传安装包。

## 构建限制与开源组件

使用 yt-dlp（Unlicense）、Node.js、FFmpeg（可能涉及 LGPL/GPL 的二进制构建）、imageio-ffmpeg、PyInstaller 和 Inno Setup。分发前请核查对应版本的许可证及第三方组件声明；商业签名证书不包含在此项目中，Windows SmartScreen 可能提示未知发行者。

未经在 Windows 虚拟机/实体机启动安装包并完成真实链接下载验证前，本工程只能被视为“可构建桌面源码及 CI 工程”，不是已完成最终端到端验收的安装程序。
