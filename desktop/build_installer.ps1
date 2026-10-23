$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root

Write-Host 'Installing Windows build dependencies...'
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
python -m pip install -r desktop\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
python -m pytest -q desktop\tests
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }

$bin = Join-Path $root 'desktop\build-tools\bin'
New-Item -ItemType Directory -Force -Path $bin | Out-Null
$ffmpeg = (python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())').Trim()
if (-not (Test-Path $ffmpeg)) { throw "Cannot find FFmpeg: $ffmpeg" }
Copy-Item $ffmpeg (Join-Path $bin 'ffmpeg.exe') -Force
$node = (node -p 'process.execPath').Trim()
if (-not (Test-Path $node)) { throw "Cannot find Node.js 22+: $node" }
Copy-Item $node (Join-Path $bin 'node.exe') -Force
& (Join-Path $bin 'node.exe') --version
& (Join-Path $bin 'ffmpeg.exe') -version | Select-Object -First 1

python -m PyInstaller --clean --noconfirm --windowed --onedir `
  --name 'YingSuVideo' `
  --collect-all 'yt_dlp' `
  --collect-all 'yt_dlp_ejs' `
  --paths "$root" `
  --add-binary "$bin\node.exe;bin" `
  --add-binary "$bin\ffmpeg.exe;bin" `
  --distpath (Join-Path $root 'dist') `
  --workpath (Join-Path $root 'build') `
  --specpath (Join-Path $root 'build') `
  desktop\gui.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
$exe = Join-Path $root 'dist\YingSuVideo\YingSuVideo.exe'
if (-not (Test-Path $exe)) { throw "No packaged exe found: $exe" }
Write-Host "GUI EXE packaged: $exe"
& $exe --self-test
if ($LASTEXITCODE -ne 0) { throw 'Packaged EXE dependency smoke-test failed' }

$iscc = [Environment]::ExpandEnvironmentVariables('%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe')
if (-not (Test-Path $iscc)) {
    choco install innosetup -y --no-progress
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup installation failed' }
}
& $iscc 'desktop\installer.iss'
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup packaging failed' }
$setup = Join-Path $root 'dist\installer\YingSuVideo-Setup-v1.0.exe'
if (-not (Test-Path $setup)) { throw "No installer was generated: $setup" }
Write-Host "Windows installer created: $setup"
Get-FileHash -Algorithm SHA256 $setup
