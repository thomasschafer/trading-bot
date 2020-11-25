import talib


class StrategyInterface():
    def should_sell(self):
        return False
    def should_buy(self):
        return False

# def BasicRSI(StrategyInterface):



class RSIWithBreakoutConfirmation(StrategyInterface):
    def __init__(self, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD):
        self.RSI_PERIOD = RSI_PERIOD
        self.RSI_OVERBOUGHT = RSI_OVERBOUGHT
        self.RSI_OVERSOLD = RSI_OVERSOLD
    
    def calc_rsi(self, closes_arr):
        cur_price = closes_arr[-1]
        prev_price = closes_arr[-2]
        rsi = talib.RSI(closes_arr, self.RSI_PERIOD)
        prev_rsi = rsi[-2]
        return cur_price, prev_price, prev_rsi

    def should_sell(self, cur_price, prev_price, prev_rsi):
        return prev_rsi >= self.RSI_OVERBOUGHT and cur_price < prev_price
    
    def should_buy(self, cur_price, prev_price, prev_rsi):
        return prev_rsi <= self.RSI_OVERSOLD and (cur_price > prev_price)