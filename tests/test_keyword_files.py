import io
import unittest

from openpyxl import Workbook

from amazon_scraper.keyword_files import inspect_keyword_file


class KeywordFileTests(unittest.TestCase):
    def test_detects_aba_keyword_and_volume_columns(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "ABA词库"
        sheet.append(["说明", "每月追加，不覆盖历史"])
        sheet.append(["关键词", "月份", "卖家精灵预测搜索量"])
        sheet.append(["washable area rug", "2026-06", 12000])
        sheet.append(["high low pile rug", "2026-06", 5300])
        output = io.BytesIO()
        workbook.save(output)

        result = inspect_keyword_file("ABA.xlsx", output.getvalue())

        self.assertTrue(result.valid)
        self.assertEqual(result.rows, 2)
        self.assertEqual(result.keyword_column, "关键词")
        self.assertEqual(result.volume_columns, ["卖家精灵预测搜索量"])
        self.assertEqual(result.month_columns, ["月份"])
        self.assertEqual(result.keywords[0].term, "washable area rug")
        self.assertEqual(result.keywords[0].volume, 12000)

    def test_rejects_workbook_without_keyword_column(self):
        workbook = Workbook()
        workbook.active.append(["ASIN", "价格"])
        output = io.BytesIO()
        workbook.save(output)

        result = inspect_keyword_file("wrong.xlsx", output.getvalue())

        self.assertFalse(result.valid)
        self.assertTrue(result.warnings)


if __name__ == "__main__":
    unittest.main()
