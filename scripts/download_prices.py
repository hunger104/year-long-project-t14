import requests
import pandas as pd


def fetch_share_prices(ticker: str, start_date: str, end_date: str, limit: int=100) -> list[dict]:
    """Загружает исторические торговые данные с MOEX ISS API.

    Args:
        ticker (str): Тикер компании
        start_date (str): Начальная дата формата YYYY-MM-DD
        end_date (str): Конечная дата формата YYYY-MM-DD
        limit (int): Лимит на загрузку строк в одном прогоне цикла. Defaults to 100.

    Returns:
        list[dict]: Возвращает список словарей, один словарь = одна запись о торгах за определенную дату.
    """

    url = f'https://iss.moex.com/iss/history/engines/stock/markets/shares/boards/TQBR/securities/{ticker}.json'
    all_rows = []
    start = 0
    params = {
        "from": start_date,
        "till": end_date,
        "limit": limit,
        "start": start
    }

    while True:

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status() # Вызовет исключение при HTTP-статусах 4хх и 5хх
            data = response.json()
            rows = data['history']['data'] # строки данных за торговый день конкретной акции
            columns = data['history']['columns'] # названия колонок к этим данным
            rows_col = [dict(zip(columns, row)) for row in rows] # делаем список словарей
            all_rows.extend(rows_col) # Добавляем построчно в общий список
        except requests.exceptions.RequestException as err:
            print("Ошибка сетевой загрузки данных!")
            raise

        params['start'] += limit

        if params['start'] >= data['history.cursor']['data'][0][1]: # если start >= total (всего доступных строк по запросу)
            break

    return all_rows




def prepare_share_prices(data: list[dict]) -> pd.DataFrame:
    """Преобразовывает данные в конечную таблицу

    Args:
        data (list[dict]): Поступающие данные

    Returns:
        pd.DataFrame: Итоговый форматированный датафрейм
    """
    if not data:
        df = pd.DataFrame(columns=["trade_date", "boardid",
                                   "secid", "open",
                                   "high", "low",
                                   "close", "volume",
                                   "value", "numtrades"
                                   ])
    else:
        df = pd.DataFrame(data)
        df = df[['TRADEDATE', 'BOARDID', 'SECID', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'VALUE', 'NUMTRADES']]
        df = df.rename(columns={'TRADEDATE': "trade_date",
                                'BOARDID': "boardid",
                                'SECID': "secid",
                                'OPEN': "open",
                                'HIGH': "high",
                                'LOW': "low",
                                'CLOSE': "close",
                                'VOLUME': "volume",
                                'VALUE': "value",
                                'NUMTRADES': "numtrades"
                                })

    return df


if __name__ == "__main__":
    tickers = ["SBER", "GAZP", "LKOH"]
    df_data = []

    for ticker in tickers:
        data = fetch_share_prices(ticker, "2026-10-01", "2026-10-10")
        df = prepare_share_prices(data)
        df_data.append(df)

    df_data = pd.concat(df_data, ignore_index=True)
    df_data = df_data.sort_values(
        by=["secid", "trade_date"]
    )

    dupl = df_data.duplicated(subset=["trade_date", "boardid", "secid"]).sum() # Проверяем DataFrame на дубликаты
    if dupl > 0:
        print(f"В DateFrame есть {dupl} дубликатов по ключу trade_date + boardid + secid.")

    # Сохранение .csv
    df_data.to_csv(path_or_buf='./data/raw/prices_daily.csv', index=False, encoding='UTF-8')
    print(f"В файле prices_daily.csv {len(df_data)} строк")

