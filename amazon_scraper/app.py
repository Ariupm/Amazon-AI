from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import ScrapeRequest
from .scraper import ScrapeError, scrape_product

app = FastAPI(title="采数 Amazon 真实数据采集器", version="1.0.0")
static = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static), name="static")
lock = asyncio.Lock()


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "real-browser"}


@app.post("/api/scrape")
async def scrape(request: ScrapeRequest):
    if lock.locked():
        raise HTTPException(status_code=409, detail="已有采集任务正在运行，请等待完成。")
    async with lock:
        try:
            return await scrape_product(request.asin, request.marketplace, request.max_review_pages, request.headless)
        except ScrapeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"采集失败：{error}") from error
