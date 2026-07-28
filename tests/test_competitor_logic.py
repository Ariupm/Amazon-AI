import unittest

from amazon_scraper.competitors import (
    _decode_reference_image,
    _dedupe_and_sort_candidates,
    _title_brand,
    _title_size,
)
from amazon_scraper.models import CompetitorCandidate


def candidate(
    asin: str,
    brand: str,
    size: str,
    monthly: int | None,
    score: int,
) -> CompetitorCandidate:
    return CompetitorCandidate(
        asin=asin,
        brand=brand,
        size=size,
        title=f"{brand} rug {size}",
        url=f"https://www.amazon.com/dp/{asin}",
        monthly_sales_estimate=monthly,
        recent_sales_signal=f"{monthly}+ bought in past month" if monthly else None,
        text_similarity=score,
        overall_similarity=score,
    )


class CompetitorLogicTests(unittest.TestCase):
    def test_decodes_uploaded_reference_image_data(self):
        import base64

        content = b"fake-image-bytes"
        encoded = "data:image/png;base64," + base64.b64encode(content).decode()

        self.assertEqual(_decode_reference_image(encoded), content)
        self.assertIsNone(_decode_reference_image("data:text/plain;base64,Zm9v"))

    def test_extracts_brand_and_size_without_using_size_as_search_input(self):
        title = "SHACOS Soft Cozy 2' x 3' Washable High Low Pile Area Rug"
        self.assertEqual(_title_brand(title), "SHACOS")
        self.assertEqual(_title_size(title), "2' x 3'")

    def test_keeps_one_monthly_sales_winner_per_brand(self):
        values = [
            candidate("B000000001", "BrandA", "2x6", 100, 88),
            candidate("B000000002", "BrandA", "2' x 6'", 500, 70),
            candidate("B000000003", "BrandA", "5x7", 50, 95),
            candidate("B000000004", "BrandB", "2x6", 1000, 60),
        ]
        result, collapsed = _dedupe_and_sort_candidates(values)
        self.assertEqual(collapsed, 2)
        self.assertEqual(
            [item.asin for item in result],
            ["B000000004", "B000000002"],
        )


if __name__ == "__main__":
    unittest.main()
