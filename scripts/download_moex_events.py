"""Скачивает из MOEX ISS справочные данные для проверки выборки.

1. data/raw/splits.csv            — официальный список сплитов и консолидаций (statistics/engines/stock/splits);
2. data/raw/imoex_composition.csv — состав IMOEX с весами на первый торговый день каждого месяца
                                    (statistics/engines/stock/markets/index/analytics/IMOEX).
Токен MOEX_TOKEN берется из .env в корне репозитория или на уровень выше.
"""
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ISS = "https://iss.moex.com/iss/"
START = "2018-01-01"


def load_token() -> str:
    for env in (ROOT / ".env", ROOT.parent / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("MOEX_TOKEN"):
                    return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit("MOEX_TOKEN не найден в .env")


session = requests.Session()
session.headers["Authorization"] = f"Bearer {load_token()}"


def iss(path: str, table: str, **params) -> pd.DataFrame:
    r = session.get(ISS + path, params={"iss.meta": "off", **params}, timeout=30)
    r.raise_for_status()
    t = r.json()[table]
    return pd.DataFrame(t["data"], columns=t["columns"])


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)

    splits = iss("statistics/engines/stock/splits.json", "splits")
    splits.to_csv(RAW / "splits.csv", index=False)
    print(f"splits.csv: {len(splits)} событий")

    frames = []
    for month in pd.date_range(START, pd.Timestamp.today(), freq="MS"):
        for shift in range(10):  # 1-е число может быть выходным: берем первый торговый день месяца
            day = month + pd.Timedelta(days=shift)
            a = iss("statistics/engines/stock/markets/index/analytics/IMOEX.json", "analytics",
                    date=day.strftime("%Y-%m-%d"), limit=100)
            time.sleep(0.2)
            if not a.empty:
                frames.append(a[["tradedate", "ticker", "shortnames", "weight"]])
                break
    comp = pd.concat(frames).drop_duplicates(["tradedate", "ticker"])
    comp.to_csv(RAW / "imoex_composition.csv", index=False)
    print(f"imoex_composition.csv: {comp['tradedate'].nunique()} дат, {comp['ticker'].nunique()} тикеров")


if __name__ == "__main__":
    main()
