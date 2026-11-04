"""Строит universe.csv: состав IMOEX + сектор, тип акции (обыкновенная/привилегированная)."""

from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent.parent  # корень репозитория
ISS = "https://iss.moex.com/iss/"
BOARD = "TQBR"

# Отраслевые индексы MOEX -> сектор. Порядок = приоритет, если тикер в нескольких.
SECTOR_INDEXES = {
    "MOEXOG": "нефть и газ",
    "MOEXEU": "электроэнергетика",
    "MOEXTN": "транспорт",
    "MOEXMM": "металлы и добыча",
    "MOEXFN": "финансы",
    "MOEXCN": "потребительский сектор",
    "MOEXCH": "химия и нефтехимия",
    "MOEXRE": "строительство и недвижимость",
    "MOEXTL": "телекоммуникации",
    "MOEXIT": "информационные технологии",
}
# Бумаги IMOEX, не входящие ни в один отраслевой индекс (определено вручную)
MANUAL_SECTOR = {"AFKS": "финансы"}  # АФК «Система» — инвестиционный холдинг


def load_token() -> str:
    env = BASE / ".env"
    if not env.exists():
        env = BASE.parent / ".env"
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


def index_members(code: str) -> pd.DataFrame:
    return iss(
        f"statistics/engines/stock/markets/index/analytics/{code}.json",
        "analytics",
        limit=100,
    )


def main() -> None:
    imoex = index_members("IMOEX")
    snapshot = imoex["tradedate"].max()
    imoex = imoex[imoex["tradedate"] == snapshot]
    tickers = sorted(imoex["ticker"])

    sector = {}
    for code, name in reversed(
        list(SECTOR_INDEXES.items())
    ):  # высший приоритет пишется последним
        for t in index_members(code)["ticker"]:
            sector[t] = name
    sector.update({t: s for t, s in MANUAL_SECTOR.items() if t not in sector})

    board = iss(
        f"engines/stock/markets/shares/boards/{BOARD}/securities.json",
        "securities",
        securities=",".join(tickers),
    )
    board = board.set_index("SECID")
    missing = [t for t in tickers if t not in board.index]
    if missing:
        raise SystemExit(f"нет на {BOARD}: {missing}")

    df = pd.DataFrame(
        {
            "secid": tickers,
            "shortname": [board.at[t, "SHORTNAME"] for t in tickers],
            "boardid": BOARD,
            "sector": [sector.get(t) for t in tickers],
            # SECTYPE: 1 — обыкновенная, 2 — привилегированная
            "is_pref": [int(str(board.at[t, "SECTYPE"]) == "2") for t in tickers],
            "snapshot_date": snapshot,
        }
    )
    out = BASE / "config" / "universe.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"записано {len(df)} строк -> {out}")


if __name__ == "__main__":
    main()
