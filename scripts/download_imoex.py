import csv
import math
from collections import Counter
from datetime import date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DATE_FROM = date(2018, 1, 1)
DATE_TO = date(2026, 11, 2)
COLUMNS = ["TRADEDATE", "SECID", "CLOSE"]

url = (
    "https://iss.moex.com/iss/history/engines/stock/"
    "markets/index/securities/IMOEX.json"
)
params = {
    "from": DATE_FROM.isoformat(),
    "till": DATE_TO.isoformat(),
    "iss.meta": "off",
    "iss.only": "history,history.cursor",
    "history.columns": ",".join(COLUMNS),
}

retry = Retry(
    total=2,
    backoff_factor=1,
    status_forcelist=(429, 500, 502, 503, 504),
)
rows = []
dates = []
total = None

with requests.Session() as session:
    session.mount("https://", HTTPAdapter(max_retries=retry))

    while total is None or len(rows) < total:
        start = len(rows)
        print(f"Запрашиваем страницу start={start}…", flush=True)
        response = session.get(url, params={**params, "start": start}, timeout=(10, 30))
        response.raise_for_status()
        data = response.json()

        history = data["history"]
        if history["columns"] != COLUMNS:
            raise ValueError(f"Неожиданные столбцы: {history['columns']}")

        cursor = data["history.cursor"]
        cursor_row, = cursor["data"]
        page_info = dict(zip(cursor["columns"], cursor_row, strict=True))
        page_total = page_info["TOTAL"]
        if total is None:
            total = page_total

        page = history["data"]
        expected_size = min(page_info["PAGESIZE"], total - start)
        if (
            page_info["INDEX"] != start
            or page_total != total
            or not page
            or len(page) != expected_size
        ):
            raise ValueError(f"Некорректная страница start={start}: {page_info}")

        for raw_date, index_code, close in page:
            trade_date = date.fromisoformat(raw_date)
            if not DATE_FROM <= trade_date <= DATE_TO:
                raise ValueError(f"Дата вне диапазона: {raw_date}")
            if dates and trade_date <= dates[-1]:
                raise ValueError(f"Дубликат или нарушение порядка: {raw_date}")
            if index_code != "IMOEX":
                raise ValueError(f"Неожиданный код индекса: {index_code}")
            if type(close) not in (int, float) or not math.isfinite(close) or close <= 0:
                raise ValueError(f"Некорректное закрытие за {raw_date}: {close}")
            dates.append(trade_date)

        rows.extend(page)

expected_first_rows = [
    ["2018-01-03", "IMOEX", 2152.97],
    ["2018-01-04", "IMOEX", 2197.6],
    ["2018-01-05", "IMOEX", 2207.41],
]
if len(rows) != total or rows[:3] != expected_first_rows:
    raise ValueError("Не совпало число строк ISS или первые три контрольные записи")

output = Path(__file__).resolve().parents[1] / "data" / "raw" / "imoex_daily.csv"
output.parent.mkdir(parents=True, exist_ok=True)
temporary = output.with_suffix(".csv.tmp")

try:
    with temporary.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["trade_date", "index_code", "close"])
        writer.writerows(rows)
    temporary.replace(output)
finally:
    temporary.unlink(missing_ok=True)

print(f"Строк: {len(rows)} из {total}")
print(f"Диапазон: {dates[0]} — {dates[-1]}")
print("Строки по годам:", dict(sorted(Counter(day.year for day in dates).items())))
print(f"Сохранено: {output}")
