import numpy as np
import pandas as pd
from datetime import datetime
import websocket
import json
import talib
from algo_utils import append_data


BINANCE_SOCKET_BASE = "wss://stream.binance.com:9443"
BINANCE_SOCKET = BINANCE_SOCKET_BASE + "/ws/ethusdt@kline_1m"

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
TRADESYMBOL = "ETHUSDT"
TRADE_QUANTITY = 0.01


with open("../config/algo_config.json") as f:
    config_dict = json.load(f)

def on_open(ws):
    print("Opened connection")

x = np.array([1, 2, 3])


def on_close(ws):
    print("Closed connection")


start_datetime = str(datetime.now())
closes_dict = {}
cur_len_closes_dict = 0

def on_candle_close(closes_arr):
    global closes_dict, cur_len_closes_dict
    
    cur_len_closes_dict = len(closes_dict)

    print("Closing prices:", closes_arr)

    # We need to ensure we are not considering the most recent price, as this will be the beginning
    # of the next candle - we must look at the previous price
    if len(closes_dict) >= 2:
        col_names = ["datetime_collected", "datetime", "price"]
        row_raw = [start_datetime,
                    list(closes_dict.keys())[-2],
                    list(closes_dict.values())[-2]
                    ]
        row = [str(x) for x in row_raw]

        append_data(f"../Trading CSVs/{TRADESYMBOL}_data.csv",
                    ", ".join(col_names),
                    ", ".join(row)
                    )
    
        rsi_calc(closes_arr)


def rsi_calc(closes_arr):    
    rsi = talib.RSI(closes_arr, RSI_PERIOD)
    last_rsi = rsi[-1]
    print(f"All RSIs calculated so far: {rsi}")

    if last_rsi > RSI_OVERBOUGHT:
        print("Sell!")
    if last_rsi < RSI_OVERSOLD:
        print("Buy!")


def on_new_message(message):
    global closes_dict, cur_len_closes_dict
    message_dict = json.loads(message)

    ticker = message_dict['s']

    unix_ts = int(message_dict['E'])/1000
    ts = datetime.utcfromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')

    close_price = float(message_dict['k']['c'])

    closes_dict[ts[:-3]] = close_price

    if len(closes_dict) > cur_len_closes_dict:
        closes_arr = np.array(list(closes_dict.values())[:-1])
        print(closes_arr)
        on_candle_close(closes_arr)

        if len(closes_dict) >= RSI_PERIOD:
                pass

    print(f"{ticker} price at {ts}: {close_price}.")


def on_message(ws, message):
    global closes_dict, cur_len_closes_dict, TRADESYMBOL, start_datetime
    try:
        on_new_message(message)

    except Exception as e:
        print(e)


binance_ws = websocket.WebSocketApp(BINANCE_SOCKET,
                                    on_open=on_open,
                                    on_close=on_close,
                                    on_message=on_message)
binance_ws.run_forever()