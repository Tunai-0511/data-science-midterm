"""第 11 題：實際點擊 NBA 商品動態分頁，每頁各存一個 CSV。"""
import json
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from support import SourceChanged, close_browser, make_browser, run_cli

URL = 'https://fchart.github.io/ML/nba_items.html'
FIELDS = ['商品編號', '商品名稱', '價格']


def parse_products(html):
    rows = []
    for tr in BeautifulSoup(html, 'html.parser').select('#table-body tr'):
        cells = tr.find_all('td', recursive=False)
        if len(cells) != 3:
            raise ValueError('商品表格不再是三欄')
        number, name, price = [c.get_text(' ', strip=True) for c in cells]
        if not number or not name:
            raise ValueError('商品編號或名稱缺失')
        rows.append(dict(zip(FIELDS, [number, name, price.replace(',', '')])))
    return rows


def validate_all(rows, expected):
    ids = [row['商品編號'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('商品編號重複，可能讀到同一頁')
    if len(rows) != expected:
        raise ValueError('擷取筆數與來源商品總數不同')


def run(job, args):
    driver = make_browser(args)
    all_rows, page_counts = [], []
    try:
        driver.get(URL)
        job.sources.append(URL)
        wait = WebDriverWait(driver, 25)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, '#table-body tr'))
        job.capture(driver, 'first_page.png')
        page = 1
        while True:
            rows = parse_products(driver.page_source)
            if not rows:
                raise SourceChanged('分頁沒有商品，不視為正常結束')
            if {r['商品編號'] for r in rows} & {r['商品編號'] for r in all_rows}:
                raise SourceChanged('翻頁後商品編號重複，停止以免假完成')
            job.save_csv(f'NBA_Products{page}.csv', FIELDS, rows)
            all_rows.extend(rows)
            page_counts.append(len(rows))
            print(f'儲存頁面: {page}', flush=True)
            next_buttons = driver.find_elements(By.CSS_SELECTOR, 'button.nextbtn')
            if not next_buttons:
                break
            if page >= 100:
                raise SourceChanged('達到 100 頁保護上限，已保存部分資料')
            previous = rows[0]['商品編號']
            next_buttons[0].click()
            wait.until(lambda d: d.find_element(By.CSS_SELECTOR, '#table-body tr td').text != previous)
            page += 1
        job.capture(driver, 'last_page.png')
        # 擷取透過可見 DOM；來源陣列只用於總數交叉驗證。
        expected = driver.execute_script('return tableData.length')
        validate_all(all_rows, expected)
        job.save_text('pagination.json', json.dumps({'pages': page, 'rows_per_page': page_counts,
                      'source_total': expected, 'unique_ids': len({r['商品編號'] for r in all_rows})}, indent=2))
        return {'status': 'passed', 'note': f'{page} 頁、{len(all_rows)} 筆，已核對商品唯一性與來源總數'}
    finally:
        close_browser(driver, args)


if __name__ == '__main__':
    run_cli(11, run)
