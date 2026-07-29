$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$port = 8765
$webPort = 3000
$healthUrl = "http://127.0.0.1:$port/health"
$openApiUrl = "http://127.0.0.1:$port/openapi.json"
$pageUrl = "http://localhost:$webPort/titles"
$requiredFeatureVersion = "structured-title-dedupe-v21"

function Get-ListenerProcessId {
    $connection = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($connection) {
        return [int]$connection.OwningProcess
    }

    # Get-NetTCPConnection can return nothing for a listener owned by a process
    # started in another terminal/session. netstat still exposes the PID.
    $line = netstat -ano |
        Select-String -Pattern "^\s*TCP\s+127\.0\.0\.1:$port\s+\S+\s+LISTENING\s+(\d+)\s*$" |
        Select-Object -First 1
    if ($line -and $line.Matches.Count -gt 0) {
        return [int]$line.Matches[0].Groups[1].Value
    }
    return $null
}

# Reuse only the exact current server. Merely having the batch API is not
# sufficient because older competitor-discovery code used the same endpoint.
$listenerProcessId = Get-ListenerProcessId
if ($listenerProcessId) {
    $isCurrentVersion = $false
    try {
        $health = Invoke-RestMethod $healthUrl -TimeoutSec 3
        $isCurrentVersion = $health.feature_version -eq $requiredFeatureVersion
    } catch {
        $isCurrentVersion = $false
    }

    if ($isCurrentVersion) {
        try {
            Invoke-WebRequest $pageUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
        } catch {
            Start-Process -FilePath "npm.cmd" `
                -ArgumentList "run", "dev", "--", "--host", "localhost", "--port", "$webPort" `
                -WorkingDirectory $PSScriptRoot `
                -WindowStyle Hidden
        }
        Start-Sleep -Seconds 2
        Start-Process $pageUrl
        Write-Host "最新版真实抓取器已经运行，已打开页面。" -ForegroundColor Green
        exit 0
    }

    $oldProcess = Get-Process -Id $listenerProcessId -ErrorAction SilentlyContinue
    if ($oldProcess -and $oldProcess.ProcessName -match "python|uvicorn") {
        Write-Host "检测到旧版抓取器，正在替换..." -ForegroundColor Yellow
        Stop-Process -Id $oldProcess.Id -Force
        Start-Sleep -Milliseconds 800
    } else {
        throw "端口 $port 被其他程序占用，无法安全替换。进程 ID：$listenerProcessId"
    }
}

$server = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "amazon_scraper.app:app", "--host", "127.0.0.1", "--port", "$port" `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden `
    -PassThru
$webServer = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev", "--", "--host", "localhost", "--port", "$webPort" `
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
            $health = Invoke-RestMethod $healthUrl -TimeoutSec 2
            if ($health.feature_version -eq $requiredFeatureVersion) {
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
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 300
        try {
            Invoke-WebRequest $pageUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
            break
        } catch {
            if ($webServer.HasExited) {
                throw "本地标题工作台启动失败。"
            }
        }
    }
    Start-Process $pageUrl
    Write-Host "标题工作台 V21 与真实抓取器已在本机启动。关闭此窗口可停止服务。" -ForegroundColor Green
    Wait-Process -Id $server.Id
} finally {
    if (Get-Process -Id $server.Id -ErrorAction SilentlyContinue) {
        Stop-Process -Id $server.Id -Force
    }
    if ($webServer -and (Get-Process -Id $webServer.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $webServer.Id -Force
    }
}
