"""
一次執行多題，最後列出每一題成功或失敗
================================================
用法
    python run_all.py           依序執行第 1～16 題
    python run_all.py 2 5 11    只執行指定的題號（第 17 題要登入 GitHub，請用這個方式單獨執行）

每一題都是獨立的程式（各資料夾的 main.py），這裡只是依序呼叫它們；
某一題失敗不會中斷，會接著跑下一題。
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent


def find_script(number):
    """依題號找到資料夾，例如 5 → 第05題_台北票房排行榜/main.py"""
    folder = next(ROOT.glob(f"第{number:02d}題_*"))
    return folder / "main.py"


def main():
    numbers = [int(arg) for arg in sys.argv[1:]] or list(range(1, 17))
    summary = []

    for number in numbers:
        script = find_script(number)
        print(f"\n{'=' * 60}\n第 {number} 題：{script.parent.name}\n{'=' * 60}", flush=True)
        start = time.time()
        # sys.executable：用跟 run_all.py 同一個 Python（同一個虛擬環境）執行
        result = subprocess.run([sys.executable, str(script)])
        summary.append((number, script.parent.name, result.returncode == 0, time.time() - start))

    print(f"\n{'=' * 60}\n執行結果\n{'=' * 60}")
    for number, name, ok, seconds in summary:
        print(f"第 {number:>2} 題  {'成功' if ok else '失敗'}  {seconds:5.1f} 秒  {name}")


if __name__ == "__main__":
    main()
