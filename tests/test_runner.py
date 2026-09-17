import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RunnerTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('run_all'), '逐題執行入口尚未實作')
        import run_all
        return run_all

    def test_invalid_question_numbers_are_rejected_before_network(self):
        runner = self.module()
        with self.assertRaises(ValueError):
            runner.validate_questions([0, 18])
        self.assertEqual(runner.validate_questions([11, 1, 11]), [11, 1])

    def test_blocked_question_does_not_prevent_next_question_output(self):
        runner = self.module()
        from support import SourceBlocked
        def blocked(job, args):
            raise SourceBlocked('HTTP 429')
        def passed(job, args):
            job.save_csv('works.csv', ['值'], [{'值': '成功'}])
            return {'status': 'passed'}
        def load(name):
            return SimpleNamespace(run={'q01': blocked, 'q02': passed}[name])
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(output=Path(folder), interactive=False)
            with patch.object(runner.importlib, 'import_module', side_effect=load):
                summary, directory = runner.run_questions([1, 2], args)
            self.assertEqual([r['status'] for r in summary], ['blocked', 'passed'])
            self.assertTrue((directory / 'q02' / 'works.csv').exists())
            self.assertEqual(json.loads((directory / 'summary.json').read_text())[0]['status'], 'blocked')


if __name__ == '__main__':
    unittest.main()
