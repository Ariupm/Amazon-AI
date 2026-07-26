from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from openpyxl import load_workbook

from .models import KeywordFileSummary

KEYWORD_ALIASES = ("关键词", "搜索词", "keyword", "search term", "query")
VOLUME_ALIASES = ("搜索量", "月搜索量", "search volume", "流量", "预估搜索量")
MONTH_ALIASES = ("月份", "month", "日期", "date")


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _matches(value: str, aliases: tuple[str, ...]) -> bool:
    lowered = value.lower()
    return any(alias in lowered for alias in aliases)


def inspect_keyword_file(filename: str, content: bytes) -> KeywordFileSummary:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xls":
        raise ValueError("旧版 .xls 暂不支持，请另存为 .xlsx 后上传。")
    if suffix not in {".xlsx", ".csv"}:
        raise ValueError("ABA 综合词库请上传 .xlsx 或 .csv 文件。")
    if not content:
        raise ValueError("上传的词库为空。")

    sheet_name = "CSV"
    if suffix == ".xlsx":
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        sheet_name = sheet.title
        rows = [list(row) for row in sheet.iter_rows(values_only=True)]
    else:
        text = content.decode("utf-8-sig", errors="replace")
        rows = [row for row in csv.reader(io.StringIO(text))]

    header_index = -1
    keyword_index = -1
    volume_indexes: list[int] = []
    month_indexes: list[int] = []
    headers: list[str] = []
    for row_index, row in enumerate(rows[:30]):
        current = [_clean(value) for value in row]
        possible_keyword = next(
            (index for index, value in enumerate(current) if _matches(value, KEYWORD_ALIASES)),
            -1,
        )
        if possible_keyword < 0:
            continue
        header_index = row_index
        keyword_index = possible_keyword
        headers = current
        volume_indexes = [
            index for index, value in enumerate(current) if _matches(value, VOLUME_ALIASES)
        ]
        month_indexes = [
            index for index, value in enumerate(current) if _matches(value, MONTH_ALIASES)
        ]
        break

    if header_index < 0:
        return KeywordFileSummary(
            filename=filename,
            sheet=sheet_name,
            valid=False,
            warnings=["前 30 行未找到“关键词 / 搜索词 / Keyword”列。"],
        )

    keywords: list[str] = []
    for row in rows[header_index + 1:]:
        value = _clean(row[keyword_index] if keyword_index < len(row) else "")
        if value and value not in keywords:
            keywords.append(value)

    warnings: list[str] = []
    if not volume_indexes:
        warnings.append("未识别到搜索量列；仍可进入下一步，但无法按流量权重选词。")
    if not keywords:
        warnings.append("关键词列下没有有效数据。")
    return KeywordFileSummary(
        filename=filename,
        sheet=sheet_name,
        valid=bool(keywords),
        rows=len(keywords),
        keyword_column=headers[keyword_index],
        volume_columns=[headers[index] for index in volume_indexes],
        month_columns=[headers[index] for index in month_indexes],
        preview=keywords[:5],
        warnings=warnings,
    )
