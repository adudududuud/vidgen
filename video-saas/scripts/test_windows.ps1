$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
& .\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
if ($LASTEXITCODE -ne 0) { throw '测试依赖安装失败' }
& .\.venv\Scripts\python.exe -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw '自动化测试未通过' }
