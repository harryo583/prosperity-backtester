import pandas as pd
import matplotlib.pyplot as plt

# Parameters
csv_path = 'prices.csv'
product_name = 'KELP'
short_window = 3
long_window = 7
num_timestamps = 80

# Load data
df = pd.read_csv(csv_path, sep=';')

# Filter for specific product
df = df[df['product'] == product_name].copy()

# Compute Best Bid & Ask
df['best_bid'] = df['bid_price_1']
df['best_ask'] = df['ask_price_1']

# Compute Moving Averages
df['short_ma_bid'] = df['best_bid'].rolling(window=short_window).mean()
df['long_ma_bid'] = df['best_bid'].rolling(window=long_window).mean()
df['short_ma_ask'] = df['best_ask'].rolling(window=short_window).mean()
df['long_ma_ask'] = df['best_ask'].rolling(window=long_window).mean()

# Slice last num_timestamps rows if specified
if num_timestamps is not None:
    df = df.tail(num_timestamps)

# Detect Intersections
green_cross = df[df['short_ma_bid'] > df['long_ma_ask']]
red_cross = df[df['short_ma_ask'] < df['long_ma_bid']]

# Plot
plt.figure(figsize=(15, 8))

# Plot Best Bid/Ask
plt.plot(df['timestamp'], df['best_bid'], label='Best Bid', color='blue', alpha=0.6)
plt.plot(df['timestamp'], df['best_ask'], label='Best Ask', color='orange', alpha=0.6)

# Plot Moving Averages
plt.plot(df['timestamp'], df['short_ma_bid'], label=f'Short MA Bid ({short_window})', color='cyan')
plt.plot(df['timestamp'], df['long_ma_bid'], label=f'Long MA Bid ({long_window})', color='green')
plt.plot(df['timestamp'], df['short_ma_ask'], label=f'Short MA Ask ({short_window})', color='magenta')
plt.plot(df['timestamp'], df['long_ma_ask'], label=f'Long MA Ask ({long_window})', color='red')

# Plot Intersections
plt.scatter(green_cross['timestamp'], green_cross['short_ma_bid'], color='green', label='Bid > Ask Intersection')
plt.scatter(red_cross['timestamp'], red_cross['short_ma_ask'], color='red', label='Ask < Bid Intersection')

plt.xlabel('Timestamp')
plt.ylabel('Price')
plt.title(f'Order Book View: {product_name}')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
