import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ============ CONFIG ============
st.set_page_config(page_title="Crypto Futures Screener", layout="wide")
BASE_URL = "https://api.binance.com/api/v3/klines"
PAIRS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]  # you can add more

# ============ FUNCTIONS ============
def get_binance_ohlcv(symbol="BTCUSDT", interval="15m", limit=200):
    url = f"{BASE_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    r = requests.get(url)
    data = r.json()
    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_av", "trades", "tb_base_av", "tb_quote_av", "ignore"
    ])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df["open"] = df["open"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    return df

def ema(df, period=20):
    return df["close"].ewm(span=period).mean()

def generate_signal(df):
    """ Very simple EMA strategy for demo """
    df["EMA20"] = ema(df, 20)
    df["EMA50"] = ema(df, 50)
    latest = df.iloc[-1]
    if latest["EMA20"] > latest["EMA50"]:
        return "BUY"
    elif latest["EMA20"] < latest["EMA50"]:
        return "SELL"
    else:
        return "HOLD"

def plot_chart(df, pair, entry, tp_list, sl):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["time"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Candles"
    ))
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], line=dict(color="blue"), name="EMA20"))
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], line=dict(color="orange"), name="EMA50"))

    # add levels
    for i, tp in enumerate(tp_list, 1):
        fig.add_hline(y=tp, line=dict(color="green", dash="dot"), annotation_text=f"TP{i}")
    fig.add_hline(y=entry, line=dict(color="yellow", dash="dash"), annotation_text="Entry")
    fig.add_hline(y=sl, line=dict(color="red", dash="dash"), annotation_text="Stop Loss")

    fig.update_layout(title=f"{pair} Chart", xaxis_rangeslider_visible=False, height=400)
    return fig

# ============ UI ============
st.title("📊 Crypto Futures Screener")

refresh = st.sidebar.button("🔄 Rescan Binance Data")

for pair in PAIRS:
    df = get_binance_ohlcv(pair)
    signal = generate_signal(df)
    price = df["close"].iloc[-1]

    if signal == "BUY":
        entry = price
        tp_list = [price * 1.01, price * 1.02, price * 1.03]
        sl = price * 0.99
    elif signal == "SELL":
        entry = price
        tp_list = [price * 0.99, price * 0.98, price * 0.97]
        sl = price * 1.01
    else:
        entry, tp_list, sl = price, [price], price

    st.subheader(f"{pair} Signal: {signal}")
    st.write(f"**Current Price:** {price:.2f}")
    st.write(f"**Entry:** {entry:.2f}")
    st.write(f"**Take Profit:** {', '.join([str(round(tp,2)) for tp in tp_list])}")
    st.write(f"**Stop Loss:** {sl:.2f}")

    fig = plot_chart(df, pair, entry, tp_list, sl)
    st.plotly_chart(fig, use_container_width=True)
