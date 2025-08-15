import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go

BASE_URL = "https://fapi.binance.com"

def get_symbols():
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    data = requests.get(url).json()
    return [s['symbol'] for s in data['symbols'] if s['quoteAsset'] == 'USDT']

def get_klines(symbol, interval="15m", limit=200):
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        'time','open','high','low','close','volume',
        'close_time','quote_asset_volume','trades',
        'taker_base_vol','taker_quote_vol','ignore'
    ])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df[['open','high','low','close','volume']] = df[['open','high','low','close','volume']].astype(float)
    return df

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def generate_signal(df):
    df['ema9'] = ema(df['close'], 9)
    df['ema21'] = ema(df['close'], 21)

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "LONG"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "SHORT"
    return None

def plot_chart(df, symbol):
    fig = go.Figure(data=[go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name="Candles"
    )])
    fig.add_trace(go.Scatter(x=df['time'], y=df['ema9'], line=dict(color="blue"), name="EMA 9"))
    fig.add_trace(go.Scatter(x=df['time'], y=df['ema21'], line=dict(color="orange"), name="EMA 21"))
    fig.update_layout(title=f"{symbol} Chart", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------- UI ----------------------
st.title("📊 Crypto Futures Screener (Binance)")

symbols = get_symbols()
symbol = st.selectbox("Select a Symbol", symbols[:30])  # limit for demo

df = get_klines(symbol, "15m", 200)
df['ema9'] = ema(df['close'], 9)
df['ema21'] = ema(df['close'], 21)

signal = generate_signal(df)
if signal:
    st.success(f"Signal for {symbol}: {signal}")
else:
    st.info("No clear signal right now.")

plot_chart(df, symbol)
