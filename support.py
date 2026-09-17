"""17 題共用的輸出、狀態與瀏覽器工具；不處理或繞過網站驗證。"""
import argparse
import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import requests
from selenium import webdriver

ROOT = Path(__file__).resolve().parent
EXIT_CODES = {'passed': 0, 'partial': 2, 'blocked': 3, 'needs_user': 4, 'error': 1}


class SourceBlocked(RuntimeError):
    """來源不可正常存取；不把阻擋畫面當成目標資料。"""


class SourceChanged(RuntimeError):
    """來源結構或資料與題目不相符。"""


class NeedsUser(RuntimeError):
    """需由使用者完成登入、確認或提供自己的設定。"""


def safe_url(url):
    parts = urlsplit(str(url))
    private = {'key', 'api_key', 'apikey', 'access_token', 'token', 'password', 'code'}
    pairs = [(k, 'REDACTED' if k.lower() in private else v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    # 不記錄 URL 內可能存在的帳密。
    host = parts.netloc.rsplit('@', 1)[-1]
    return urlunsplit((parts.scheme, host, parts.path, urlencode(pairs), ''))


class Job:
    def __init__(self, number, output_dir):
        self.number = number
        self.path = Path(output_dir).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        self.sources = []
        self.files = []
        self.csv_rows = {}
        self.started_at = datetime.now().astimezone().isoformat()

    def _target(self, filename):
        if not filename or Path(filename).name != str(filename):
            raise ValueError('輸出名稱只能是目前題目目錄內的檔名')
        path = self.path / filename
        if path.exists():
            raise FileExistsError(f'不覆寫已存在的結果：{filename}')
        return path

    def save_bytes(self, filename, data):
        path = self._target(filename)
        with path.open('xb') as stream:
            stream.write(data)
        self.files.append(filename)
        return path

    def save_text(self, filename, text):
        return self.save_bytes(filename, text.encode('utf-8'))

    def save_csv(self, filename, fields, rows):
        rows, fields = list(rows), list(fields)
        if not rows or not fields:
            raise ValueError('沒有資料，不建立看似完成的空 CSV')
        if len(set(fields)) != len(fields) or any(set(row) != set(fields) for row in rows):
            raise ValueError('CSV 欄位重複或與資料不一致')
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        data = buffer.getvalue().encode('utf-8-sig')
        reread = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        if len(reread) != len(rows):
            raise ValueError('CSV 重新讀取筆數不一致')
        path = self.save_bytes(filename, data)
        self.csv_rows[filename] = len(rows)
        return path

    def fetch(self, url, name='source.html', params=None):
        self.sources.append(safe_url(url))
        try:
            response = requests.get(url, params=params, timeout=(10, 35))
        except requests.exceptions.SSLError:
            raise SourceBlocked('來源 TLS 憑證驗證失敗；未關閉憑證檢查') from None
        except requests.exceptions.RequestException as error:
            raise SourceBlocked(f'網路請求失敗：{type(error).__name__}；未輸出可能含 key 的例外網址') from None
        self.sources.append(safe_url(response.url))
        body = response.content
        private = {'key', 'api_key', 'apikey', 'access_token', 'token', 'password', 'code'}
        parameters = list(parse_qsl(urlsplit(url).query)) + list((params or {}).items())
        for field, value in parameters:
            if field.lower() in private and value:
                for form in (str(value), quote(str(value), safe=''), json.dumps(str(value))[1:-1]):
                    body = body.replace(form.encode('utf-8'), b'REDACTED')
        self.save_bytes(name, body)
        if response.status_code != 200:
            raise SourceBlocked(f'來源回傳 HTTP {response.status_code}，原始回應已保存')
        return response

    def capture(self, driver, filename='source.png'):
        path = self._target(filename)
        if not driver.save_screenshot(str(path)):
            raise RuntimeError('瀏覽器截圖未成功儲存')
        self.files.append(filename)
        self.sources.append(safe_url(driver.current_url))
        return path


def make_browser(args):
    options = webdriver.ChromeOptions()
    headless = getattr(args, 'headless', False) and not getattr(args, 'interactive', False)
    if headless:
        options.add_argument('--headless=new')
    if getattr(args, 'keep_open', False) and not headless:
        options.add_experimental_option('detach', True)
    options.add_argument('--window-size=1440,1000')
    options.page_load_strategy = 'eager'
    # 使用 Selenium 的正常驅動管理，不載入私人設定檔，不隱藏自動化。
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(40)
    return driver


def close_browser(driver, args):
    headless = getattr(args, 'headless', False) and not getattr(args, 'interactive', False)
    if getattr(args, 'keep_open', False) and not headless:
        # 停止控制服務但保留公開網頁，讓使用者自行關閉 Chrome。
        driver.service.stop()
    else:
        driver.quit()


def pause_for_user(driver, args, message):
    if not getattr(args, 'interactive', False):
        raise NeedsUser(message + '；請在本機以 --interactive 執行')
    print(message, flush=True)
    print('請在瀏覽器自行完成必要操作。不要把密碼或驗證碼貼到聊天中。', flush=True)
    try:
        input('完成後回到終端按 Enter；取消請按 Ctrl+C：')
    except EOFError:
        raise NeedsUser('互動模式需要可輸入的本機終端') from None


def execute(job, handler, args):
    try:
        result = handler(job, args) or {}
        status = result.get('status', 'passed')
        if status not in EXIT_CODES:
            raise ValueError('題目回傳了未知狀態')
        if status == 'passed' and not job.files:
            raise ValueError('沒有保存任何成果，不能標記為完成')
        note = result.get('note', '')
    except NeedsUser as error:
        status, note = 'needs_user', str(error)
    except SourceBlocked as error:
        status, note = 'blocked', str(error)
    except SourceChanged as error:
        status, note = 'partial', str(error)
    except KeyboardInterrupt:
        status, note = 'needs_user', '使用者已中止互動；尚未完成'
    except Exception as error:
        # 外部例外可能含 URL、cookie 或表單值，因此只記錄類型。
        status, note = 'error', f'{type(error).__name__}：執行未完成，請檢查來源與程式'
    record = {
        'question': job.number, 'status': status, 'note': note,
        'started_at': job.started_at, 'finished_at': datetime.now().astimezone().isoformat(),
        'sources': list(dict.fromkeys(safe_url(s) for s in job.sources)),
        'files': list(job.files), 'csv_rows': job.csv_rows,
        'sha256': {name: hashlib.sha256((job.path / name).read_bytes()).hexdigest() for name in job.files},
    }
    job.save_text('status.json', json.dumps(record, ensure_ascii=False, indent=2))
    print(f'第 {job.number:02d} 題 [{status}] {note}\n成果目錄：{job.path}', flush=True)
    return record


def cli_parser(number=None):
    parser = argparse.ArgumentParser(description=f'PDF 原題 {number or "1–17"} 實作')
    parser.add_argument('--interactive', action='store_true', help='允許本人完成必要登入或確認，強制顯示瀏覽器')
    parser.add_argument('--headless', action='store_true', help='不顯示瀏覽器；預設會開啟可見的 Chrome')
    parser.add_argument('--keep-open', action='store_true', help='公開網頁題目執行後保留 Chrome；第 10、17 題仍關閉')
    parser.add_argument('--output', type=Path, default=ROOT / 'results', help='結果根目錄，每次仍建立新的時間目錄')
    parser.add_argument('--max-pages', type=int, default=5, help='搜尋結果安全頁數上限；達上限會標示部分完成')
    parser.add_argument('--check-in', default=(date.today() + timedelta(days=21)).isoformat())
    parser.add_argument('--check-out', default=(date.today() + timedelta(days=22)).isoformat())
    parser.add_argument('--adults', type=int, default=2)
    return parser


def run_cli(number, handler):
    args = cli_parser(number).parse_args()
    if args.max_pages < 1 or args.adults < 1:
        raise SystemExit('max-pages 與 adults 必須是正整數')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    job = Job(number, args.output / stamp / f'q{number:02d}')
    record = execute(job, handler, args)
    raise SystemExit(EXIT_CODES[record['status']])
