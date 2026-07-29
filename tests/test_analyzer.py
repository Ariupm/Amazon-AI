import unittest

from amazon_scraper.analyzer import analyze_reviews
from amazon_scraper.models import Review


class ReviewAnalyzerTests(unittest.TestCase):
    def test_low_star_mixed_review_only_keeps_negative_clause(self):
        result = analyze_reviews([
            Review(rating=2, body="The rug looks nice, however it never stays in place."),
            Review(rating=1, body="Looks nice but it never stays in place and keeps sliding."),
            Review(rating=1, body="Nunca llego y no recibí el producto."),
            Review(rating=2, body="This is a washable rug and the print looks good."),
        ])

        phrases = " ".join(item.phrase for item in result.pains)
        evidence = " ".join(text for item in result.pains for text in item.evidence)
        self.assertNotIn("looks nice", phrases)
        self.assertNotIn("washable rug", phrases)
        self.assertNotIn("print looks", phrases)
        self.assertIn("never stays", phrases)
        self.assertIn("★", evidence)

    def test_positive_low_star_sentence_is_not_a_pain(self):
        result = analyze_reviews([
            Review(rating=3, body="The color is beautiful and the washable rug looks nice."),
        ])
        self.assertEqual(result.pains, [])


if __name__ == "__main__":
    unittest.main()
