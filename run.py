"""
用題號執行某一題（一次只執行一題）
================================================
用法
    python run.py 5     執行第 5 題（等同 python 第05題_台北票房排行榜/main.py）
    python run.py       先列出所有題目，再輸入要執行的題號
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def list_questions():
    """找出所有「第NN題_xxx」資料夾，回傳 {題號: 資料夾}。"""
    questions = {}
    for folder in sorted(ROOT.glob("第*題_*")):
        number = int(folder.name[1:3])  # 「第05題_…」→ 5
        questions[number] = folder
    return questions


def main():
    questions = list_questions()

    if len(sys.argv) > 2:
        raise SystemExit("一次只能執行一題，例如：python run.py 5")
    if len(sys.argv) == 2:
        answer = sys.argv[1]
    else:
        for number, folder in questions.items():
            print(f"{number:>2}. {folder.name}")
        answer = input("\n請輸入要執行的題號：").strip()

    if not answer.isdigit() or int(answer) not in questions:
        raise SystemExit(f"沒有第 {answer} 題，請輸入 1～{max(questions)} 的題號。")

    script = questions[int(answer)] / "main.py"
    print(f"執行：{script.parent.name}/main.py\n", flush=True)
    # sys.executable：用跟 run.py 同一個 Python（同一個虛擬環境）執行
    process = subprocess.Popen([sys.executable, str(script)])
    while True:
        try:
            sys.exit(process.wait())
        except KeyboardInterrupt:
            # 按 Ctrl+C 時題目程式也會收到，讓它自己收尾（先存已抓到的資料、關掉 Chrome），這裡繼續等它結束。
            # 不用 subprocess.run：它只給題目程式 0.25 秒就強制關掉，來不及存檔。
            continue


if __name__ == "__main__":
    main()
