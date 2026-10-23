$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
if (!(Test-Path '.venv\Scripts\python.exe')) { throw '运行环境不存在，请先执行 scripts\install_windows.ps1' }
if (!(Test-Path '.env')) { throw '.env 配置不存在，请先运行安装脚本' }
Write-Host '网页地址: http://127.0.0.1:8000' -ForegroundColor Green
Write-Host '管理后台: http://127.0.0.1:8000/admin' -ForegroundColor Green
Start-Process 'http://127.0.0.1:8000'
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
