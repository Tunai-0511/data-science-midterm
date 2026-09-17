from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name("fixtures")
sys.path.insert(0, str(ROOT))

from search_tools import (  # noqa: E402
    completion_status,
    extract_google_news_sections,
    extract_google_results,
    inspect_momo_search_result,
    is_verification_page,
    pagination_action,
    search_box_score,
)


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class GoogleResultParserTests(unittest.TestCase):
    def test_extracts_natural_results_inside_search_and_normalizes_redirect(self):
        # Break caught: scraping navigation/ads or returning Google's redirect URL.
        self.assertEqual(
            extract_google_results(fixture("search_google.html")),
            [
                {
                    "title": "Steam 精選遊戲",
                    "url": "https://store.steampowered.com/curator/123",
                },
                {
                    "title": "今年值得玩的 Steam 遊戲",
                    "url": "https://example.com/steam-list",
                },
            ],
        )

    def test_empty_search_area_does_not_fall_back_to_all_page_links(self):
        # Break caught: treating unrelated page links as search results.
        html = '<nav><a href="https://example.com"><h3>不是搜尋結果</h3></a></nav>'
        self.assertEqual(extract_google_results(html), [])


class GoogleNewsParserTests(unittest.TestCase):
    def test_each_requested_category_is_bounded_to_its_own_container(self):
        # Break caught: claiming all links on the page belong to every category.
        sections, missing = extract_google_news_sections(fixture("search_news.html"))
        self.assertEqual(missing, [])
        self.assertEqual(
            {name: [item["title"] for item in rows] for name, rows in sections.items()},
            {
                "焦點新聞": ["提要焦點標題", "主要焦點標題"],
                "地方新聞": ["提要地方標題", "地方新聞標題"],
                "您的主題": ["主題新聞標題"],
                "更多新聞": ["更多新聞標題"],
            },
        )

    def test_missing_categories_are_reported_instead_of_filled_with_other_links(self):
        # Break caught: silent completeness claim when a personalized section is absent.
        html = '<main><section><h2>焦點新聞</h2><article><a href="./read/a"><h3>A</h3></a></article></section></main>'
        sections, missing = extract_google_news_sections(html)
        self.assertEqual(sections["焦點新聞"][0]["title"], "A")
        self.assertIn("您的主題", missing)
        self.assertNotIn("更多新聞", sections)


class PageSafetyTests(unittest.TestCase):
    def test_search_box_scoring_requires_search_semantics(self):
        # Break caught: typing the query into an unrelated login or coupon field.
        self.assertGreater(
            search_box_score(
                {
                    "name": "keyword",
                    "placeholder": "請輸入商品關鍵字",
                    "aria-label": "搜尋商品",
                    "type": "search",
                }
            ),
            0,
        )
        self.assertEqual(
            search_box_score(
                {"name": "email", "placeholder": "電子郵件", "type": "text"}
            ),
            0,
        )

    def test_pagination_action_only_accepts_verified_visible_labels(self):
        # Break caught: clicking a visually unrelated link selected by a stale CSS class.
        self.assertEqual(pagination_action("更多結果", ""), "more")
        self.assertEqual(pagination_action("", "下一頁"), "next")
        self.assertIsNone(pagination_action("購物", ""))

    def test_google_unusual_traffic_page_is_verification_not_empty_results(self):
        # Break caught: saving a protection page as a successful empty scrape.
        html = "<html><title>Sorry...</title><p>Our systems have detected unusual traffic</p></html>"
        self.assertTrue(is_verification_page("Sorry...", html, "https://www.google.com/sorry/index"))

    def test_inactive_captcha_script_does_not_block_an_ordinary_page(self):
        # Break caught: classifying any page that merely loads CAPTCHA code as blocked.
        html = "<html><head><script src='/recaptcha/api.js'></script></head><body><main>一般搜尋結果</main></body></html>"
        self.assertFalse(
            is_verification_page("Google", html, "https://www.google.com/search?q=xpath")
        )
        ok, note = inspect_momo_search_result(
            "<html><script>const captchaConfig = {};</script><input value='nba'><ul class='goods-list'><li><a href='/goods/GoodsDetail.jsp?i_code=1'>NBA 球衣</a></li></ul></html>",
            "https://www.momoshop.com.tw/search/searchShop.jsp?keyword=nba",
            "nba",
        )
        self.assertTrue(ok, note)

    def test_momo_homepage_is_not_accepted_as_search_results(self):
        # Break caught: writing the homepage to NBA_test.html and reporting success.
        ok, note = inspect_momo_search_result(
            '<html><input name="keyword" value=""></html>',
            "https://www.momoshop.com.tw/main/Main.jsp",
            "nba",
        )
        self.assertFalse(ok)
        self.assertIn("搜尋結果網址", note)

    def test_momo_result_requires_query_evidence_and_product_cards(self):
        # Break caught: accepting a challenge/error page merely because its URL changed.
        ok, note = inspect_momo_search_result(
            fixture("search_momo.html"),
            "https://www.momoshop.com.tw/search/searchShop.jsp?keyword=nba",
            "nba",
        )
        self.assertTrue(ok, note)

    def test_momo_filled_homepage_with_products_is_not_a_result_page(self):
        # Break caught: ENTER has not navigated, but typed text and homepage recommendations satisfy weak checks.
        html = "<html><input name='keyword' value='nba'><ul class='listAreaUl'><li><a href='/goods/GoodsDetail.jsp?i_code=1'>推薦商品</a></li></ul></html>"
        ok, note = inspect_momo_search_result(
            html,
            "https://www.momoshop.com.tw/main/Main.jsp",
            "nba",
        )
        self.assertFalse(ok)
        self.assertIn("搜尋結果網址", note)

    def test_safety_bound_and_blocked_page_are_partial(self):
        # Break caught: claiming all Google results after hitting a cap or verification.
        self.assertEqual(completion_status("max_pages"), "partial")
        self.assertEqual(completion_status("blocked"), "partial")
        self.assertEqual(completion_status("no_control"), "partial")
        self.assertEqual(completion_status("no_next_after_navigation"), "passed")


if __name__ == "__main__":
    unittest.main()
