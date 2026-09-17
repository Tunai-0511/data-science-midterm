"""第 10 題：PTT 八卦板列表；年齡確認必須由本人操作。"""
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from support import NeedsUser, make_browser, pause_for_user, run_cli

URL = 'https://www.ptt.cc/bbs/Gossiping/index.html'


def parse_posts(html):
    soup = BeautifulSoup(html, 'html.parser')
    rows, skipped = [], 0
    for card in soup.select('.r-ent'):
        title = card.select_one('.title a')
        if not title or not title.get('href'):
            skipped += 1
            continue
        author = card.select_one('.author')
        rows.append({'網址': urljoin(URL, title['href']), '標題': title.get_text(' ', strip=True),
                     '作者': author.get_text(strip=True) if author else ''})
    return rows, skipped


def completion_result(count, skipped, confirmed):
    if confirmed:
        return {'status': 'passed', 'note': f'目前列表 {count} 筆；略過 {skipped} 筆無連結文章；年齡確認由本人完成'}
    return {'status': 'partial', 'note': f'目前列表 {count} 筆；略過 {skipped} 筆無連結文章；本次未出現分級頁，未實測原題分級確認步驟'}


def run(job, args):
    if not args.interactive:
        raise NeedsUser('PTT 分級頁須由本人確認；執行 python q10.py --interactive')
    driver = make_browser(args)
    try:
        driver.get(URL)
        job.sources.append(URL)
        WebDriverWait(driver, 25).until(lambda d: d.find_elements(By.CSS_SELECTOR, '.r-ent, form[action*="/ask/over18"]'))
        confirmed = False
        if driver.find_elements(By.CSS_SELECTOR, 'form[action*="/ask/over18"]'):
            # 不點擊年齡按鈕，不注入 over18 cookie，也不替本人宣告年齡。
            pause_for_user(driver, args, '請自行閱讀並完成適用的 PTT 年齡確認，且停留在八卦板列表。')
            confirmed = True
        WebDriverWait(driver, 25).until(lambda d: d.find_elements(By.CSS_SELECTOR, '.r-ent'))
        if '/bbs/Gossiping/' not in driver.current_url:
            raise NeedsUser('目前不是八卦板列表，請重新執行並停留在指定頁面')
        rows, skipped = parse_posts(driver.page_source)
        job.save_csv('ptt_gossiping.csv', ['網址', '標題', '作者'], rows)
        job.save_text('page_title.txt', driver.title + '\n')
        job.capture(driver)
        print(driver.title)
        for row in rows:
            print(row['網址'], row['標題'], row['作者'], sep='\n')
        return completion_result(len(rows), skipped, confirmed)
    finally:
        driver.quit()


if __name__ == '__main__':
    run_cli(10, run)
