from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import BatchItemResult, BatchResult, BatchScrapeRequest, ScrapeRequest
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
            return await scrape_product(
                request.asin, request.marketplace, request.max_review_pages,
                request.headless, request.variant_mode,
            )
        except ScrapeError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=f"采集失败：{error}") from error


@app.post("/api/scrape/batch", response_model=BatchResult)
async def scrape_batch(request: BatchScrapeRequest) -> BatchResult:
    if lock.locked():
        raise HTTPException(status_code=409, detail="已有采集任务正在运行，请等待完成。")
    normalized = list(dict.fromkeys(value.strip().upper() for value in request.asins if value.strip()))
    if not normalized:
        raise HTTPException(status_code=422, detail="没有可采集的 ASIN。")
    items: list[BatchItemResult] = []
    async with lock:
        for asin in normalized:
            if len(asin) != 10 or not asin.isalnum():
                items.append(BatchItemResult(requested_asin=asin, success=False, error="ASIN 格式错误"))
                continue
            try:
                result = await scrape_product(
                    asin, request.marketplace, request.max_review_pages,
                    request.headless, request.variant_mode,
                )
                items.append(BatchItemResult(requested_asin=asin, success=True, result=result))
            except Exception as error:
                items.append(BatchItemResult(requested_asin=asin, success=False, error=str(error)))
    succeeded = sum(item.success for item in items)
    return BatchResult(items=items, total=len(items), succeeded=succeeded, failed=len(items) - succeeded)
