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
        """Returns True if there is a long position currently open and the RSI
        is at or above the overbought threshold, otherwise False.
        """
        return in_long_position and cur_rsi >= self.RSI_OVERBOUGHT
    
    def should_buy(self, cur_rsi: float, in_long_position: bool) -> bool:
        """Returns True if there is no long position currently open and the RSI
        is at or below the oversold threshold, otherwise False.
        """
        return (not in_long_position) and cur_rsi <= self.RSI_OVERSOLD

class RSIWithBreakoutConfirmation(BasicRSI):
    """Strategy that is similar to BasicRSI, but waits for a reversal to begin
    before making a trade.

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
        """Returns True if there is a long position currently open, the RSI is
        at or above the overbought threshold and the price is decreasing,
        otherwise False.
        """
        return super().should_sell(prev_rsi, in_long_position) and cur_price < prev_price
    
    def should_buy(self, prev_rsi: float, in_long_position: bool, 
                        cur_price: float, prev_price: float) -> bool:
        """Returns True if there is no long position currently open, the RSI is
        at or below the oversold threshold and the price is increasing,
        otherwise False.
        """
        return super().should_buy(prev_rsi, in_long_position) and cur_price > prev_price

class BasicLSTM(StrategyInterface):
    """Strategy using a pre-trained LSTM (Long short-term memory) neural
    network to predict movements in price. In particular, this stratgey buying
    if the predicted price is sufficiently high above the current price, the
    price is increasing and an open position is not currently being held. The
    strategy sells if the predicted price is sufficiently low below the current
    price, the price is decreasing and no position is currently held.

    Attributes
    ----------
    model : Sequential
        The pre-trained Keras model used to predict prices
    mean : float
        The mean of the training data, which will be required to normalise (and
        then denormalise) the data in order to predict the future price
    std : float
        The standard deviation of the training data, which will again be
        required to normalise and denormalise the data
    percent_change_trade_threshold : float
        The minimum predicted percent change required to make a trade. For
        instance, if this is set to be 1 then a trade will only be made if the
        predicted price is at least 1% higher (or lower) than the current price
    """
    def __init__(self, model_path: str, std_and_mean_path: str,
                    percent_change_trade_threshold: float = 1) -> None:
        self.model = self.load_keras_model(model_path)
        self.mean, self.std = self.load_mean_and_std(std_and_mean_path)
        self.change_trade_threshold = percent_change_trade_threshold/100

    def load_keras_model(self, model_path: str) -> Sequential:
        """Loads pre-trained keras model
        """
        model = keras.models.load_model(model_path)
        return model

    def load_mean_and_std(self, std_and_mean_path: str) -> Tuple[float, float]:
        """Loads mean and standard deviation of training data, in order to
        normalise data for use with the model
        """
        with open(std_and_mean_path, 'r', encoding='utf-8') as f:
            data_loaded = json.load(f)
        std = data_loaded['std']
        mean = data_loaded['mean']
        return mean, std

    def predict_30_min_price(self, closes_arr: np.ndarray) -> float:
        """Predicts the price 30 mins in the future, using the pre-loaded
        Keras LSTM
        """
        # Formatting array of closing prices in order to make a prediction
        closes_arr_norm = (np.array(closes_arr) - self.mean)/self.std
        closes_arr_norm = closes_arr_norm[-120:]

        # Using model to predict normalised pri e
        pred_arr = self.model.predict(closes_arr_norm.reshape(1, -1, 1))
        prediction_norm = pred_arr[0, 0]

        # Denormalising and returning prediction
        prediction = prediction_norm*self.std + self.mean
        return prediction

    def should_sell(self, closes_arr: np.ndarray, in_long_position: bool) -> bool:
        """Returns True if there is a long position currently open, the
        predicted price is at least percent_change_trade_threshold lower than
        the current price, and the price is decreasing. Otherwise returns
        False.
        """
        if in_long_position and len(closes_arr) >= 120:
            prediction = self.predict_30_min_price(closes_arr)
            cur_price = closes_arr[-1]
            if ((prediction <= cur_price*(1-self.change_trade_threshold))\
                and (closes_arr[-1] < closes_arr[-2])):
                return True
        return False

    def should_buy(self, closes_arr: np.ndarray, in_long_position: bool) -> bool:
        """Returns True if there is no long position currently open, the
        predicted price is at least percent_change_trade_threshold higher than
        the current price, and the price is increasing. Otherwise returns
        False.
        """
        if (not in_long_position) and len(closes_arr) >= 120:
            prediction = self.predict_30_min_price(closes_arr)
            cur_price = closes_arr[-1]
            if ((prediction >= cur_price*(1+self.change_trade_threshold))\
                and (closes_arr[-1] > closes_arr[-2])):
                return True
        return False
