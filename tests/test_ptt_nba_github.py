"""小型 HTML 是測試資料，不是來源網站的實際完成證據。"""
import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class OriginalQuestionsTests(unittest.TestCase):
    def module(self, name):
        self.assertIsNotNone(importlib.util.find_spec(name), f'{name} 尚未實作')
        return importlib.import_module(name)

    def test_ptt_omits_deleted_links_but_preserves_anonymous_author(self):
        q = self.module('q10')
        html = '''<div class="r-ent"><div class="title"><a href="/bbs/Gossiping/M.1.html">測試標題</a></div><div class="author">作者甲</div></div>
        <div class="r-ent"><div class="title">(本文已被刪除)</div><div class="author">-</div></div>'''
        rows, skipped = q.parse_posts(html)
        self.assertEqual(rows, [{'網址': 'https://www.ptt.cc/bbs/Gossiping/M.1.html', '標題': '測試標題', '作者': '作者甲'}])
        self.assertEqual(skipped, 1)

    def test_ptt_default_never_claims_user_age(self):
        q = self.module('q10')
        from support import NeedsUser
        with self.assertRaises(NeedsUser):
            q.run(None, SimpleNamespace(interactive=False))

    def test_nba_strips_price_separators_and_checks_exact_columns(self):
        q = self.module('q11')
        rows = q.parse_products('<tbody id="table-body"><tr><td>1</td><td>球衣</td><td>1,190</td></tr></tbody>')
        self.assertEqual(rows, [{'商品編號': '1', '商品名稱': '球衣', '價格': '1190'}])
        with self.assertRaises(ValueError):
            q.parse_products('<tbody id="table-body"><tr><td>1</td><td>球衣</td></tr></tbody>')

    def test_nba_duplicate_ids_and_source_count_mismatch_are_failures(self):
        q = self.module('q11')
        rows = [{'商品編號': '1'}, {'商品編號': '1'}]
        with self.assertRaises(ValueError):
            q.validate_all(rows, 2)
        with self.assertRaises(ValueError):
            q.validate_all([{'商品編號': '1'}], 2)
        q.validate_all([{'商品編號': '1'}, {'商品編號': '2'}], 2)

    def test_github_default_never_starts_authentication(self):
        q = self.module('q17')
        from support import NeedsUser
        with self.assertRaises(NeedsUser):
            q.run(None, SimpleNamespace(interactive=False))

    def test_github_panel_mapping_does_not_substitute_repository_list(self):
        q = self.module('q17')
        html = '''<aside><h2>Top repositories</h2><a>private/repo</a></aside>
        <section><h2>Create your first project</h2><p>Projects help organize your work.</p></section>
        <section><h2>Updates to your homepage feed</h2><p>We have combined the Following feed with the For you feed.</p></section>'''
        panels = q.parse_panels(html)
        self.assertEqual(set(panels), {'1', '2'})
        self.assertNotIn('private/repo', panels['1'])
        self.assertIn('Projects help organize', panels['1'])

    def test_github_missing_old_panels_remains_missing(self):
        q = self.module('q17')
        self.assertEqual(q.parse_panels('<main><h1>Home</h1><p>Trending repos</p></main>'), {})

    def test_github_never_exports_private_siblings_of_target_description(self):
        q = self.module('q17')
        html = '''<div><h2>Create your first project</h2><p>Create a repository to start building.</p>
        <aside><p>private-owner/secret-repo</p></aside></div>'''
        panel = q.parse_panels(html)['1']
        self.assertIn('Create a repository', panel)
        self.assertNotIn('private-owner', panel)

    def test_github_rejects_ambiguous_nonadjacent_description(self):
        q = self.module('q17')
        html = '<div><h2>Create your first project</h2><aside><p>private-owner/secret-repo</p></aside></div>'
        self.assertEqual(q.parse_panels(html), {})

    def test_github_manual_fallback_cannot_count_as_verified_password_login(self):
        q = self.module('q17')
        self.assertTrue(hasattr(q, 'completion_status'), '缺少登入驗證完成判定')
        self.assertEqual(q.completion_status({'1': 'a', '2': 'b'}, False), 'partial')
        self.assertEqual(q.completion_status({'1': 'a', '2': 'b'}, True), 'passed')
        self.assertEqual(q.completion_status({'1': 'a'}, True), 'partial')

    def test_ptt_missing_gate_does_not_claim_person_confirmed_age(self):
        q = self.module('q10')
        self.assertTrue(hasattr(q, 'completion_result'), '缺少分級頁實際操作狀態')
        result = q.completion_result(10, 1, False)
        self.assertEqual(result['status'], 'partial')
        self.assertNotIn('年齡確認由本人完成', result['note'])
        self.assertEqual(q.completion_result(10, 1, True)['status'], 'passed')


if __name__ == '__main__':
    unittest.main()
