import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go

BASE_URL = "https://fapi.binance.com"

# Get Futures USDT pairs
def get_symbols(limit=20):
    url = f"{BASE_URL}/fapi/v1/exchangeInfo"
    data = requests.get(url).json()
    return [s['symbol'] for s in data['symbols'] if s['quoteAsset'] == 'USDT'][:limit]

# Fetch candles
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

# EMA function
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

# Generate signals
def generate_signal(df, symbol):
    df['ema9'] = ema(df['close'], 9)
    df['ema21'] = ema(df['close'], 21)

    last_price = df['close'].iloc[-1]
    signal = "NO SIGNAL"
    entry = stop_loss = tp1 = tp2 = tp3 = leverage = confidence = None

    # Long
    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        signal = "LONG"
        entry = last_price
        stop_loss = last_price * 0.99
        tp1 = last_price * 1.01
        tp2 = last_price * 1.02
        tp3 = last_price * 1.03
        leverage = "10x"
        confidence = (df['ema9'].iloc[-1] - df['ema21'].iloc[-1]) / last_price

    # Short
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        signal = "SHORT"
        entry = last_price
        stop_loss = last_price * 1.01
        tp1 = last_price * 0.99
        tp2 = last_price * 0.98
        tp3 = last_price * 0.97
        leverage = "10x"
        confidence = (df['ema21'].iloc[-1] - df['ema9'].iloc[-1]) / last_price

    return {
        "symbol": symbol,
        "signal": signal,
        "last_price": last_price,
        "entry": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "leverage": leverage,
        "confidence": confidence,
        "volume": df['volume'].iloc[-1]
    }

# Plot chart
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
    fig.update_layout(title=f"{symbol} (15m)", xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# ---------------- Streamlit UI ----------------
st.title("📊 Binance Futures Screener – Top 3 Signals")

symbols = get_symbols(limit=20)
results = []

# Scan all pairs
for sym in symbols:
    try:
        df = get_klines(sym, "15m", 200)
        res = generate_signal(df, sym)
        if res["signal"] != "NO SIGNAL":
            results.append(res)
    except:
        continue

# Rank by confidence × volume
if results:
    ranked = sorted(results, key=lambda x: x["confidence"] * x["volume"], reverse=True)[:3]

    for r in ranked:
        st.subheader(f"{r['symbol']} – {r['signal']} Signal")
        st.markdown(f"""
        ### 📌 Signal Card
        - **Current Price:** {r['last_price']:.4f}
        - **Entry:** {r['entry']:.4f}
        - **Stop Loss:** {r['stop_loss']:.4f}
        - **Take Profit 1:** {r['tp1']:.4f}
        - **Take Profit 2:** {r['tp2']:.4f}
        - **Take Profit 3:** {r['tp3']:.4f}
        - **Leverage:** {r['leverage']}
        - **Confidence Score:** {r['confidence']:.4f}
        """)

        df = get_klines(r['symbol'], "15m", 200)
        plot_chart(df, r['symbol'])
else:
    st.warning("⚠️ No strong signals found right now.")
