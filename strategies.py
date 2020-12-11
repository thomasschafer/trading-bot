from typing import Tuple
import json
import talib
import numpy as np
from tensorflow import keras
from tensorflow.python.keras.engine.sequential import Sequential


class StrategyInterface():
    """Strategies should take this format to ensure no modification to
    algo_main is required.
    """
    def should_sell(self) -> bool:
        return False
    def should_buy(self) -> bool:
        return False


class BasicRSI(StrategyInterface):
    """Strategy that simply buys when there is no open position and the RSI
    (Relative Strength Index) is sufficiently low, and sells when there is an
    open position and the RSI is sufficiently high.

    Attributes
    ----------
    RSI_PERIOD : int
        The period over which the RSI is calculated
    RSI_OVERBOUGHT : int
        Threshold over which a sell will be executed
    RSI_OVERSOLD : int
        Threshold below which a buy will be executed
    """
    def __init__(self, RSI_PERIOD: float, RSI_OVERBOUGHT: float, RSI_OVERSOLD: float):
        self.RSI_PERIOD = RSI_PERIOD
        self.RSI_OVERBOUGHT = RSI_OVERBOUGHT
        self.RSI_OVERSOLD = RSI_OVERSOLD
    
    def calc(self, closes_arr: np.ndarray) -> bool:
        """Calculate and returns the current RSI
        """
        rsi = talib.RSI(closes_arr, self.RSI_PERIOD)
        cur_rsi = rsi[-1]
        return cur_rsi
    
    def should_sell(self, cur_rsi: float, in_long_position: bool) -> bool:
        """Returns a boolean indicating whether or not the asset should be sold
        """
        return in_long_position and cur_rsi >= self.RSI_OVERBOUGHT
    
    def should_buy(self, cur_rsi: float, in_long_position: bool) -> bool:
        """Returns a boolean indicating whether or not the asset should be
        bought
        """
        return (not in_long_position) and cur_rsi <= self.RSI_OVERSOLD

class RSIWithBreakoutConfirmation(BasicRSI):
    """Strategy that is similar to BasicRSI, but waits for a reversal to begin
    before trading

    Attributes
    ----------
    RSI_PERIOD : int
        The period over which the RSI is calculated
    RSI_OVERBOUGHT : int
        Threshold over which a sell will be executed
    RSI_OVERSOLD : int
        Threshold below which a buy will be executed
    """
    def __init__(self, RSI_PERIOD: float, RSI_OVERBOUGHT: float, RSI_OVERSOLD: float):
        super().__init__(RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD)
        
    def calc(self, closes_arr: np.ndarray) -> Tuple[float, float, float]:
        """Returns the previous RSI, alonside the current and previous prices
        """
        cur_price = closes_arr[-1]
        prev_price = closes_arr[-2]
        prev_rsi = super().calc(closes_arr[:-1])
        return cur_price, prev_price, prev_rsi

    def should_sell(self, prev_rsi: float, in_long_position: bool,
                        cur_price: float, prev_price: float) -> bool:
        """Returns a boolean indicating whether or not the asset should be sold
        """
        return super().should_sell(prev_rsi, in_long_position) and cur_price < prev_price
    
    def should_buy(self, prev_rsi: float, in_long_position: bool, 
                        cur_price: float, prev_price: float) -> bool:
        """Returns a boolean indicating whether or not the asset should be
        bought
        """
        return super().should_buy(prev_rsi, in_long_position) and cur_price > prev_price


class BasicLSTM(StrategyInterface):
    """
    """
    def __init__(self, model_path: str, std_and_mean_path: str) -> None:
        self.model = self.load_keras_model(model_path)
        self.mean, self.std = self.load_std_and_mean(std_and_mean_path)

    def load_keras_model(self, model_path: str) -> Sequential:
        model = keras.models.load_model(model_path)
        return model

    def load_std_and_mean(self, std_and_mean_path: str) -> Tuple[float, float]:
        with open(std_and_mean_path, 'r', encoding='utf-8') as f:
            data_loaded = json.load(f)
        std = data_loaded['std']
        mean = data_loaded['mean']
        return mean, std