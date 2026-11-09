"""Скачивает дивиденды с dohod.ru для всех бумаг из config/universe.csv.

Результат: data/raw/dividends.csv (сырые данные, не правим).
Парсинг как в futures-calc: страница https://www.dohod.ru/ik/analytics/dividend/{ticker},
третья таблица левой колонки. Строки с пометкой "(прогноз)" сохраняются с is_forecast=1.
"""
import time
import warnings
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "config" / "universe.csv"
OUT = ROOT / "data" / "raw" / "dividends.csv"
URL = "https://www.dohod.ru/ik/analytics/dividend/{ticker}"


def parse_ticker(secid: str) -> list[dict]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = requests.get(URL.format(ticker=secid.lower()), verify=False, timeout=30)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")
    table = soup.select_one("#leftside-col > table:nth-of-type(3)")
    if table is None:
        return []
    rows = []
    for tr in table.find_all("tr")[1:]:
        td = [c.text.strip() for c in tr.find_all("td")]
        if len(td) < 4:
            continue
        rows.append({
            "secid": secid,
            "announce_date": td[0],
            "registry_close_date": td[1].split()[0],
            "is_forecast": int("прогноз" in td[1].lower()),
            "year_for_account": td[2],
            "div": td[3].split()[0],
        })
    return rows


def main() -> None:
    universe = pd.read_csv(UNIVERSE)
    rows, empty = [], []
    for secid in universe["secid"]:
        got = parse_ticker(secid)
        if not got:
            empty.append(secid)
        rows += got
        print(f"{secid}: {len(got)} строк")
        time.sleep(0.5)

    df = pd.DataFrame(rows)
    df["announce_date"] = pd.to_datetime(df["announce_date"], format="%d.%m.%Y", errors="coerce")
    df["registry_close_date"] = pd.to_datetime(df["registry_close_date"], format="%d.%m.%Y", errors="coerce")
    df["year_for_account"] = pd.to_numeric(df["year_for_account"], errors="coerce")
    df["div"] = pd.to_numeric(df["div"], errors="coerce")
    df = df.sort_values(["secid", "registry_close_date"]).reset_index(drop=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"\nСохранено {len(df)} строк в {OUT}")
    print("Без страницы/таблицы:", empty)


if __name__ == "__main__":
    main()
