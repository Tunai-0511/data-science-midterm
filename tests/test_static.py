import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import q01
import q02
import q03
import q04
import q05
import q07
import q08
from support import Job, SourceBlocked, SourceChanged


FIXTURES = Path(__file__).parent / "fixtures"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class StaticParserTests(unittest.TestCase):
    def test_q01_extracts_each_film_card_without_mixing_fields(self):
        # Would fail if the card selector or runtime pattern stops matching.
        rows = q01.parse_movies(fixture_text("static_q01.html"), q01.URL)
        self.assertEqual(rows, [{"標題": "測試電影 Test Film", "內容": "這是手工核對的劇情摘要。", "片長分鐘": "98", "網址": "https://www.atmovies.com.tw/movie/fabc123/"}])

    def test_q01_keeps_a_film_when_only_runtime_is_unavailable(self):
        # Would fail if one missing runtime discards otherwise valid source data.
        html = '<article class="filmList"><div class="filmTitle"><a href="/movie/a/">片名</a></div><p>摘要</p><div class="runtime">上映日期：9/10/2026</div></article>'
        rows = q01.parse_movies(html, q01.URL)
        self.assertEqual(rows[0]["片長分鐘"], "")

    def test_q02_uses_desktop_rate_cells_once_and_carries_source_timestamp(self):
        # Would fail if responsive duplicate columns are parsed as extra rates.
        rows = q02.parse_rates(fixture_text("static_q02.html"))
        self.assertEqual(rows, [{"幣別": "美金 (USD)", "現金買入": "31.17", "現金賣出": "31.84", "即期買入": "31.52", "即期賣出": "31.62", "牌價時間": "2026/09/10 14:13"}])

    def test_q03_accepts_the_government_dataset_contract_and_preserves_headers(self):
        # Would fail if required government columns are removed or renamed.
        fields, rows = q03.parse_dataset((FIXTURES / "static_q03.csv").read_bytes())
        self.assertEqual(fields, ["年", "週", "就診類別", "年齡別", "縣市", "腸病毒健保就診人次", "健保就診總人次"])
        self.assertEqual(rows[0]["腸病毒健保就診人次"], "12")

    def test_q03_rejects_an_html_error_page_saved_as_csv(self):
        # Would fail if a 200 error document could be mistaken for the dataset.
        with self.assertRaises(SourceChanged):
            q03.parse_dataset(b"<html>not csv</html>")

    def test_q03_only_creates_final_csv_after_validating_source(self):
        # Would fail if an unvalidated download body gets the requested final name.
        valid = (FIXTURES / "static_q03.csv").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            job = Job(3, directory)
            job.fetch = lambda *args, **kwargs: SimpleNamespace(content=valid)
            q03.run(job, SimpleNamespace())
            self.assertEqual(job.csv_rows, {q03.FILENAME: 1})
            self.assertTrue((Path(directory) / q03.FILENAME).exists())

    def test_q03_html_response_never_creates_requested_final_csv(self):
        # Would fail if a 200 HTML error document can masquerade as the final CSV.
        with tempfile.TemporaryDirectory() as directory:
            job = Job(3, directory)
            job.fetch = lambda *args, **kwargs: SimpleNamespace(content=b"<html>error</html>")
            with self.assertRaises(SourceChanged):
                q03.run(job, SimpleNamespace())
            self.assertFalse((Path(directory) / q03.FILENAME).exists())

    def test_q04_emits_the_exact_requested_columns_from_one_search_page(self):
        # Would fail if title links, author labels, or offer prices drift.
        rows = q04.parse_books(fixture_text("static_q04.html"), q04.URL)
        self.assertEqual(rows, [{"書名": "圖解演算法", "網址": "https://www.books.com.tw/products/0010999999", "作者": "王小明、李小華", "書價": "395元"}])

    def test_q05_pairs_each_ranking_with_its_week_and_total_box_office(self):
        # Would fail if the site's two-row ranking layout is flattened incorrectly.
        rows = q05.parse_rankings(fixture_text("static_q05.html"))
        self.assertEqual(rows, [{"排名": "1", "片名": "電影甲 Film A", "本週票房": "$360", "累計票房": "$16,534"}, {"排名": "2", "片名": "電影乙 Film B", "本週票房": "$270", "累計票房": "$500"}])

    def test_q05_preserves_statistical_period_and_unit_for_interpretation(self):
        # Would fail if monetary values lose their period or ten-thousand-dollar unit.
        context = q05.parse_context(fixture_text("static_q05.html"))
        self.assertEqual(context, ("2026-09-04～2026-09-06", "萬新台幣"))

    def test_q05_chrome_network_error_is_source_block_not_missing_selector(self):
        self.assertTrue(hasattr(q05, 'ensure_source_page'))
        with self.assertRaisesRegex(SourceBlocked, 'ERR_TIMED_OUT'):
            q05.ensure_source_page('<div class="error-code">ERR_TIMED_OUT</div>')
        q05.ensure_source_page(fixture_text('static_q05.html'))

    def test_q07_maps_a_realistic_google_books_page_without_inventing_missing_values(self):
        # Would fail if absent optional publication dates crash or gain fake values.
        payload = json.loads(fixture_text("static_q07.json"))
        rows = q07.parse_page(payload, page=1)
        self.assertEqual(rows[0], {"頁碼": 1, "ID": "id-a", "書名": "Python 入門", "作者": "甲作者；乙作者", "出版日期": "2025", "網址": "https://books.google.com/books?id=id-a"})
        self.assertEqual(rows[1]["出版日期"], "")

    def test_q08_reads_every_item_in_featured_carousel_not_sidebar_dropdown(self):
        # Would fail if the implementation silently substitutes the sidebar or More page.
        rows = q08.parse_featured(fixture_text("static_q08_carousel.html"), q08.URL)
        self.assertEqual(rows, [{"標題": "未來電影甲", "上映日期": "2026/10/2", "網址": "https://www.atmovies.com.tw/movie/future-a/"}, {"標題": "未來電影乙", "上映日期": "2026/10/9", "網址": "https://www.atmovies.com.tw/movie/future-b/"}])


if __name__ == "__main__":
    unittest.main()
