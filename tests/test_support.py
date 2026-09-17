"""測試輸出不可假成功、不可覆寫，以及敏感查詢參數遮蔽。"""
import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class SupportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('support'), '共用輸出與狀態處理尚未實作')
        import support
        self.s = support
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.job = support.Job(1, Path(self.temp.name) / 'q01')

    def test_csv_preserves_jersey_00_and_chinese_with_bom(self):
        p = self.job.save_csv('players.csv', ['姓名', '背號'], [{'姓名': '測試球員', '背號': '00'}])
        self.assertTrue(p.read_bytes().startswith(b'\xef\xbb\xbf'))
        with p.open(encoding='utf-8-sig', newline='') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [{'姓名': '測試球員', '背號': '00'}])

    def test_empty_output_is_not_a_successful_csv(self):
        with self.assertRaises(ValueError):
            self.job.save_csv('empty.csv', ['姓名'], [])
        self.assertFalse((self.job.path / 'empty.csv').exists())

    def test_mismatched_fields_do_not_leave_misleading_output(self):
        with self.assertRaises(ValueError):
            self.job.save_csv('bad.csv', ['姓名'], [{'名字': '甲'}])
        self.assertFalse((self.job.path / 'bad.csv').exists())

    def test_existing_results_are_not_overwritten(self):
        self.job.save_text('result.txt', 'first')
        with self.assertRaises(FileExistsError):
            self.job.save_text('result.txt', 'second')
        self.assertEqual((self.job.path / 'result.txt').read_text(), 'first')

    def test_output_cannot_escape_question_directory(self):
        with self.assertRaises(ValueError):
            self.job.save_text('../secret.txt', 'bad')

    def test_sources_hide_api_keys_but_keep_search_parameters(self):
        self.assertEqual(self.s.safe_url('https://example.org/?q=Python&key=secret&startIndex=10'),
                         'https://example.org/?q=Python&key=REDACTED&startIndex=10')

    def test_api_error_body_cannot_export_supplied_secret(self):
        response = SimpleNamespace(url='https://example.org/?key=private-value',
                                   content=b'{"error":"private-value is invalid"}', status_code=429)
        with patch.object(self.s.requests, 'get', return_value=response):
            with self.assertRaises(self.s.SourceBlocked):
                self.job.fetch('https://example.org/', 'error.json', {'key': 'private-value'})
        self.assertNotIn(b'private-value', (self.job.path / 'error.json').read_bytes())
        self.assertNotIn('private-value', json.dumps(self.job.sources))

    def test_chrome_is_visible_by_default_and_does_not_hide_automation_banner(self):
        with patch.object(self.s.webdriver, 'Chrome') as factory:
            self.s.make_browser(SimpleNamespace(interactive=False, headless=False, keep_open=False))
        options = factory.call_args.kwargs['options']
        self.assertFalse(any('headless' in flag for flag in options.arguments))
        self.assertNotIn('enable-automation', options.experimental_options.get('excludeSwitches', []))

    def test_headless_is_an_explicit_opt_in(self):
        with patch.object(self.s.webdriver, 'Chrome') as factory:
            self.s.make_browser(SimpleNamespace(interactive=False, headless=True, keep_open=False))
        self.assertIn('--headless=new', factory.call_args.kwargs['options'].arguments)

    def test_keep_open_preserves_visible_chrome_after_driver_service_stops(self):
        self.assertTrue(hasattr(self.s, 'close_browser'), '缺少可見瀏覽器保留功能')
        state = {'browser_open': True, 'service_running': True}
        def quit_browser():
            state['browser_open'] = False
        def stop_service():
            state['service_running'] = False
        driver = SimpleNamespace(quit=quit_browser, service=SimpleNamespace(stop=stop_service))
        self.s.close_browser(driver, SimpleNamespace(keep_open=True, headless=False, interactive=False))
        self.assertEqual(state, {'browser_open': True, 'service_running': False})

    def test_visible_keep_open_sets_chrome_detach_option(self):
        with patch.object(self.s.webdriver, 'Chrome') as factory:
            self.s.make_browser(SimpleNamespace(interactive=False, headless=False, keep_open=True))
        self.assertTrue(factory.call_args.kwargs['options'].experimental_options.get('detach'))

    def test_needs_user_has_machine_readable_status_not_success(self):
        def run(job, args):
            raise self.s.NeedsUser('需由本人完成年齡確認')
        record = self.s.execute(self.job, run, SimpleNamespace())
        self.assertEqual(record['status'], 'needs_user')
        self.assertEqual(json.loads((self.job.path / 'status.json').read_text())['status'], 'needs_user')

    def test_success_requires_saved_output(self):
        record = self.s.execute(self.job, lambda job, args: {'status': 'passed'}, SimpleNamespace())
        self.assertEqual(record['status'], 'error')

    def test_partial_keeps_true_rows_and_does_not_upgrade_to_passed(self):
        def run(job, args):
            job.save_csv('partial.csv', ['名稱'], [{'名稱': '一筆'}])
            return {'status': 'partial', 'note': '來源未提供全部必要欄位'}
        record = self.s.execute(self.job, run, SimpleNamespace())
        self.assertEqual(record['status'], 'partial')
        self.assertEqual(record['csv_rows'], {'partial.csv': 1})


if __name__ == '__main__':
    unittest.main()
