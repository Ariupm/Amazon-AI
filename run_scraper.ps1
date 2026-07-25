$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$port = 8765
$healthUrl = "http://127.0.0.1:$port/health"
$openApiUrl = "http://127.0.0.1:$port/openapi.json"
$pageUrl = "http://127.0.0.1:$port"

# Reuse a current server, but replace a stale version that lacks the batch API.
$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1
if ($listener) {
    $hasBatchApi = $false
    try {
        $schema = Invoke-RestMethod $openApiUrl -TimeoutSec 3
        $hasBatchApi = $null -ne $schema.paths."/api/scrape/batch"
    } catch {
        $hasBatchApi = $false
    }

    if ($hasBatchApi) {
        Start-Process $pageUrl
        Write-Host "真实抓取器已经运行，已打开页面。" -ForegroundColor Green
        exit 0
    }

    $oldProcess = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if ($oldProcess -and $oldProcess.ProcessName -match "python|uvicorn") {
        Stop-Process -Id $oldProcess.Id -Force
        Start-Sleep -Milliseconds 800
    } else {
        throw "端口 $port 被其他程序占用，无法安全替换。进程 ID：$($listener.OwningProcess)"
    }
}

$server = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "amazon_scraper.app:app", "--host", "127.0.0.1", "--port", "$port" `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden `
    -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 300
        if ($server.HasExited) {
            throw "抓取器启动失败，请查看当前窗口中的错误。"
        }
        try {
            $schema = Invoke-RestMethod $openApiUrl -TimeoutSec 2
            if ($null -ne $schema.paths."/api/scrape/batch") {
                $ready = $true
                break
            }
        } catch {
            # Server is still starting.
        }
    }
    if (-not $ready) {
        throw "抓取器启动超时。"
    }
    Start-Process $pageUrl
    Write-Host "真实抓取器已启动。关闭此窗口可停止服务。" -ForegroundColor Green
    Wait-Process -Id $server.Id
} finally {
    if (Get-Process -Id $server.Id -ErrorAction SilentlyContinue) {
        Stop-Process -Id $server.Id -Force
    }
}
