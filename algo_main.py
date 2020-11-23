import numpy as np
import pandas as pd
from datetime import datetime
import websocket
import json
import talib
from binance.client import Client
from binance import enums
from algo_utils import append_data


BINANCE_SOCKET_BASE = "wss://stream.binance.com:9443"
BINANCE_SOCKET = BINANCE_SOCKET_BASE + "/ws/bnbbtc@kline_1m"

RSI_PERIOD = 14
RSI_OVERBOUGHT = 69
RSI_OVERSOLD = 31
TRADE_SYMBOL = "BNBBTC"
TRADE_QUANTITY = 0.3

in_long_position = False
start_datetime = str(datetime.now())
closes_dict = {}
cur_len_closes_dict = 0


# Loading API key and secret, which are saved in an external file
with open("../config/algo_config.json") as f:
    config_dict = json.load(f)

client = Client(config_dict['api_key'], config_dict['api_sec'])


def order(symbol, side, order_type, quantity, last_rsi):
    # try:
    #     print("Sending order")
    #     order = client.create_order(symbol=symbol,
    #                                 side=side,
    #                                 type=order_type,
    #                                 quantity=quantity)
    #     print(order)
    
    # except Exception as e:
    #     print("Order failed:", e)
    #     return False

    print("Executing order...")

    col_names = ["collected_datetime", "order_placed_datetime", "ticker", "side", "order_type", "quantity", "details"]
    row = [start_datetime, datetime.now(), symbol, side, order_type, quantity, f"Last RSI: {last_rsi}"]
    append_data(f"../Trading CSVs/{TRADE_SYMBOL}_trades_log.csv", col_names, row)

    return True


def on_open(ws):
    print("Opened connection")

def on_close(ws):
    print("Closed connection")

def on_candle_close(closes_arr):
    global closes_dict, cur_len_closes_dict
    
    cur_len_closes_dict = len(closes_dict)

    print("Closing prices:", closes_arr)

    # We need to ensure we are not considering the most recent price, as this will be the beginning
    # of the next candle - we must look at the previous price
    if len(closes_dict) >= 2:
        col_names = ["datetime_collected", "datetime", "price"]
        row = [start_datetime,
                    list(closes_dict.keys())[-2],
                    list(closes_dict.values())[-2]
                    ]

        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_data.csv", col_names, row)

        # RSI can only be calculated on the (RSI_PERIOD+1)th closing price
        if len(closes_dict) >= RSI_PERIOD + 1:
            rsi_calc(closes_arr)


def rsi_calc(closes_arr):    
    global in_long_position

    rsi = talib.RSI(closes_arr, RSI_PERIOD)
    last_rsi = rsi[-1]
    print(f"All RSIs calculated so far: {rsi}")

    if last_rsi >= RSI_OVERBOUGHT:
        if in_long_position:
            print("Sell!")
            order_succeeded = order(TRADE_SYMBOL, enums.SIDE_SELL, enums.ORDER_TYPE_MARKET, TRADE_QUANTITY, last_rsi)
            if order_succeeded:
                in_long_position = False
        else:
            print("Overbought but nothing to do")

    if last_rsi <= RSI_OVERSOLD:
        if in_long_position:
            print("Oversold but nothing to do")
        else:
            print("Buy!")
            order_succeeded = order(TRADE_SYMBOL, enums.SIDE_BUY, enums.ORDER_TYPE_MARKET, TRADE_QUANTITY, last_rsi)
            if order_succeeded:
                in_long_position = True


def on_message_helper(message):
    global closes_dict, cur_len_closes_dict
    message_dict = json.loads(message)

    ticker = message_dict['s']

    unix_ts = int(message_dict['E'])/1000
    ts = datetime.utcfromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')

    close_price = float(message_dict['k']['c'])

    closes_dict[ts[:-3]] = close_price

    if len(closes_dict) > cur_len_closes_dict:
        closes_arr = np.array(list(closes_dict.values())[:-1])
        on_candle_close(closes_arr)

    print(f"{ticker} price at {ts}: {close_price}\n")


def on_message(ws, message):
    global closes_dict, cur_len_closes_dict, start_datetime
    try:
        on_message_helper(message)

    except Exception as e:
        print(e)


binance_ws = websocket.WebSocketApp(BINANCE_SOCKET,
                                    on_open=on_open,
                                    on_close=on_close,
                                    on_message=on_message)
binance_ws.run_forever()