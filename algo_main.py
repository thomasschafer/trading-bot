# Core Python modules
from datetime import datetime
import json

# Binance modules
from binance.client import Client
from binance import enums

# Project modules
from utilities import append_data, CurrentTradingSession
from strategies import BasicLSTM

# Additional modules
import numpy as np
import pandas as pd
import websocket

# Constants adjustable by user
ASSET_1 = "BTC" # Ticker for asset bought
ASSET_2 = "USDT" # Ticker for asset sold
TRADE_QUANTITY = 0.001

# Regardless of the strategy chosen, a a trailing stop loss is used, with the
# parameters set below
STOP_LOSS_THRESHOLD = 0.5/100
STOP_LOSS_COOL_DOWN_MINS = 5

# Strategy used to decide when to trade
Strategy = BasicLSTM("../models/LSTM/model_save", 0.1, 1)
MAX_MINS_OF_PRICES_HELD_IN_MEMORY = Strategy.MAX_MINS_OF_PRICES_HELD_IN_MEMORY

# Other constants
TRADE_SYMBOL = ASSET_1 + ASSET_2
BINANCE_SOCKET = f"wss://stream.binance.com:9443/ws/{TRADE_SYMBOL.lower()}@kline_1m"
START_DATETIME = str(datetime.now())

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

    # Pull out the timestamp, and round it down to the nearest minute
    unix_ts = int(message_dict['E'])/1000
    cur_ts = datetime.utcfromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')
    cur_ts = cur_ts[:-3]
    
    # The first condition checks whether the previous minute candle has closed.
    # The second condition ensures that this first condition will not be
    # triggered by accident, when we first begin trading and there will not be
    # a valid previous timestamp.
    if (cur_ts != cur_trading_sess.prev_ts) and (cur_trading_sess.prev_price != -1):
        cur_trading_sess.prev_ts = cur_ts

        # Updates the list of closing prices, only keeping the most recent two
        # hours of data
        prev_candle_close = cur_trading_sess.prev_price
        cur_trading_sess.closes_list.append(prev_candle_close)
        cur_trading_sess.closes_list = cur_trading_sess.closes_list[-MAX_MINS_OF_PRICES_HELD_IN_MEMORY:]

        closes_arr = np.array(cur_trading_sess.closes_list)
        on_candle_close(closes_arr)

    # Displays ticker information and new closing price
    ticker = message_dict['s']
    close_price = float(message_dict['k']['c'])
    print(f"{ticker} price at {cur_ts}: {close_price}")

    # Updates the previous price attribute
    cur_trading_sess.prev_price = close_price
    


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

    print("\nClosing prices:", closes_arr, "\n")

    if len(closes_arr) >= 2:

        # Updating the trailing stop loss if necessary
        if cur_trading_sess.in_long_position:
            cur_trading_sess.max_price_since_buy = max(cur_trading_sess.max_price_since_buy,
                                                        closes_arr[-1])

        trade_executed = consider_trade(closes_arr)

        col_names = ["datetime_collected", "datetime", "price", "trade_made"]
        row = [START_DATETIME,
               cur_trading_sess.prev_price,
               cur_trading_sess.prev_ts,
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
    should_sell = Strategy.should_sell(closes_arr,
                                        cur_trading_sess.in_long_position)
    should_buy = Strategy.should_buy(closes_arr,
                                        cur_trading_sess.in_long_position)

    # Checking if the price has gone below (or is at) the stop loss threshold.
    # Again, this is a trailing stop loss, so we compare with the maximum price
    # achieved since buying
    should_trigger_stop_loss = (closes_arr[-1] <= (1 - STOP_LOSS_THRESHOLD)*cur_trading_sess.max_price_since_buy)

    order_executed_type = None

    # For debugging purposes
    cur_price, prev_price = closes_arr[-1], closes_arr[-2]
    # Can be modified if using an RSI-based strategy
    prev_rsi = 0
    print("Considering trade: cur_price:", cur_price,
            ", prev_price:", prev_price,
            ", prev_rsi:", prev_rsi,
            ", should_sell:", should_sell,
            ", should_buy:", should_buy,
            ", should_trigger_stop_loss:", should_trigger_stop_loss,
            ", in_long_position:", cur_trading_sess.in_long_position,
            ", max_price_since_buy:", cur_trading_sess.max_price_since_buy)

    # Deciding whether to sell
    if should_sell or (should_trigger_stop_loss and cur_trading_sess.in_long_position):
        print("Attempting to sell" + should_trigger_stop_loss*" (stop loss executed)")
        order_succeeded = order(TRADE_SYMBOL, enums.SIDE_SELL,
                                enums.ORDER_TYPE_MARKET, TRADE_QUANTITY,
                                closes_arr)
        
        # Resetting for next time a buy order is executed
        cur_trading_sess.max_price_since_buy = 0

        if should_trigger_stop_loss:
            cur_trading_sess.last_position_stop_triggered = cur_trading_sess.cur_closes_dict_len

        if order_succeeded:
            cur_trading_sess.in_long_position = False
            order_executed_type = "sell"

    # Otherwise, deciding whether to buy
    elif should_buy\
        and (cur_trading_sess.cur_closes_dict_len >=
                cur_trading_sess.last_position_stop_triggered + STOP_LOSS_COOL_DOWN_MINS):
        
        print("Attempting to buy...")
        order_succeeded = order(TRADE_SYMBOL, enums.SIDE_BUY,
                                enums.ORDER_TYPE_MARKET, TRADE_QUANTITY,
                                closes_arr)
        
        if order_succeeded:
            cur_trading_sess.max_price_since_buy = closes_arr[-1]
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
    
    # Using a number of try-except statements, as there are a number of issues
    # that can occur when trying to execute an order, which are otherwise
    # handled by the websocket without displaying any feedback.
    try:
        print("Sending order")
        order = client.create_order(symbol=symbol,
                                    side=side,
                                    type=order_type,
                                    quantity=quantity)
        print("Order successful:", order, "\n\n")

        order_was_successful = True

        # Fetching executed price and quantity, for logs
        try:
            actual_price = order['fills'][0]['price']
            actual_quantity = order['fills'][0]['qty']
            commission = order['fills'][0]['commission']
        except Exception as e:
            actual_price = ""
            actual_quantity = ""
            commission = ""
            print("Error getting order details:", e)

        # Fetching balances of both assets traded, for logs
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
            print("Error getting balances:", e)

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


if __name__ == "__main__":
    binance_ws = websocket.WebSocketApp(BINANCE_SOCKET,
                                        on_open=on_open,
                                        on_close=on_close,
                                        on_message=on_message)
    binance_ws.run_forever()