from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    BatchItemResult, BatchResult, BatchScrapeRequest, CompetitorDiscoverRequest,
    CompetitorDiscoverResult, CompetitorExportRequest, CompetitorPlanRequest,
    CompetitorPlanResult, KeywordFileSummary,
    ScrapeRequest, TitleExportRequest, TitleGenerateRequest, TitleGenerateResult,
)
from .competitors import build_competitor_plan, discover_competitors
from .excel_export import build_competitors_xlsx, build_products_xlsx, build_titles_xlsx
from .keyword_files import inspect_keyword_file, inspect_negative_file
from .scraper import BrowserSession, ScrapeError, scrape_product
from .title_generator import generate_titles

FEATURE_VERSION = "parent-size-title-batch-v20"
app = FastAPI(title="采数 Amazon 真实数据采集器", version="1.20.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://caishu-amazon-insights.chumoiii.chatgpt.site",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
static = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static), name="static")
lock = asyncio.Lock()


@app.middleware("http")
async def private_network_access(request, call_next):
    response = await call_next(request)
    if request.headers.get("access-control-request-private-network") == "true":
        response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(static / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "real-browser",
        "feature_version": FEATURE_VERSION,
        "version": app.version,
    }


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
        async with BrowserSession(request.marketplace, request.headless) as session:
            assert session.context is not None
            for asin in normalized:
                if len(asin) != 10 or not asin.isalnum():
                    items.append(BatchItemResult(requested_asin=asin, success=False, error="ASIN 格式错误"))
                    continue
                try:
                    result = await scrape_product(
                        asin, request.marketplace, request.max_review_pages,
                        request.headless, request.variant_mode,
                        context=session.context,
                    )
                    items.append(BatchItemResult(requested_asin=asin, success=True, result=result))
                except Exception as error:
                    items.append(BatchItemResult(requested_asin=asin, success=False, error=str(error)))
    succeeded = sum(item.success for item in items)
    return BatchResult(items=items, total=len(items), succeeded=succeeded, failed=len(items) - succeeded)


@app.post("/api/export/xlsx")
async def export_xlsx(batch: BatchResult) -> StreamingResponse:
    workbook = await build_products_xlsx(batch)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="amazon-products-with-images.xlsx"'},
    )


@app.post("/api/competitors/discover", response_model=CompetitorDiscoverResult)
async def competitor_discovery(request: CompetitorDiscoverRequest) -> CompetitorDiscoverResult:
    if lock.locked():
        raise HTTPException(status_code=409, detail="已有采集任务正在运行，请等待完成。")
    async with lock:
        async with BrowserSession(request.marketplace, request.headless) as session:
            assert session.context is not None
            try:
                return await discover_competitors(
                    session.context, request.asin, request.marketplace,
                    request.limit, request.headless, request.category,
                    request.material, request.style, request.use_case,
                    request.features, request.search_queries, request.brand,
                    request.search_pages, request.exclude_asins,
                    request.reference_titles, request.reference_bullets,
                    request.target_name, request.reference_image_data,
                    request.verify_detail_pages, request.product_type,
                    request.direct_competitor_definition, request.excluded_terms,
                    request.search_query_weights,
                )
            except ScrapeError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
            except Exception as error:
                raise HTTPException(status_code=500, detail=f"竞品发现失败：{error}") from error


@app.post("/api/competitors/plan", response_model=CompetitorPlanResult)
async def competitor_plan(request: CompetitorPlanRequest) -> CompetitorPlanResult:
    try:
        return build_competitor_plan(
            request.target_name, request.category, request.material, request.style,
            request.use_case, request.features, request.reference_titles,
            request.reference_bullets,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/competitors/export/xlsx")
async def export_competitors_xlsx(request: CompetitorExportRequest) -> StreamingResponse:
    workbook = await build_competitors_xlsx(request)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="amazon-competitor-candidates.xlsx"'},
    )


@app.post("/api/keywords/inspect", response_model=KeywordFileSummary)
async def inspect_keywords(request: Request, filename: str) -> KeywordFileSummary:
    content = await request.body()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="词库文件不能超过 20 MB。")
    try:
        return inspect_keyword_file(filename, content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/keywords/negative/inspect")
async def inspect_negative_keywords(request: Request, filename: str) -> dict[str, object]:
    content = await request.body()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="否词文件不能超过 20 MB。")
    try:
        return inspect_negative_file(filename, content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/titles/generate", response_model=TitleGenerateResult)
async def title_generation(request: TitleGenerateRequest) -> TitleGenerateResult:
    result = generate_titles(request)
    if not result.candidates:
        raise HTTPException(status_code=422, detail="真实资料不足，未能形成标题候选。")
    return result


@app.post("/api/titles/plan", response_model=TitleGenerateResult)
async def title_keyword_plan(request: TitleGenerateRequest) -> TitleGenerateResult:
    return generate_titles(request)


@app.post("/api/titles/export/xlsx")
async def export_titles_xlsx(request: TitleExportRequest) -> StreamingResponse:
    workbook = build_titles_xlsx(request)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="amazon-size-titles.xlsx"'},
    )
