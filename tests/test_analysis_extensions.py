"""Offline regressions: python -m unittest discover -s tests -v."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_question(number):
    path = next(ROOT.glob(f"第{number:02}題_*/main.py"))
    spec = importlib.util.spec_from_file_location(f"question_{number}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnalysisRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.log = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.log)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def module(self, number):
        module = load_question(number)
        for name in ("OUTPUT", "DETAIL_OUTPUT", "CHART_OUTPUT", "MERGED_OUTPUT"):
            if hasattr(module, name):
                setattr(module, name, self.folder / getattr(module, name).name)
        return module

    def test_books_normal_entry_point_saves_scraped_rows(self):
        module = self.module(4)
        html = '''<div class="table-td" id="prod-itemlist-001">
          <h4><a title="離線測試書">book</a></h4>
          <p class="author"><a>Author</a></p><ul class="price">優惠價 500 元</ul>
        </div>'''
        with patch.object(module, "get_html_with_chrome", return_value=html):
            module.main()
        rows = pd.read_csv(module.OUTPUT)
        self.assertEqual(rows.iloc[0]["書名"], "離線測試書")
        self.assertEqual(rows.iloc[0]["書價"], 500)
        self.assertTrue(module.CHART_OUTPUT.exists())

    def test_book_missing_prices_remain_missing(self):
        module = self.module(4)
        module.analyze_and_draw(pd.DataFrame({
            "書名": ["A", "B", "C"], "作者": ["a"]*3,
            "網址": ["https://example.com/a", "", None],
            "書價": ["1,500", "售完", -1],
        }))
        # 「1,500」轉成 1500；「售完」和 -1 不算有效價格
        self.assertIn("有效價格 1 本；缺漏或無效價格 2 本", self.log.getvalue())
        self.assertIn("最低價 1,500.00", self.log.getvalue())
        self.assertTrue(module.CHART_OUTPUT.exists())

    def test_boxoffice_small_unsorted_sample_and_invalid_value(self):
        module = self.module(5)
        module.analyze_and_draw(pd.DataFrame({
            "排名": [2, 1, 3, 4], "片名": ["A", "B", "C", "D"],
            "本週票房": ["$1", "$2", "$3", "未知"],
            "累計票房": ["$10", "$20", "$30", "未知"],
        }))
        rows = pd.read_csv(module.DETAIL_OUTPUT)
        self.assertEqual(rows["片名"].tolist(), ["C", "B", "A"])
        self.assertAlmostEqual(rows["累積票房佔比(%)"].iloc[-1], 100)
        self.assertAlmostEqual(rows["本週票房佔比(%)"].iloc[0], 50)

    def test_missing_book_ids_are_not_duplicates(self):
        module = self.module(7)
        module.analyze_and_draw(pd.DataFrame({
            "書名": ["A", "B"], "出版日期": [None, None],
            "出版社": [None, None], "網址": [None, ""],
        }))
        self.assertIn("重複 ID 列數（含同組全部列）0", self.log.getvalue())
        self.assertTrue(module.CHART_OUTPUT.exists())

    def test_movie_chart_handles_more_than_thirteen_and_iso_year(self):
        module = self.module(8)
        module.analyze_and_draw(pd.DataFrame({
            "名稱": [f"Movie {i}" for i in range(15)],
            "上映時間": ["2027/1/1"]*14 + ["未定"],
        }))
        rows = pd.read_csv(module.DETAIL_OUTPUT)
        self.assertEqual(rows["上映週別"].dropna().unique().tolist(), ["2026-W53"])
        self.assertEqual(rows["上映日期_dt"].notna().sum(), 14)
        self.assertTrue(module.CHART_OUTPUT.exists())

    def test_product_names_do_not_confuse_hoodies_capes_or_sleeves(self):
        module = self.module(11)
        examples = {
            "NIKE 連帽上衣 帽T": "上衣",
            "Modern Women's Cape 休閒外套": "上衣",
            "NBA 棒球帽 cap": "帽子",
            "NBA 球衣 同款球褲": "褲子",
            "籃球臂套 Sleeve": "其他",
            "NBA 長袖上衣": "上衣",
        }
        for title, expected in examples.items():
            with self.subTest(title=title):
                self.assertEqual(module.classify_product(title), expected)

    def test_product_merge_handles_absent_categories_and_bad_prices(self):
        module = self.module(11)
        module.FOLDER = self.folder
        pd.DataFrame({
            "商品編號": [1, 2], "商品名稱": ["帽T", "連帽上衣"], "價格": ["1,000", "售完"],
        }).to_csv(self.folder / "NBA_Products1.csv", index=False)
        module.analyze_and_draw()
        rows = pd.read_csv(module.MERGED_OUTPUT)
        self.assertEqual(rows["商品類型"].tolist(), ["上衣", "上衣"])
        self.assertEqual(rows["價格(元)"].notna().sum(), 1)
        self.assertTrue(module.CHART_OUTPUT.exists())

    def test_hotel_chart_keeps_high_prices_and_unrated_stays(self):
        module = self.module(16)
        frame = pd.DataFrame({
            "價格(元)": [1000, 2000, 200000], "評分": [8, 9, None], "地區": ["逢甲"]*3,
        })
        import matplotlib.figure
        savefig = matplotlib.figure.Figure.savefig
        observed = []

        def inspect(figure, *args, **kwargs):
            observed.append(figure.axes[0].get_ylim())
            return savefig(figure, *args, **kwargs)

        with patch.object(matplotlib.figure.Figure, "savefig", inspect):
            module.analyze_and_draw(frame)
        self.assertGreaterEqual(observed[0][1], 200000)
        self.assertIn("有效價格 3 筆；價格與評分皆有效 2 筆", self.log.getvalue())


if __name__ == "__main__":
    unittest.main()
