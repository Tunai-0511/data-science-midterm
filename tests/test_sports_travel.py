"""PDF 原題第 6、14、16 題的解析與查詢條件契約。"""
import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from selenium.common.exceptions import ElementClickInterceptedException

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name('fixtures')


def fixture(name):
    return (FIXTURES / name).read_text(encoding='utf-8')


class BasketballRosterTests(unittest.TestCase):
    def test_roster_parser_preserves_jersey_00_rookie_and_blank_college(self):
        # Mutation caught: numeric conversion or filtering blank college would corrupt/drop the first row.
        q06 = importlib.import_module('q06')
        rows = q06.parse_roster(fixture('sports_roster.html'), 'CLE')
        self.assertEqual(rows[0], {
            '球隊': 'CLE', '背號': '00', '姓名': 'Jordan Test', '位置': 'PG',
            '體重': '190', '生日': 'January 2, 2000', '經驗': 'R', '大學': '',
        })
        self.assertEqual(len(rows), 2)

    def test_roster_parser_finds_table_inside_html_comment(self):
        # Mutation caught: parsing only visible DOM would miss Basketball Reference's commented tables.
        q06 = importlib.import_module('q06')
        rows = q06.parse_roster(fixture('sports_roster_commented.html'), 'HOU')
        self.assertEqual(rows[0]['姓名'], 'Comment Player')
        self.assertEqual(rows[0]['球隊'], 'HOU')

    def test_roster_parser_rejects_a_page_without_roster(self):
        # Mutation caught: accepting a block/error page could create a misleading successful CSV.
        q06 = importlib.import_module('q06')
        with self.assertRaises(q06.SourceChanged):
            q06.parse_roster('<html><title>Access denied</title></html>', 'GSW')


class HoopsHypeTests(unittest.TestCase):
    def test_salary_parser_keeps_every_header_and_row_in_current_table(self):
        # Mutation caught: hard-coded legacy columns would discard current/future season fields.
        q14 = importlib.import_module('q14')
        table = q14.parse_salary_table(fixture('sports_salaries.html'))
        self.assertEqual(table.fields, ['排名', 'Player', '2026-27', '2027-28'])
        self.assertEqual(len(table.rows), 4)
        self.assertEqual(table.rows[1]['2027-28'], 'P $ 62,841,702')

    def test_salary_parser_selects_first_three_verified_descending_salaries(self):
        # Mutation caught: treating rank as jersey or choosing more than three rows would fail here.
        q14 = importlib.import_module('q14')
        table = q14.parse_salary_table(fixture('sports_salaries.html'))
        self.assertEqual(
            [(p.name, p.salary, p.url) for p in table.top_three],
            [
                ('Stephen Curry', '$ 62,587,158', 'https://www.hoopshype.com/salaries/players/stephen-curry/338365/'),
                ('Nikola Jokic', '$ 59,033,114', 'https://www.hoopshype.com/salaries/players/nikola-jokic/830650/'),
                ('G. Antetokounmpo', '$ 58,456,566', 'https://www.hoopshype.com/salaries/players/giannis-antetokounmpo/739957/'),
            ],
        )
        self.assertEqual(table.season, '2026-27')

    def test_later_salary_pages_do_not_require_top_three_profile_links(self):
        # Mutation caught: only page 1 defines highest.csv; later pages may legitimately have no profile links.
        q14 = importlib.import_module('q14')
        html = fixture('sports_salaries.html').replace('<a href=', '<span data-unused=').replace('</a>', '</span>')
        table = q14.parse_salary_table(html, require_top_three=False)
        self.assertEqual(len(table.rows), 4)
        self.assertEqual(table.top_three, [])

    def test_salary_parser_rejects_malformed_rows_instead_of_claiming_all(self):
        # Mutation caught: silently skipping one current table row makes all_play.csv incomplete.
        q14 = importlib.import_module('q14')
        html = fixture('sports_salaries.html').replace(
            '</tbody>', '<tr><td>5</td><tdtd>Broken Player</td></tr></tbody>'
        )
        with self.assertRaises(q14.SourceChanged):
            q14.parse_salary_table(html)

    def test_salary_page_reports_current_and_total_pages(self):
        # Mutation caught: treating page 1 of 29 as the complete table would claim incomplete output.
        q14 = importlib.import_module('q14')
        self.assertEqual(q14.parse_pagination(fixture('sports_salaries.html')), (1, 29))

    def test_final_page_number_is_not_complete_when_validation_failed(self):
        # Mutation caught: current_page can reach total before the final page is parsed and accepted.
        q14 = importlib.import_module('q14')
        self.assertFalse(q14.pagination_is_complete(
            current_page=29, total_pages=29, loaded_pages=28, issue='final parse failed'
        ))
        self.assertTrue(q14.pagination_is_complete(
            current_page=29, total_pages=29, loaded_pages=29, issue=''
        ))

    def test_salary_ranks_follow_competition_sequence_across_pages(self):
        # Mutation caught: stale/repeated/skipped pages cannot masquerade as a complete salary table.
        q14 = importlib.import_module('q14')
        valid = [{'排名': rank, 'Player': name} for rank, name in [
            ('1', 'A'), ('2', 'B'), ('T3', 'C'), ('T3', 'D'), ('T3', 'E'), ('T6', 'F'),
        ]]
        q14.validate_rank_sequence(valid)
        with self.assertRaises(q14.SourceChanged):
            q14.validate_rank_sequence([{'排名': '1', 'Player': 'A'}, {'排名': '1', 'Player': 'A'}])
        with self.assertRaises(q14.SourceChanged):
            q14.validate_rank_sequence([{'排名': '1', 'Player': 'A'}, {'排名': '4', 'Player': 'B'}])

    def test_jersey_parser_reads_profile_number_not_salary_rank(self):
        # Mutation caught: using salary rank 1 instead of the profile's #30 would fail.
        q14 = importlib.import_module('q14')
        self.assertEqual(q14.parse_jersey(fixture('sports_profile.html'), 'Stephen Curry'), '30')
        self.assertIsNone(q14.parse_jersey('<main><div>#1</div><h1>Stephen Curry Salary</h1></main>', 'Stephen Curry'))

    def test_profile_failure_keeps_complete_salary_table_and_marks_partial(self):
        # Mutation caught: visiting profiles before saving all_play.csv loses requirement 3 on a profile failure.
        q14 = importlib.import_module('q14')
        from support import Job

        class SalaryPageBrowser:
            current_url = q14.URL
            page_source = fixture('sports_salaries.html')

            def get(self, _url):
                return None

            def find_elements(self, *_args):
                return []

            def save_screenshot(self, path):
                Path(path).write_bytes(b'fixture screenshot')
                return True

            def quit(self):
                return None

        with tempfile.TemporaryDirectory() as temp:
            job = Job(14, Path(temp) / 'q14')
            with patch.object(q14, 'make_browser', return_value=SalaryPageBrowser()), \
                    patch.object(q14, '_load_profile', return_value=None):
                result = q14.run(job, SimpleNamespace(interactive=False, max_pages=1))
            self.assertEqual(result['status'], 'partial')
            self.assertTrue((job.path / 'all_play.csv').exists())
            self.assertTrue((job.path / 'highest.csv').exists())

    def test_pagination_click_failure_keeps_verified_first_page_and_evidence(self):
        # Mutation caught: a covered next button must not erase already verified salary rows.
        q14 = importlib.import_module('q14')
        from support import Job

        class SalaryPageBrowser:
            current_url = q14.URL
            page_source = fixture('sports_salaries.html')

            def get(self, _url):
                return None

            def find_elements(self, *_args):
                return []

            def save_screenshot(self, path):
                Path(path).write_bytes(b'pager failure screenshot')
                return True

            def quit(self):
                return None

        with tempfile.TemporaryDirectory() as temp:
            job = Job(14, Path(temp) / 'q14')
            with patch.object(q14, 'make_browser', return_value=SalaryPageBrowser()), \
                    patch.object(q14, '_next_page_button', return_value=object()), \
                    patch.object(q14, '_click_next_page', side_effect=ElementClickInterceptedException('covered')), \
                    patch.object(q14, '_load_profile', return_value='30'):
                result = q14.run(job, SimpleNamespace(interactive=False, headless=True, keep_open=False, max_pages=29))
            self.assertEqual(result['status'], 'partial')
            self.assertTrue((job.path / 'all_play.csv').exists())
            self.assertTrue((job.path / 'pagination_failure_page_1.html').exists())
            self.assertTrue((job.path / 'pagination_failure.png').exists())


class AgodaTests(unittest.TestCase):
    def test_query_validation_requires_future_ordered_dates_and_positive_adults(self):
        # Mutation caught: invalid or ambiguous stay conditions must not reach Agoda.
        q16 = importlib.import_module('q16')
        self.assertEqual(q16.validate_stay('2026-10-01', '2026-10-02', 2, today=date(2026, 9, 10)), 1)
        for values in [
            ('2026-10-02', '2026-10-01', 2),
            ('2026-09-09', '2026-09-10', 2),
            ('2026-10-01', '2026-10-02', 0),
            ('not-a-date', '2026-10-02', 2),
        ]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                q16.validate_stay(*values, today=date(2026, 9, 10))

    def test_agoda_parser_pairs_each_hotel_with_its_own_price_and_context(self):
        # Mutation caught: global name/price lists can silently pair different cards.
        q16 = importlib.import_module('q16')
        rows = q16.parse_results(
            fixture('sports_agoda_results.html'),
            check_in='2026-10-01', check_out='2026-10-02', adults=2,
            captured_at='2026-09-10T12:00:00+08:00', source_url='https://www.agoda.com/zh-tw/search?city=12080',
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            '飯店名': '台中測試旅店', '價格': 'NT$ 2,345', '幣別': 'TWD',
            '價格範圍': '每晚', '稅費': '另加稅金和其他費用',
            '入住日': '2026-10-01', '退房日': '2026-10-02', '晚數': '1',
            '房數': '1', '成人數': '2', '擷取時間': '2026-09-10T12:00:00+08:00',
            '來源網址': 'https://www.agoda.com/zh-tw/test-hotel/hotel/taichung-tw.html',
        })
        self.assertEqual(rows[1]['價格範圍'], '每晚')
        self.assertEqual(rows[1]['稅費'], '含稅及其他費用')

    def test_agoda_parser_rejects_cards_without_prices(self):
        # Mutation caught: unavailable prices cannot be reported as a completed price scrape.
        q16 = importlib.import_module('q16')
        with self.assertRaises(q16.SourceChanged):
            q16.parse_results(
                '<div data-selenium="hotel-item"><h3 data-selenium="hotel-name">旅店</h3></div>',
                check_in='2026-10-01', check_out='2026-10-02', adults=2,
                captured_at='2026-09-10T12:00:00+08:00', source_url='https://www.agoda.com/zh-tw/search',
            )

    def test_agoda_parser_keeps_distinct_linkless_hotels(self):
        # Mutation caught: falling back to the shared search URL collapses different linkless cards.
        q16 = importlib.import_module('q16')
        html = '''
          <div data-selenium="hotel-item"><h3 data-selenium="hotel-name">甲旅店</h3><b data-selenium="display-price">TWD 1,000</b><span>每晚</span></div>
          <div data-selenium="hotel-item"><h3 data-selenium="hotel-name">乙旅店</h3><b data-selenium="display-price">TWD 1,200</b><span>每晚</span></div>
        '''
        rows = q16.parse_results(
            html, check_in='2026-10-01', check_out='2026-10-02', adults=2,
            captured_at='2026-09-10T12:00:00+08:00', source_url='https://www.agoda.com/zh-tw/search',
        )
        self.assertEqual([row['飯店名'] for row in rows], ['甲旅店', '乙旅店'])

    def test_agoda_parser_does_not_infer_price_unit_from_selector_name(self):
        # Mutation caught: display-price alone does not prove whether Agoda shows per-night or whole-stay price.
        q16 = importlib.import_module('q16')
        html = '<div data-selenium="hotel-item"><h3 data-selenium="hotel-name">旅店</h3><b data-selenium="display-price">TWD 1,000</b></div>'
        rows = q16.parse_results(
            html, check_in='2026-10-01', check_out='2026-10-02', adults=2,
            captured_at='2026-09-10T12:00:00+08:00', source_url='https://www.agoda.com/zh-tw/search',
        )
        self.assertEqual(rows[0]['價格範圍'], '頁面未明示')

    def test_set_adults_uses_picker_that_checkout_already_opened(self):
        # Mutation caught: clicking the guest summary when the picker is open closes it and causes a timeout.
        q16 = importlib.import_module('q16')

        class Value:
            text = '2'

        class Panel:
            def is_displayed(self):
                return True

            def find_element(self, _by, selector):
                if selector == '[data-selenium="desktop-occ-adult-value"]':
                    return Value()
                raise AssertionError(selector)

        class Box:
            clicks = 0

            def click(self):
                self.clicks += 1

        box, panel = Box(), Panel()

        class Driver:
            def find_elements(self, _by, selector):
                return [panel] if selector == '[data-selenium="occupancyAdults"]' else []

            def find_element(self, _by, selector):
                if selector == '[data-selenium="occupancyBox"]':
                    return box
                if selector == '[data-selenium="occupancyAdults"]':
                    return panel
                raise AssertionError(selector)

        class Wait:
            def until(self, condition):
                return condition(Driver())

        q16._set_adults(Driver(), Wait(), 2)
        self.assertEqual(box.clicks, 1)

    def test_select_date_ignores_hidden_duplicate_calendar_day(self):
        # Mutation caught: Agoda may render duplicate calendars; clicking the hidden matching day fails.
        q16 = importlib.import_module('q16')

        class Day:
            def __init__(self, visible):
                self.visible = visible
                self.clicked = False

            def is_displayed(self):
                return self.visible

            def click(self):
                if not self.visible:
                    raise AssertionError('hidden day clicked')
                self.clicked = True

        hidden, visible = Day(False), Day(True)

        class Driver:
            def find_elements(self, _by, selector):
                self.selector = selector
                return [hidden, visible]

        q16._select_date(Driver(), None, '2026-10-01')
        self.assertFalse(hidden.clicked)
        self.assertTrue(visible.clicked)

    def test_hidden_calendar_markup_does_not_count_as_an_open_picker(self):
        # Mutation caught: hidden duplicate date markup must not suppress the click that opens the real picker.
        q16 = importlib.import_module('q16')

        class Hidden:
            def is_displayed(self):
                return False

        class Driver:
            def find_elements(self, *_args):
                return [Hidden()]

        self.assertFalse(q16._date_picker_is_visible(Driver()))


if __name__ == '__main__':
    unittest.main()
