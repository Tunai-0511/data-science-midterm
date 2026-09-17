"""依 PDF 題號執行；單題遇到阻擋仍保存狀態並接著執行其他題。"""
import importlib
import json
from datetime import datetime
from support import Job, cli_parser, execute


def validate_questions(numbers):
    if not numbers or any(number < 1 or number > 17 for number in numbers):
        raise ValueError('題號必須是 1 至 17')
    return list(dict.fromkeys(numbers))


def run_questions(numbers, args):
    numbers = validate_questions(numbers)
    directory = args.output / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    directory.mkdir(parents=True, exist_ok=False)
    summary = []
    for number in numbers:
        job = Job(number, directory / f'q{number:02d}')
        def handler(current_job, current_args):
            return importlib.import_module(f'q{number:02d}').run(current_job, current_args)
        record = execute(job, handler, args)
        summary.append(record)
        # 每一題之後即更新本次摘要，中途停止也保留已完成的狀態。
        (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return summary, directory


def main():
    parser = cli_parser()
    parser.add_argument('--questions', nargs='+', type=int, default=list(range(1, 18)), help='只跑指定題號，例如 --questions 1 5 11')
    args = parser.parse_args()
    if args.max_pages < 1 or args.adults < 1:
        parser.error('max-pages 與 adults 必須是正整數')
    try:
        numbers = validate_questions(args.questions)
    except ValueError as error:
        parser.error(str(error))
    summary, directory = run_questions(numbers, args)
    counts = {name: sum(r['status'] == name for r in summary)
              for name in ('passed', 'partial', 'blocked', 'needs_user', 'error')}
    print(json.dumps(counts, ensure_ascii=False), '\n本次摘要：', directory / 'summary.json')
    return 0 if all(r['status'] == 'passed' for r in summary) else 2


if __name__ == '__main__':
    raise SystemExit(main())
