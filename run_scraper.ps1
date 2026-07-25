$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
Start-Process "http://127.0.0.1:8765"
python -m uvicorn amazon_scraper.app:app --host 127.0.0.1 --port 8765
