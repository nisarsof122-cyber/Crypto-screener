    import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime

# Binance API endpoint
BASE_URL = "https://fapi.binance.com"

# ---------------------------------
# Helper functions
# ---------------------------------
def get_futures_symbols():
    """Fetch all USDT futures trading pairs from Binance"""
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    data = requests.get(url).json()
    symbols = [s['symbol'] for s in data['symbols'] if s['quoteAsset'] == 'USDT']
    return symbols

def get_klines(symbol, interval="15m", limit=200):
    """Fetch candlestick data"""
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        'time','open','high','low','close','volume',
        'close_time','quote_asset_volume','trades',
        'taker_base_vol','taker_quote_vol','ignore'
    ])
    df['time'] = pd.to_datetime(df['time'], unit='ms')
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    return df

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def generate_signal(df):
    """Very simple EMA crossover + volume filter strategy"""
    df['ema_fast'] = ema(df['close'], 9)
    df['ema_slow'] = ema(df['close'], 21)

    if df['ema_fast'].iloc[-1] > df['ema_slow'].iloc[-1] and df['volume'].iloc[-1] > df['volume'].mean():
        return "LONG"
    elif df['ema_fast'].iloc[-1] < df['ema_slow'].iloc[-1] and df['volume'].iloc[-1] > df['volume'].mean():
        return "SHORT"
    else:
        return None

def plot_chart(df, symbol, entry, tp_levels, sl):
    fig = go.Figure(data=[go.Candlestick(
        x=df['time'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name="Candles"
    )])

    # EMA overlays
    fig.add_trace(go.Scatter(x=df['time'], y=df['ema_fast'], line=dict(color="blue", width=1), name="EMA 9"))
    fig.add_trace(go.Scatter(x=df['time'], y=df['ema_slow'], line=dict(color="orange", width=1), name="EMA 21"))

    # Entry, TP, SL lines
    fig.add_hline(y=entry, line=dict(color="green", dash="dot"), annotation_text="Entry")
    fig.add_hline(y=sl, line=dict(color="red", dash="dot"), annotation_text="Stop Loss")
    for i, tp in enumerate(tp_levels, 1):
        fig.add_hline(y=tp, line=dict(color="purple", dash="dot"), annotation_text=f"TP{i}")

    fig.update_layout(title=f"{symbol} Signal Chart", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------
# Streamlit UI
# ---------------------------------
st.set_page_config(page_title="Crypto Futures Screener", layout="wide")
st.title("📊 Crypto Futures Screener (Binance)")

st.markdown("Scans USDT futures pairs, applies EMA + volume filter, and shows top signals with chart.")

# Fetch symbols
symbols = get_futures_symbols()

# Limit scan for demo (to avoid API overload)
subset = symbols[:20]

signals = []
for sym in subset:
    try:
        df = get_klines(sym, "15m", 200)
        sig = generate_signal(df)
        if sig:
            price = df['close'].iloc[-1]
            if sig == "LONG":
                entry = price
                tp_levels = [round(price * 1.01, 4), round(price * 1.02, 4), round(price * 1.03, 4)]
                sl = round(price * 0.99, 4)
            else:  # SHORT
                entry = price
                tp_levels = [round(price * 0.99, 4), round(price * 0.98, 4), round(price * 0.97, 4)]
                sl = round(price * 1.01, 4)

            signals.append({
                "symbol": sym,
                "signal": sig,
                "price": price,
                "entry": entry,
                "tp1": tp_levels[0],
                "tp2": tp_levels[1],
                "tp3": tp_levels[2],
                "sl": sl,
                "leverage": "10x"
            })
    except Exception:
        continue

# Pick top 3
signals = signals[:3]

if not signals:
    st.warning("No strong signals found right now.")
else:
    for sig in signals:
        with st.container():
            st.subheader(f"💡 {sig['symbol']} - {sig['signal']}")
            st.write(f"**Current Price:** {sig['price']}")
            st.write(f"**Entry:** {sig['entry']} | **Stop Loss:** {sig['sl']}")
            st.write(f"**Take Profits:** {sig['tp1']}, {sig['tp2']}, {sig['tp3']}")
            st.write(f"**Leverage Suggestion:** {sig['leverage']}")
            
            df = get_klines(sig['symbol'], "15m", 200)
            df['ema_fast'] = ema(df['close'], 9)
            df['ema_slow'] = ema(df['close'], 21)
            plot_chart(df, sig['symbol'], sig['entry'], [sig['tp1'], sig['tp2'], sig['tp3']], sig['sl'])
