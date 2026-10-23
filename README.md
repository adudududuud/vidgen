# 影速 Video SaaS — V0.1 工程包

这是基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 的中文视频处理 SaaS MVP 工程包，作为**独立备份分支**存放，不影响 `vidgen` 主分支。

## 下载

点击此目录中的 **video-saas-MVP-v0.1.zip**，然后点击 **Download raw file** 下载完整工程包。

原始压缩包校验值：
```
SHA-256  8414e8e4ace1baf89f5129b0cea678e391b1fcef02354460419199ebb3c27fd3
```

## Windows 本地安装

1. 下载并解压 ZIP 到 `D:\AI\Youtube-抖音\video\`
2. 进入 `video-saas` 文件夹
3. 运行 `install.cmd`（需要 Python 和 Git，建议 Node.js、FFmpeg）
4. 启动后访问 `http://127.0.0.1:8000`，后台访问 `http://127.0.0.1:8000/admin`

请先阅读压缩包中的 `README.md` 与 `docs/上线验收清单.md`。

## 注意

- 这是 **V0.1 MVP 源码包**，并非经生产安全审计的商业成品。
- 真实视频下载、Docker 镜像和云服务器部署还需在具备相应网络与环境的机器上实测。
- 下载应限定为拥有权利或许可的内容，遵守平台服务条款、版权规定及 Google 广告政策。
- 本仓库不包含 yt-dlp 上游源码；Windows 安装脚本在具备网络时拉取它。
