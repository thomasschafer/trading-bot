import talib

# Interface providing the format for all strategies
class StrategyInterface():
    def should_sell(self):
        return False
    def should_buy(self):
        return False

# Strategy that simply buys and sells based on predefined RSI thresholds
class BasicRSI(StrategyInterface):
    def __init__(self, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD):
        self.RSI_PERIOD = RSI_PERIOD
        self.RSI_OVERBOUGHT = RSI_OVERBOUGHT
        self.RSI_OVERSOLD = RSI_OVERSOLD
    
    def should_sell(self, cur_price, prev_price, prev_rsi):
        return prev_rsi >= self.RSI_OVERBOUGHT
    
    def should_buy(self, cur_price, prev_price, prev_rsi):
        return prev_rsi <= self.RSI_OVERSOLD

# Strategy that is similar to BasicRSI, but waits for a reversal to begin before trading
class RSIWithBreakoutConfirmation(BasicRSI):
    def __init__(self, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD):
        super().__init__(RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD)
    
    def calc_rsi(self, closes_arr):
        cur_price = closes_arr[-1]
        prev_price = closes_arr[-2]
        rsi = talib.RSI(closes_arr, self.RSI_PERIOD)
        prev_rsi = rsi[-2]
        return cur_price, prev_price, prev_rsi

    def should_sell(self, cur_price, prev_price, prev_rsi):
        return super().should_sell() and cur_price < prev_price
    
    def should_buy(self, cur_price, prev_price, prev_rsi):
        return super().should_buy() and cur_price > prev_price