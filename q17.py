"""第 17 題：本人啟動後自動填入登入表單，擷取 PDF 指定兩個提示區塊。

密碼僅於本機隱藏輸入，不寫入檔案；2FA、通行金鑰及驗證由本人處理。
未驗證私人帳號端到端流程；若舊版卡片不存在，會標示部分完成。
"""
import getpass
import json
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from support import NeedsUser, make_browser, pause_for_user, run_cli

TARGETS = {'1': ('create your first project', '建立您的第一個專案', '建立第一個專案'),
           '2': ('updates to your homepage feed', '首頁動態消息更新', '首頁摘要更新')}


def parse_panels(html):
    soup = BeautifulSoup(html, 'html.parser')
    result = {}
    for number, phrases in TARGETS.items():
        for heading in soup.select('h1,h2,h3,h4,h5,strong'):
            text = heading.get_text(' ', strip=True).lower()
            if not any(phrase in text for phrase in phrases):
                continue
            # 只取標題緊接的說明段落，絕不輸出整個祖先容器或私人兄弟節點。
            following = heading.find_next_sibling()
            if following is not None and following.name == 'p':
                result[number] = heading.get_text(' ', strip=True) + ' ' + following.get_text(' ', strip=True)
            break
    return result


def completion_status(panels, password_verified):
    return 'passed' if set(panels) == {'1', '2'} and password_verified else 'partial'


def logged_in(driver):
    location = urlsplit(driver.current_url)
    if location.scheme != 'https' or location.hostname != 'github.com':
        return False
    elements = driver.find_elements(By.CSS_SELECTOR, 'meta[name="user-login"]')
    return bool(elements and elements[0].get_attribute('content'))


def password_stage_reached(driver):
    if logged_in(driver):
        return True
    location = urlsplit(driver.current_url)
    if location.scheme != 'https' or location.hostname != 'github.com':
        return False
    return location.path.startswith('/sessions/two-factor') and bool(driver.find_elements(
        By.CSS_SELECTOR, 'input[autocomplete="one-time-code"],input[name="app_otp"],input[name="otp"]'))


def run(job, args):
    if not args.interactive:
        raise NeedsUser('需要本人啟動 GitHub 登入：python q17.py --interactive；勿將帳密貼到聊天')
    driver = make_browser(args)
    try:
        driver.get('https://github.com/login')
        wait = WebDriverWait(driver, 25)
        if urlsplit(driver.current_url).hostname != 'github.com' or not driver.current_url.startswith('https://'):
            raise NeedsUser('目前不是 GitHub 的 HTTPS 登入頁；不輸入或提交帳密')
        # 留空帳號可改由本人使用通行金鑰／SSO；該路徑會標明非自動密碼登入。
        username = input('GitHub 帳號（只在本機輸入；留空改為手動登入）：').strip()
        password_verified = False
        if username:
            password = getpass.getpass('GitHub 密碼（隱藏輸入，不儲存）：')
            if not password:
                raise NeedsUser('未提供密碼；沒有提交登入表單')
            user_field = wait.until(lambda d: d.find_element(By.ID, 'login_field'))
            user_field.clear()
            user_field.send_keys(username)
            driver.find_element(By.ID, 'password').send_keys(password)
            password = None
            driver.find_element(By.CSS_SELECTOR, 'input[name="commit"],button[type="submit"]').click()
            try:
                password_verified = bool(WebDriverWait(driver, 8).until(password_stage_reached))
            except TimeoutException:
                # 無法證明密碼階段成功時，即使之後手動登入，也不宣稱自動登入完成。
                password_verified = False
        if not logged_in(driver):
            pause_for_user(driver, args, '請自行完成 GitHub 登入及必要的 2FA／裝置驗證，然後停留在 GitHub 首頁。')
        if not logged_in(driver):
            raise NeedsUser('尚未確認登入成功；未保存登入頁或帳密')
        driver.get('https://github.com/')
        wait.until(lambda d: d.find_elements(By.TAG_NAME, 'main'))
        panels = parse_panels(driver.page_source)
        job.sources.append('https://github.com/')
        for key, text in panels.items():
            job.save_text(f'github_panel_{key}.txt', text + '\n')
            print(f'視窗 {key}: {text}')
        missing = sorted({'1', '2'} - set(panels))
        job.save_text('panel_status.json', json.dumps({'found': sorted(panels), 'missing': missing,
                      'automatic_password_stage_verified': password_verified,
                      'note': '只保存指定提示區塊；未保存完整私人首頁、密碼、cookie 或登入頁'}, ensure_ascii=False, indent=2))
        if missing:
            return {'status': 'partial', 'note': f'已登入，但目前帳號／新版首頁未找到 PDF 視窗 {",".join(missing)}；未用其他區塊替代'}
        if not password_verified:
            return {'status': completion_status(panels, password_verified), 'note': '已擷取兩個視窗；本次需手動登入或未能驗證自動密碼階段，未宣稱自動登入完成'}
        return {'status': completion_status(panels, password_verified), 'note': '已驗證自動密碼階段並擷取兩個指定視窗；如有額外驗證由本人完成'}
    finally:
        driver.quit()


if __name__ == '__main__':
    run_cli(17, run)
