import unittest

from amazon_scraper.models import KeywordEntry, TitleGenerateRequest, TitleKeywordSelection
from amazon_scraper.title_generator import generate_titles


class TitleGeneratorTests(unittest.TestCase):
    def test_generates_three_split_candidates_for_each_variant_combo(self):
        request = TitleGenerateRequest(
            brand="GENIMO",
            product_title="GENIMO Soft Washable High Low Pile Arch Pattern Area Rug",
            bullets=["Non slip textured polyester rug for living room and bedroom."],
            competitor_titles=[
                "Arch Pattern High Low Pile Washable Area Rug",
                "High Low Pile Textured Area Rug Non Slip",
            ],
            keywords=[
                KeywordEntry(term="washable area rugs", volume=12000),
                KeywordEntry(term="high low pile rug", volume=5300),
                KeywordEntry(term="kitchen knife set", volume=50000),
            ],
            category="Area Rug",
            use_case="Living Room and Bedroom",
            colors=["Beige", "Grey"],
            sizes=["5' x 7'", "8' x 10'"],
            title_format="split",
        )

        result = generate_titles(request)

        self.assertEqual(len(result.candidates), 12)
        self.assertTrue(result.traffic_keywords)
        self.assertNotIn("kitchen knife set", [item.term for item in result.traffic_keywords])
        self.assertTrue(all(item.main_count <= 75 for item in result.candidates))
        self.assertTrue(all(item.highlight_count <= 125 for item in result.candidates))
        self.assertTrue(all("Area Rug" in item.main_title for item in result.candidates))

    def test_classic_title_stays_within_200_characters(self):
        result = generate_titles(TitleGenerateRequest(
            product_title="Brand Modern Washable Non Slip Soft Textured Area Rug",
            keywords=[KeywordEntry(term="modern area rug", volume=1000)],
            title_format="classic",
        ))
        self.assertTrue(result.candidates)
        self.assertTrue(all(item.full_count <= 200 for item in result.candidates))

    def test_large_size_never_inherits_runner_or_bathroom_category(self):
        result = generate_titles(TitleGenerateRequest(
            brand="GENIMO",
            product_title="GENIMO Soft 2x6 Runner Rug Washable High Low Pile",
            bullets=["Non slip arch pattern rug."],
            competitor_titles=["Washable Area Rug for Living Room"],
            keywords=[
                KeywordEntry(term="bathroom rugs", volume=100000, rank=1, month="2026-06"),
                KeywordEntry(term="runner rug", volume=90000, rank=2, month="2026-06"),
                KeywordEntry(term="area rugs for living room", volume=80000, rank=3, month="2026-06"),
            ],
            category="Area Rug",
            colors=["Beige"],
            sizes=["9' x 12'"],
            title_format="split",
        ))
        self.assertTrue(result.candidates)
        self.assertTrue(all("Area Rug" in item.main_title for item in result.candidates))
        self.assertTrue(all("Runner" not in item.main_title for item in result.candidates))
        self.assertNotIn("bathroom rugs", [item.term for item in result.traffic_keywords])
        self.assertNotIn("runner rug", [item.term for item in result.traffic_keywords])
        self.assertIn("Living Room", result.size_scenarios[0].primary_scenes)

    def test_keeps_for_inside_confirmed_high_traffic_scene_phrase(self):
        result = generate_titles(TitleGenerateRequest(
            brand="GENIMO",
            product_title="GENIMO Washable Vintage Area Rug",
            bullets=["Indoor rug designed for living room."],
            keywords=[
                KeywordEntry(term="area rugs for living room", volume=80000),
                KeywordEntry(term="washable area rugs", volume=50000),
            ],
            keyword_selections=[
                TitleKeywordSelection(term="area rugs for living room", placement="main"),
                TitleKeywordSelection(term="washable area rugs", placement="highlight"),
            ],
            category="Area Rug",
            use_case="Living Room",
            sizes=["8' x 10'"],
        ))
        self.assertTrue(any("Area Rugs for Living Room" in item.main_title for item in result.candidates))

    def test_negative_terms_and_unverified_pains_never_become_title_claims(self):
        result = generate_titles(TitleGenerateRequest(
            brand="GENIMO",
            product_title="GENIMO Soft Area Rug",
            keywords=[
                KeywordEntry(term="outdoor area rug", volume=90000),
                KeywordEntry(term="soft area rug", volume=20000),
            ],
            negative_terms=["outdoor"],
            category="Area Rug",
            verified_improvements=["Reinforced Edges"],
            sizes=["5' x 7'"],
        ))
        self.assertNotIn("outdoor area rug", [item.term for item in result.traffic_keywords])
        self.assertTrue(any("Reinforced Edges" in item.full_title for item in result.candidates))

    def test_verified_style_is_prioritized_in_main_title(self):
        result = generate_titles(TitleGenerateRequest(
            brand="Yamaziot",
            product_title="Yamaziot Washable Runner Rug",
            bullets=["Machine washable low pile rug."],
            keywords=[
                KeywordEntry(term="runner rug", volume=80000),
                KeywordEntry(term="boho runner rug", volume=50000),
            ],
            category="Runner Rug",
            style="Boho, Vintage, Distressed, Floral, Traditional",
            sizes=["2' x 6'"],
            title_format="split",
        ))
        self.assertTrue(result.candidates)
        self.assertTrue(all("Boho" in item.main_title for item in result.candidates))
        boho = next(item for item in result.keyword_analysis if item.term == "boho runner rug")
        self.assertEqual(boho.recommended_placement, "main")

    def test_competitor_terms_are_analyzed_separately_from_aba_terms(self):
        result = generate_titles(TitleGenerateRequest(
            brand="GENIMO",
            product_title="GENIMO Washable Boho Runner Rug",
            competitor_titles=[
                "BrandA Washable Boho Runner Rug Non Slip",
                "BrandB Boho Runner Rug Washable Low Pile",
                "BrandC Vintage Boho Runner Rug for Hallway",
            ],
            keywords=[KeywordEntry(term="runner rugs", volume=90000)],
            category="Runner Rug",
            style="Boho, Vintage",
            must_have=["Washable", "Non-Slip", "Low Pile"],
            sizes=["2' x 6'"],
        ))
        self.assertEqual(result.keyword_analysis[0].term, "runner rugs")
        self.assertTrue(result.competitor_terms)
        self.assertTrue(any("boho runner rug" in item.term for item in result.competitor_terms))
        self.assertTrue(any(item.coverage_percent == 100 for item in result.competitor_terms))


if __name__ == "__main__":
    unittest.main()
