# One-click source installer for Windows PowerShell 5.1/7
$ErrorActionPreference='Stop'
$target='D:\AI\Youtube-抖音\video'
Write-Host "[1/6] 安装目录: $target" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $target | Out-Null
$source=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($source -ne $target) {
  foreach($folder in @('app','static','deploy','scripts','docs','tests')) {
    Copy-Item -Path (Join-Path $source $folder) -Destination $target -Recurse -Force
  }
  foreach($item in @('requirements.txt','requirements-test.txt','.env.example','Dockerfile','compose.yaml','README.md','SOURCE_NOTES.md','CHANGELOG.md','.gitignore','install.cmd','start.cmd')) {
    Copy-Item -Path (Join-Path $source $item) -Destination $target -Force
  }
}
Set-Location $target
Write-Host '[2/6] 检查 Python/Git' -ForegroundColor Cyan
& python --version
if ($LASTEXITCODE -ne 0) { throw 'Python 未安装或未加入 PATH（建议 Python 3.12）' }
& git --version
if ($LASTEXITCODE -ne 0) { throw 'Git 未安装或未加入 PATH' }
Write-Host '[3/6] 拉取 yt-dlp 官方 GitHub 源码' -ForegroundColor Cyan
if (Test-Path (Join-Path $target 'yt-dlp\.git')) {
  & git -C (Join-Path $target 'yt-dlp') pull --ff-only
} else {
  & git clone --depth 1 https://github.com/yt-dlp/yt-dlp.git (Join-Path $target 'yt-dlp')
}
if ($LASTEXITCODE -ne 0) { throw 'GitHub 源码拉取失败，请检查网络或代理' }
Write-Host '[4/6] 创建 Python 独立运行环境' -ForegroundColor Cyan
if (!(Test-Path '.venv\Scripts\python.exe')) { & python -m venv .venv }
if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败' }
Write-Host '[5/6] 安装 yt-dlp 源码与网站依赖' -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw '安装网站依赖失败' }
& .\.venv\Scripts\python.exe -m pip install -e ".\yt-dlp[default]"
if ($LASTEXITCODE -ne 0) { throw '安装 yt-dlp 本地源码失败' }
$nodeMajor=0
try { $nodeVersion=(& node --version 2>$null); $nodeMajor=[int]($nodeVersion.TrimStart('v').Split('.')[0]) } catch {}
if ($nodeMajor -lt 22) {
  Write-Host '警告: 建议安装 Node.js 22+，否则 YouTube 部分视频无法解析。' -ForegroundColor Yellow
  Write-Host '可尝试: winget install --id OpenJS.NodeJS.LTS -e' -ForegroundColor Yellow
}
if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host '警告: 未检测到 FFmpeg；高画质音视频合并可能失败。' -ForegroundColor Yellow
  Write-Host '可尝试: winget install --id Gyan.FFmpeg -e' -ForegroundColor Yellow
}
if (!(Test-Path '.env')) {
  $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create()
  $bytes=New-Object byte[] 48
  $rng.GetBytes($bytes)
  $rng.Dispose()
  $secret=[Convert]::ToBase64String($bytes).Replace('+','x').Replace('/','y')
  $password=([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
  $envText=[System.IO.File]::ReadAllText((Join-Path $target '.env.example'))
  $envText=$envText.Replace('CHANGE_ME_TO_RANDOM_64_CHARACTERS',$secret).Replace('CHANGE_ME_TO_UNIQUE_LONG_ADMIN_PASSWORD',$password)
  [System.IO.File]::WriteAllText((Join-Path $target '.env'),$envText,(New-Object System.Text.UTF8Encoding($false)))
  Write-Host "首次管理员密码（保存后勿外传）: $password" -ForegroundColor Yellow
}
Write-Host '[6/6] 启动本地网站' -ForegroundColor Green
& (Join-Path $target 'scripts\run_windows.ps1')
