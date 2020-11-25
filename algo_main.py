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

TRADE_QUANTITY = 0.5

RSI_PERIOD = 14
RSI_OVERBOUGHT = 63
RSI_OVERSOLD = 37

BINANCE_SOCKET = f"wss://stream.binance.com:9443/ws/{TRADE_SYMBOL.lower()}@kline_1m"

START_DATETIME = str(datetime.now())

in_long_position = False
closes_dict = {}
cur_closes_dict_len = len(closes_dict)


# Loading API key and secret, which are saved in an external file
with open("../config/algo_config.json") as f:
    config_dict = json.load(f)

client = Client(config_dict['api_key'], config_dict['api_sec'])


def on_open(ws):
    print("Opened connection")

def on_close(ws):
    print("Closed connection")

def on_message(ws, message):
    global cur_closes_dict_len
    try:
        on_message_helper(message)

    except Exception as e:
        print(e)


def on_message_helper(message):
    global cur_closes_dict_len
    message_dict = json.loads(message)

    ticker = message_dict['s']

    unix_ts = int(message_dict['E'])/1000
    ts = datetime.utcfromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')

    close_price = float(message_dict['k']['c'])

    closes_dict[ts[:-3]] = close_price

    print(f"{ticker} price at {ts}: {close_price}")

    if len(closes_dict) > cur_closes_dict_len:
        closes_arr = np.array(list(closes_dict.values())[:-1])
        on_candle_close(closes_arr)



def on_candle_close(closes_arr):
    global cur_closes_dict_len
    
    cur_closes_dict_len = len(closes_dict)

    print("\nClosing prices:", closes_arr, "\n")

    # We need to ensure we are not considering the most recent price, as this will be the beginning
    # of the next candle - we must look at the previous price
    if len(closes_dict) >= 2:

        trade_executed = None

        # RSI can only be calculated on the (RSI_PERIOD+1)th closing price
        if len(closes_arr) >= RSI_PERIOD + 1: #####+2
            trade_executed = consider_trade(closes_arr)

        col_names = ["datetime_collected", "datetime", "price", "trade_made"]
        row = [START_DATETIME,
                    list(closes_dict.keys())[-2],
                    list(closes_dict.values())[-2],
                    trade_executed
                    ]

        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_data.csv", col_names, row)


def consider_trade(closes_arr):    
    global in_long_position

    rsi = talib.RSI(closes_arr, RSI_PERIOD)
    last_rsi = rsi[-2]
    print(f"All RSIs calculated so far: {rsi}\n")

    if (last_rsi >= RSI_OVERBOUGHT) and (closes_arr[-1] < closes_arr[-2]):
        if in_long_position:
            print("Attempting to sell...")
            order_succeeded = order(TRADE_SYMBOL, enums.SIDE_SELL, enums.ORDER_TYPE_MARKET, TRADE_QUANTITY, closes_arr, last_rsi)
            if order_succeeded:
                in_long_position = False
                trade_executed = "sell"
                return trade_executed
        else:
            print("Selling opportunity, but not in long position\n")

    if (last_rsi <= RSI_OVERSOLD) and (closes_arr[-1] > closes_arr[-2]):
        if in_long_position:
            print("Buying opportunity, but already in a position\n")
        else:
            print("Attempting to buy...")
            order_succeeded = order(TRADE_SYMBOL, enums.SIDE_BUY, enums.ORDER_TYPE_MARKET, TRADE_QUANTITY, closes_arr, last_rsi)
            if order_succeeded:
                in_long_position = True
                trade_executed = "buy"
                return trade_executed
    
    return None

def order(symbol, side, order_type, quantity, closes_arr, last_rsi):
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol,
                                    side=side,
                                    type=order_type,
                                    quantity=quantity)
        print("Order successful:", order, "\n\n")

        # Logging executed price and quantity
        try:
            actual_price = order['fills'][0]['price']
            actual_quantity = order['fills'][0]['qty']
            commission = order['fills'][0]['commission']
        except Exception as e:
            actual_price = ""
            actual_quantity = ""
            commission = ""
            print("Error saving to order details logs:", e)

        # Logging balances of both assets traded
        try:
            balance_1 = float(client.get_asset_balance(asset=ASSET_1)['free'])
            usd_price_1 = float(client.get_avg_price(symbol=f'{ASSET_1}USDT')['price'])
            balance_2 = float(client.get_asset_balance(asset=ASSET_2)['free'])
            usd_price_2 = float(client.get_avg_price(symbol=f'{ASSET_2}USDT')['price'])
            balance_usd = balance_1*usd_price_1 + balance_2*usd_price_2
        except Exception as e:
            balance_1 = ""
            usd_price_1 = ""
            balance_2 = ""
            usd_price_2 = ""
            balance_usd = ""
            print("Error saving balances to logs:", e)

        try:
            total_balance_btc = float(balance_1)*float(actual_price) + float(balance_2)
        except Exception as e:
            total_balance_btc = ""
            print("Error getting BTC balance:", e)


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
                        "total_balance_btc",
                        "last RSI"]
        row = [START_DATETIME,
                datetime.now(),
                symbol,
                side,
                order_type,
                quantity,
                closes_arr[-2],
                actual_price,
                actual_quantity,
                commission,
                balance_1,
                balance_2,
                balance_usd,
                total_balance_btc,
                last_rsi]
        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_trades_log.csv", col_names, row)
    
    except Exception as e:
        print("Order failed:", e, "\n\n")
        return False

    return True


binance_ws = websocket.WebSocketApp(BINANCE_SOCKET,
                                    on_open=on_open,
                                    on_close=on_close,
                                    on_message=on_message)
binance_ws.run_forever()