# Trading bot

This project is an automated trading system that trades cryptocurrencies on the Binance exchange. By default it trades **BTCUSDT**, but all pairs on the exchange can be traded.

Prices and executed trades are visualised in an automatically updating chart. Minute by minute candle data is continually appended to a CSV for analysis, alongside a log of trades and account balances to track profitability.

Please read the disclaimer before trading using this bot.


## Prerequesites

Ensure that you have installed all packages in requirements.txt, either manually or by using:

```python
pip install -r requirements.txt
```

By default, the script looks for Binance API keys saved in a folder called **`config`** in the parent directory of the project. The keys are expected to be in a file called **`algo_config.json`**  which takes the form:

```json
{"api_key": "INSERT API KEY HERE", "api_secret": "INSERT API SECRET HERE"}
```

This location can of course be modified in **`algo_main.py`**. Ensure that these keys remain secure as they permit access to all funds on the account.

## Usage

Run **`algo_main.py`** to begin trading. Ensure that **TRADE_QUANTITY** is modified to be the amount you would like to trade: this must be at least 0.001 when trading **BTCUSDT**.

Running **`visualise.py`** will create an automatically updating chart that displays the price movements since the bot began running, as well green dots for points at which a buy order was executed and red dots to indicate executed sell orders. Note that this uses **matplotlib.animation.FuncAnimation** which is a little temperamental about the IDEs it  works well with - I found issues running this in VSCode, but no problems using IDLE.

The strategies used for trading are defined as classes in **`strategies.py`**, and can be easily extended when new ideas are developed. Once a new strategy class is defined, simply modify the initialisation of the **Strategy** object in **`algo_main.py`**.

## Disclaimer

Please review all code in this project before allowing access to your funds. This project is presented without license or warranty, and no responsibility can be taken for money lost through trading or otherwise. No promise is made here about the profitability of the strategies used to trade, and users should be aware that investments may decrease in value or become worthless. If you are at all unsure about the nature of this tool, cryptocurrencies or trading then please seek professional financial advice.