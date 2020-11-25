# Core Python modules
from datetime import datetime
import json

# Binance modules
from binance.client import Client
from binance import enums

# Project modules
from utilities import append_data
from strategies import RSIWithBreakoutConfirmation

# Additional modules
import numpy as np
import pandas as pd
import websocket


ASSET_1 = "BNB" # Ticker for asset bought
ASSET_2 = "BTC" # Ticker for asset sold
TRADE_SYMBOL = ASSET_1 + ASSET_2

TRADE_QUANTITY = 0.2

RSI_PERIOD = 14
RSI_OVERBOUGHT = 63
RSI_OVERSOLD = 37

STOP_LOSS_THRESHOLD = 1/100
STOP_LOSS_COOL_DOWN_MINS = 5

BINANCE_SOCKET = f"wss://stream.binance.com:9443/ws/{TRADE_SYMBOL.lower()}@kline_1m"

START_DATETIME = str(datetime.now())

# Strategy is the strategy used to decide when to trade
Strategy = RSIWithBreakoutConfirmation(RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD)

in_long_position = False
last_buy_price = 0
last_position_stop_triggered = -1000
closes_dict = {}
cur_closes_dict_len = len(closes_dict)


# Loading API key and secret, which are saved in an external file
with open("../config/algo_config.json") as f:
    config_dict = json.load(f)

client = Client(config_dict['api_key'], config_dict['api_sec'])


# Functions determining what happens when the web socket is openened and closed, and when a message is recieved
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
    if cur_closes_dict_len >= 2:

        trade_executed = None

        # RSI can only be calculated on the (RSI_PERIOD+1)th closing price
        if len(closes_arr) >= RSI_PERIOD + 2:
            trade_executed = consider_trade(closes_arr)

        col_names = ["datetime_collected", "datetime", "price", "trade_made"]
        row = [START_DATETIME,
                    list(closes_dict.keys())[-2],
                    list(closes_dict.values())[-2],
                    trade_executed
                    ]

        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_data.csv", col_names, row)


def consider_trade(closes_arr):    
    global cur_closes_dict_len, in_long_position, last_buy_price, last_position_stop_triggered

    cur_price, prev_price, prev_rsi = Strategy.calc_rsi(closes_arr)

    should_sell = Strategy.should_sell(cur_price, prev_price, prev_rsi)
    should_buy = Strategy.should_buy(cur_price, prev_price, prev_rsi)

    should_trigger_stop_loss = (closes_arr[-1] <= (1 - STOP_LOSS_THRESHOLD)*last_buy_price)

    if (should_sell or should_trigger_stop_loss) and in_long_position:
        print("Attempting to sell" + should_trigger_stop_loss*" (stop loss executed)")
        order_succeeded = order(TRADE_SYMBOL, enums.SIDE_SELL, enums.ORDER_TYPE_MARKET, TRADE_QUANTITY, closes_arr)
        if should_trigger_stop_loss:
            last_position_stop_triggered = cur_closes_dict_len

        if order_succeeded:
            in_long_position = False
            return "sell"

    elif (should_buy and not in_long_position
            and (cur_closes_dict_len >= last_position_stop_triggered + STOP_LOSS_COOL_DOWN_MINS)):
        
        print("Attempting to buy...")
        order_succeeded = order(TRADE_SYMBOL, enums.SIDE_BUY, enums.ORDER_TYPE_MARKET, TRADE_QUANTITY, closes_arr)
        
        if order_succeeded:
            last_buy_price = closes_arr[-1]
            in_long_position = True
            return "buy"
    
    return None

def order(symbol, side, order_type, quantity, closes_arr):
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol,
                                    side=side,
                                    type=order_type,
                                    quantity=quantity)
        print("Order successful:", order, "\n\n")

        # Executed price and quantity, for logs
        try:
            actual_price = order['fills'][0]['price']
            actual_quantity = order['fills'][0]['qty']
            commission = order['fills'][0]['commission']
        except Exception as e:
            actual_price = ""
            actual_quantity = ""
            commission = ""
            print("Error saving to order details logs:", e)

        # Balances of both assets traded, for logs
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
                        "total_balance_btc"]
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
                total_balance_btc]
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