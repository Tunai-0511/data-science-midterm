"""原題 3：下載並驗證健保腸病毒就診資料。"""
import csv
import io

from support import SourceChanged, run_cli


URL = "https://od.cdc.gov.tw/eic/NHI_EnteroviralInfection.csv"
FILENAME = "NHI_EnteroviralInfection.csv"
REQUIRED_FIELDS = ["年", "週", "就診類別", "年齡別", "縣市", "腸病毒健保就診人次", "健保就診總人次"]


def parse_dataset(data):
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise SourceChanged("政府資料集不是預期的 UTF-8 CSV") from None
    reader = csv.DictReader(io.StringIO(text))
    fields = list(reader.fieldnames or [])
    if not set(REQUIRED_FIELDS).issubset(fields):
        raise SourceChanged("政府資料集缺少預期欄位，或下載內容不是 CSV")
    rows = list(reader)
    if not rows:
        raise SourceChanged("政府資料集沒有資料列")
    return fields, rows


def run(job, args):
    response = job.fetch(URL, name="source_NHI_EnteroviralInfection.csv")
    fields, rows = parse_dataset(response.content)
    job.save_csv(FILENAME, fields, rows)
    return {"status": "passed", "note": f"已驗證 {len(fields)} 個原始欄位與 {len(rows)} 筆資料；最終 CSV 正規化為 UTF-8 BOM。", "rows": len(rows)}


if __name__ == "__main__":
    run_cli(3, run)
