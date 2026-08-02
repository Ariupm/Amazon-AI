$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "未找到 $Name。请先安装：$InstallHint"
    }
}

Require-Command "node" "Node.js 22.13 或更高版本：https://nodejs.org/"
Require-Command "npm.cmd" "Node.js 22.13 或更高版本：https://nodejs.org/"
Require-Command "python" "Python 3.10 或更高版本：https://www.python.org/downloads/"

$nodeVersion = [version]((node --version).TrimStart('v'))
if ($nodeVersion -lt [version]"22.13.0") {
    throw "Node.js 版本过低：$nodeVersion。需要 22.13.0 或更高版本。"
}

$pythonVersionText = python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
$pythonVersion = [version]$pythonVersionText
if ($pythonVersion -lt [version]"3.10.0") {
    throw "Python 版本过低：$pythonVersion。需要 3.10 或更高版本。"
}

$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
)
if (-not ($chromePaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1)) {
    throw "未找到 Google Chrome。请先安装：https://www.google.com/chrome/"
}

Write-Host "正在安装网页依赖..." -ForegroundColor Cyan
npm.cmd ci

Write-Host "正在安装本地抓取器依赖..." -ForegroundColor Cyan
python -m pip install -r "amazon_scraper\requirements.txt"

Write-Host "依赖安装完成。以后双击“启动真实抓取器.bat”即可使用。" -ForegroundColor Green
