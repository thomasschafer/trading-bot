# Trading bot

This project is an automated trading system that trades cryptocurrencies on the Binance exchange. By default it trades **BTCUSDT**, but all pairs on the exchange can be traded.

Minute by minute candle data is continually appended to a CSV for analysis, alongside a log of trades and account balances to track profitability. Errors such as API errors are outputted to the console without halting trading.


## Prerequesites

Ensure that you have installed all packages in requirements.txt, either manually or by using:

```python
pip install -r requirements.txt
```

By default, the script looks for Binance API keys saved in a folder called **`config`** in the parent directory of the project. The keys are expected to be in a file called **`algo_config.json`**  which takes the form:

```json
{"api_key": "INSERT API KEY HERE", "api_secret": "INSERT API KEY HERE"}
```

This location can of course be modified in **`algo_main.py`**. Ensure that these keys remain secure as they permit access to all funds on the account.

## Usage

Run **`algo_main.py`** to begin trading.

Running **`visualise.py`** will create an automatically updating chart that displays the price movements since the bot began running, as well green dots for points at which a buy order was executed and red dots to indicate executed sell orders. Note that this uses matplotlib.animation.FuncAnimation which is a little temperamental about the IDEs it  works well with - I found issues running this in VSCode, but no problems using IDLE.

The strategies used for trading are defined as classes in **`strategies.py`**, and can be easily extended when new ideas are developed. Once a new strategy class is defined, simply modify the initialisation of **Strategy** object in **`algo_main.py`**.