import unittest
from openpyxl import load_workbook

from amazon_scraper.excel_export import build_titles_xlsx
from amazon_scraper.models import TitleExportItem, TitleExportRequest


class TitleExportTests(unittest.TestCase):
    def test_sizes_are_column_headers_and_details_are_auditable(self):
        workbook_bytes = build_titles_xlsx(TitleExportRequest(
            parent_asin="B0PARENT00",
            main_child_asin="B0CHILD001",
            items=[
                TitleExportItem(
                    asin="B0CHILD001", size="5' x 7'", strategy="balanced",
                    main_title="Brand Vintage Area Rug 5' x 7'",
                    highlight_item="Washable Low Pile", full_title="Full one", score=96,
                ),
                TitleExportItem(
                    asin="B0CHILD002", size="8' x 10'", strategy="balanced",
                    main_title="Brand Vintage Area Rug 8' x 10'",
                    highlight_item="Washable Low Pile", full_title="Full two", score=95,
                ),
            ],
        ))
        workbook = load_workbook(workbook_bytes)
        self.assertEqual(workbook["按尺寸标题"]["B1"].value, "5' x 7'")
        self.assertEqual(workbook["按尺寸标题"]["C1"].value, "8' x 10'")
        self.assertEqual(workbook["标题明细"]["A2"].value, "B0PARENT00")
        self.assertEqual(workbook["标题明细"]["B2"].value, "B0CHILD001")


if __name__ == "__main__":
    unittest.main()
