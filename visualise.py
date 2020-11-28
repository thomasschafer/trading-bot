import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from pandas.plotting import register_matplotlib_converters; register_matplotlib_converters()

fig = plt.figure()
ax = fig.add_subplot(111)

def plot_trade_data(data_loc):
    df_full = pd.read_csv(data_loc)

    # Only using data from current trading session
    df = df_full[df_full['datetime_collected'] == df_full['datetime_collected'].iloc[-1]]
    closing_prices = df['price'].values.reshape(-1)

    # Defining numpy arrays for plotting
    trades = df['trade_made'].values.reshape(-1)
    buy_executed = np.array([closing_prices[i] if (trades[i] == "buy") else None for i in range(len(closing_prices))])
    sell_executed = np.array([closing_prices[i] if (trades[i] == "sell") else None for i in range(len(closing_prices))])
    x = pd.to_datetime(df['datetime'])

    # Plotting graph
    ax.clear()
    ax.plot(x, closing_prices, c='gray', label="Closing price")
    ax.plot(x, buy_executed, 'g-', marker='o', linewidth=3, ms=12)
    ax.plot(x, sell_executed, 'r-', marker='o', linewidth=3, ms=12)
    ax.set_ylabel('Closing price')
    ax.set_xlabel("Datetime")

trade_data_loc = "/Users/thomasschafer/Documents/Programming/Python/Trading CSVs/BTCUSDT_data.csv"
     
def animate(i):
    plot_trade_data(trade_data_loc)

a = FuncAnimation(fig, animate, interval=100)        
plt.show()