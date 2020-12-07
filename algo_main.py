# Core Python modules
from datetime import datetime
import json

# Binance modules
from binance.client import Client
from binance import enums

# Project modules
from utilities import append_data, CurrentTradingSession
from strategies import RSIWithBreakoutConfirmation

# Additional modules
import numpy as np
import pandas as pd
import websocket

# Constants adjustable by user
ASSET_1 = "BTC" # Ticker for asset bought
ASSET_2 = "USDT" # Ticker for asset sold
TRADE_QUANTITY = 0.001
STOP_LOSS_THRESHOLD = 0.5/100
STOP_LOSS_COOL_DOWN_MINS = 5
# For use with strategies requiring RSI calculations
RSI_PERIOD = 14
RSI_OVERBOUGHT = 65
RSI_OVERSOLD = 35

# Constants not intended to be adjusted
TRADE_SYMBOL = ASSET_1 + ASSET_2
BINANCE_SOCKET = f"wss://stream.binance.com:9443/ws/{TRADE_SYMBOL.lower()}@kline_1m"
START_DATETIME = str(datetime.now())

# Strategy used to decide when to trade
Strategy = RSIWithBreakoutConfirmation(RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD)

# This object holds information about the current trading session, such as
# whether a long position is being held and what the last buy price was
cur_trading_sess = CurrentTradingSession()


# Loading API key and secret, which are saved in an external file
with open("../config/algo_config.json") as f:
    config_dict = json.load(f)

client = Client(config_dict['api_key'], config_dict['api_secret'])


# Functions determining what happens when the web socket is openened and closed,
# and when a message is recieved
def on_open(ws):
    print("Opened connection")

def on_close(ws):
    print("Closed connection")

def on_message(ws, message):
    try:
        on_message_helper(message)

    except Exception as e:
        print(e)


def on_message_helper(message: str) -> None:
    """Loads the message from the Binance websocket into a dictionary, and
    extracts the price and time returned. This is outputted to the console,
    and saved into a dictionary mapping datetime values (accurate to the
    nearest minute) to price values. If a new minute has begun, on_candle_close
    is called.

    Parameters
    ----------
    message : str
        message from the websocket

    Returns
    -------
    None
    """
    message_dict = json.loads(message)

    ticker = message_dict['s']

    unix_ts = int(message_dict['E'])/1000
    ts = datetime.utcfromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')

    close_price = float(message_dict['k']['c'])

    cur_trading_sess.closes_dict[ts[:-3]] = close_price

    print(f"{ticker} price at {ts}: {close_price}")

    if len(cur_trading_sess.closes_dict) > cur_trading_sess.cur_closes_dict_len:
        closes_arr = np.array(list(cur_trading_sess.closes_dict.values())[:-1])
        on_candle_close(closes_arr)


def on_candle_close(closes_arr: np.ndarray) -> None:
    """Outputs the closing prices array to the console (for debugging
    purposes), and appends the most recent closing price to a trading data CSV.
    If sufficient data has been collected then a there is the possiblity of
    making a trade, in which case consider_trade will be called.

    Parameters
    ----------
    closes_arr : np.ndarray
        Numpy array of closing prices

    Returns
    -------
    None
    """
    cur_trading_sess.cur_closes_dict_len = len(cur_trading_sess.closes_dict)

    print("\nClosing prices:", closes_arr, "\n")

    # We need to ensure we are not considering the most recent price, as this
    # will be the beginning of the next candle - we must look at the previous
    # price
    if cur_trading_sess.cur_closes_dict_len >= 2:

        trade_executed = None

        # RSI can only be calculated on the (RSI_PERIOD+1)th closing price
        if len(closes_arr) >= RSI_PERIOD + 2:
            trade_executed = consider_trade(closes_arr)

        col_names = ["datetime_collected", "datetime", "price", "trade_made"]
        row = [START_DATETIME,
                    list(cur_trading_sess.closes_dict.keys())[-2],
                    list(cur_trading_sess.closes_dict.values())[-2],
                    trade_executed
                    ]

        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_data.csv", col_names, row)


def consider_trade(closes_arr: np.ndarray) -> str:
    """Uses the trading strategy encapsulated in the Strategy object to
    determine whether to make a trade, either buying or selling, possibly
    due to the stop loss threshold being reached.

    Parameters
    ----------
    closes_arr : np.ndarray
        Numpy array of closing prices

    Returns
    -------
    order_executed_type : str
        The type of order that was executed, if any. This takes values "buy",
        "sell" or None.
    """
    cur_price, prev_price, prev_rsi = Strategy.calc(closes_arr)
    should_sell = Strategy.should_sell(prev_rsi, cur_trading_sess.in_long_position,
                                        cur_price, prev_price)
    should_buy = Strategy.should_buy(prev_rsi, cur_trading_sess.in_long_position,
                                        cur_price, prev_price)

    should_trigger_stop_loss = (closes_arr[-1] <= (1 - STOP_LOSS_THRESHOLD)*cur_trading_sess.last_buy_price)

    order_executed_type = None

    # For debugging purposes
    print("Considering trade: cur_price:", cur_price,
            ", prev_price:", prev_price,
            ", prev_rsi:", prev_rsi,
            ", should_sell:", should_sell,
            ", should_buy:", should_buy,
            ", should_trigger_stop_loss:", should_trigger_stop_loss,
            ", in_long_position:", cur_trading_sess.in_long_position)

    if should_sell or (should_trigger_stop_loss and cur_trading_sess.in_long_position):
        print("Attempting to sell" + should_trigger_stop_loss*" (stop loss executed)")
        order_succeeded = order(TRADE_SYMBOL, enums.SIDE_SELL,
                                enums.ORDER_TYPE_MARKET, TRADE_QUANTITY,
                                closes_arr)
        if should_trigger_stop_loss:
            cur_trading_sess.last_position_stop_triggered = cur_trading_sess.cur_closes_dict_len

        if order_succeeded:
            cur_trading_sess.in_long_position = False
            order_executed_type = "sell"

    elif should_buy\
        and (cur_trading_sess.cur_closes_dict_len >=
                cur_trading_sess.last_position_stop_triggered + STOP_LOSS_COOL_DOWN_MINS):
        
        print("Attempting to buy...")
        order_succeeded = order(TRADE_SYMBOL, enums.SIDE_BUY,
                                enums.ORDER_TYPE_MARKET, TRADE_QUANTITY,
                                closes_arr)
        
        if order_succeeded:
            cur_trading_sess.last_buy_price = closes_arr[-1]
            cur_trading_sess.in_long_position = True
            order_executed_type = "buy"
    
    return order_executed_type


def order(symbol: str, side: str, order_type: str,
            quantity: float, closes_arr: np.ndarray) -> bool:
    """Attempts to send the order specified to Binance. If this was successful,
    details of the trade are saved to the trades log CSV, as well as account
    balances and other useful information.

    Parameters
    ----------
    symbol : str
        The symbol (ticker) for the asset to be traded
    side : str
        The side to be traded (representing buying or selling)
    order type : str
        The type of order to be made, e.g. market order
    quantity : float
        The quantity of the aforementioned symbol to be traded
    closes_arr : np.ndarray
        Numpy array of closing prices

    Returns
    -------
    order_was_successful : bool
        Boolean set to true if the order was completed successfully, otherwise
        false.
    """
    order_was_successful = False
    
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol,
                                    side=side,
                                    type=order_type,
                                    quantity=quantity)
        print("Order successful:", order, "\n\n")

        order_was_successful = True

        # Executed price and quantity, for logs
        try:
            actual_price = order['fills'][0]['price']
            actual_quantity = order['fills'][0]['qty']
            commission = order['fills'][0]['commission']
        except Exception as e:
            actual_price = ""
            actual_quantity = ""
            commission = ""
            print("Error getting order details:", e)

        # Balances of both assets traded, for logs
        try:
            balance_1 = float(client.get_asset_balance(asset=ASSET_1)['free'])
            usd_price_1 = float(client.get_avg_price(symbol=f'{ASSET_1}USDT')['price'])
            balance_2 = float(client.get_asset_balance(asset=ASSET_2)['free'])
            if ASSET_1 == "USDT":
                usd_price_2 = 1
            else:
                usd_price_2 = float(client.get_avg_price(symbol=f'{ASSET_1}USDT')['price'])
            balance_usd = balance_1*usd_price_1 + balance_2*usd_price_2
        except Exception as e:
            balance_1 = ""
            balance_2 = ""
            balance_usd = ""
            print("Error saving balances to logs:", e)

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
                        "total_balance_usd"
                        ]
        row = [START_DATETIME,
                datetime.now(),
                symbol,
                side,
                order_type,
                quantity,
                closes_arr[-1],
                actual_price,
                actual_quantity,
                commission,
                balance_1,
                balance_2,
                balance_usd
            ]
        append_data(f"../Trading CSVs/{TRADE_SYMBOL}_trades_log.csv", col_names, row)
    
    except Exception as e:
        print("Order failed:", e, "\n")

    return order_was_successful


if __name__ == '__main__':
    binance_ws = websocket.WebSocketApp(BINANCE_SOCKET,
                                        on_open=on_open,
                                        on_close=on_close,
                                        on_message=on_message)
    binance_ws.run_forever()