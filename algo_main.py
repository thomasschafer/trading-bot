import numpy as np
import pandas as pd
from datetime import datetime
import websocket
import json
import talib
from binance.client import Client
from binance import enums
from algo_utils import append_data


ASSET_1 = "BNB" # Ticker for asset bought
ASSET_2 = "BTC" # Ticker for asset sold
TRADE_SYMBOL = ASSET_1 + ASSET_2

TRADE_QUANTITY = 0.3

RSI_PERIOD = 14
RSI_OVERBOUGHT = 63
RSI_OVERSOLD = 37

BINANCE_SOCKET = f"wss://stream.binance.com:9443/ws/{TRADE_SYMBOL.lower()}@kline_1m"

in_long_position = False
start_datetime = str(datetime.now())
closes_dict = {}
cur_len_closes_dict = 0


# Loading API key and secret, which are saved in an external file
with open("../config/algo_config.json") as f:
    config_dict = json.load(f)

client = Client(config_dict['api_key'], config_dict['api_sec'])


def order(symbol, side, order_type, quantity, last_rsi):
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol,
                                    side=side,
                                    type=order_type,
                                    quantity=quantity)
        print("Order successful:", order, "\n\n")

        # Logging executed price and quantity
        try:
            # order_formatted = order.replace("'", '"')
            # order_dict = json.loads(order_formatted)
            order_dict = order

            actual_price = order_dict['fills'][0]['price']
            actual_quantity = order_dict['fills'][0]['qty']
            commission = order_dict['fills'][0]['commission']
        except Exception as e:
            actual_price = "Error"
            actual_quantity = "Error"
            commission = "Error"
            print("Error saving to logs:", e)

        # Logging balances of both assets traded
        try:
            balance_1 = client.get_asset_balance(asset=ASSET_1)['free']
            usd_price_1 = client.get_avg_price(symbol=f'{ASSET_1}USDT')['price']
            balance_2 = client.get_asset_balance(asset=ASSET_2)['free']
            usd_price_2 = client.get_avg_price(symbol=f'{ASSET_2}USDT')['price']
            balance_usd = float(balance_1)*float(usd_price_1) + float(balance_2)*float(usd_price_2)
        except Exception as e:
            balance_1 = "Error"
            usd_price_1 = "Error"
            balance_2 = "Error"
            usd_price_2 = "Error"
            balance_usd = "Error"
            print("Error saving to logs:", e)


        col_names = ["collection_started_datetime",
                        "order_placed_datetime",
                        "ticker",
                        "side", 
                        "order_type",
                        "quantity_attempted",
                        "expected_price",
                        "actual_price",
                        "actual_quantity",
                        "commission",
                        f"{ASSET_1}_balance",
                        f"{ASSET_2}_balance",
                        "total_balance_usd",
                        "last RSI"]
        row = [start_datetime,
                datetime.now(),
                symbol,
                side,
                order_type,
                quantity,
                list(closes_dict.values())[-2],
                actual_price,
                actual_quantity,
                commission,
                balance_1,
                balance_2,
                balance_usd,
                last_rsi]
        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_trades_log.csv", col_names, row)
    
    except Exception as e:
        print("Order failed:", e, "\n\n")
        return False

    return True


def on_open(ws):
    print("Opened connection")

def on_close(ws):
    print("Closed connection")

def on_candle_close(closes_arr):
    global closes_dict, cur_len_closes_dict
    
    cur_len_closes_dict = len(closes_dict)

    print("\nClosing prices:", closes_arr, "\n")

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
    print(f"All RSIs calculated so far: {rsi}\n")

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

    print(f"{ticker} price at {ts}: {close_price}")

    if len(closes_dict) > cur_len_closes_dict:
        closes_arr = np.array(list(closes_dict.values())[:-1])
        on_candle_close(closes_arr)


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