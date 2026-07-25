from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .scraper import scrape_product


def main() -> None:
    parser = argparse.ArgumentParser(description="使用本机 Chrome 采集真实 Amazon 商品数据")
    parser.add_argument("asin")
    parser.add_argument("--marketplace", default="US", choices=["US", "UK", "DE", "JP"])
    parser.add_argument("--review-pages", type=int, default=2)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(scrape_product(args.asin, args.marketplace, args.review_pages, args.headless))
    text = result.model_dump_json(indent=2)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(args.output.resolve())
    else:
        print(text)


if __name__ == "__main__":
    main()
