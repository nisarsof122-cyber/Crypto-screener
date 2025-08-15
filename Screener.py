import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

BINANCE_API = "https://api.binance.com/api/v3"

# -----------------------------
# Fetch Binance klines
# -----------------------------
def fetch_klines(symbol, interval="5m", limit=200):
    url = f"{BINANCE_API}/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        df = pd.DataFrame(data, columns=[
            "time","open","high","low","close","volume","c1","c2","c3","c4","c5","c6"
        ])
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df[["time","open","high","low","close","volume"]]
    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")
        return None

# -----------------------------
# Indicators
# -----------------------------
def add_indicators(df):
    df["EMA20"] = df["close"].ewm(span=20).mean()
    df["EMA50"] = df["close"].ewm(span=50).mean()
    df["EMA200"] = df["close"].ewm(span=200).mean()

    delta = df["close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    exp1 = df["close"].ewm(span=12).mean()
    exp2 = df["close"].ewm(span=26).mean()
    df["MACD"] = exp1 - exp2
    df["Signal"] = df["MACD"].ewm(span=9).mean()
    return df

# -----------------------------
# Generate trading signal
# -----------------------------
def generate_signal(df):
    latest = df.iloc[-1]
    score = 0
    reasons = []

    if latest["EMA20"] > latest["EMA50"] > latest["EMA200"]:
        score += 3; reasons.append("Bullish EMA trend")
    elif latest["EMA20"] < latest["EMA50"] < latest["EMA200"]:
        score -= 3; reasons.append("Bearish EMA trend")

    if latest["RSI"] < 30:
        score += 2; reasons.append("Oversold RSI")
    elif latest["RSI"] > 70:
        score -= 2; reasons.append("Overbought RSI")

    if latest["MACD"] > latest["Signal"]:
        score += 2; reasons.append("MACD bullish crossover")
    else:
        score -= 2; reasons.append("MACD bearish crossover")

    conf = min(max((score + 5) / 10, 0), 1)
    bias = "Long" if conf >= 0.6 else "Short" if conf <= 0.4 else "Neutral"

    # Trading levels
    entry = latest["close"]
    if bias == "Long":
        tp1, tp2, tp3 = entry * 1.01, entry * 1.02, entry * 1.03
        sl = entry * 0.99
    elif bias == "Short":
        tp1, tp2, tp3 = entry * 0.99, entry * 0.98, entry * 0.97
        sl = entry * 1.01
    else:
        tp1 = tp2 = tp3 = sl = None

    return {
        "confidence": conf,
        "bias": bias,
        "reasons": reasons,
        "entry": entry,
        "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl
    }

# -----------------------------
# Chart
# -----------------------------
def plot_chart(df, signal):
    fig = go.Figure(data=[
        go.Candlestick(
            x=df["time"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"], name="Candles"
        )
    ])
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA20"], name="EMA20", line=dict(color="blue")))
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA50"], name="EMA50", line=dict(color="orange")))
    fig.add_trace(go.Scatter(x=df["time"], y=df["EMA200"], name="EMA200", line=dict(color="purple")))
    return fig

# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="Crypto Futures Screener", layout="wide")

st.title("📊 Binance USDT Futures Screener")

interval = st.sidebar.selectbox("Timeframe", ["1m","5m","15m","1h","4h"], index=1)
confidence_threshold = st.sidebar.slider("Confidence threshold", 0.5, 0.95, 0.9, 0.05)
refresh_interval = st.sidebar.slider("Auto-refresh (minutes)", 0, 15, 5)
if refresh_interval > 0:
    st_autorefresh(interval=refresh_interval*60*1000, key="refresh")

# Binance symbols
symbols = []
try:
    info = requests.get(f"{BINANCE_API}/exchangeInfo").json()
    symbols = [s["symbol"] for s in info["symbols"] if s["symbol"].endswith("USDT")]
except Exception as e:
    st.error(f"Could not fetch symbols: {e}")

signals = []
for sym in symbols[:30]:
    df = fetch_klines(sym, interval)
    if df is None: continue
    df = add_indicators(df)
    sig = generate_signal(df)
    if sig["confidence"] >= confidence_threshold:
        signals.append({"symbol": sym, "signal": sig, "data": df})

if not signals:
    st.warning("No signals found at this level.")
else:
    st.dataframe(pd.DataFrame([
        {"Symbol": s["symbol"], "Bias": s["signal"]["bias"], "Confidence": round(s["signal"]["confidence"],2)}
        for s in signals
    ]))

    st.subheader("🔥 Top 3 Signal Cards")
    top3 = sorted(signals, key=lambda x: x["signal"]["confidence"], reverse=True)[:3]
    for sig in top3:
        s = sig["signal"]
        st.markdown(f"### {sig['symbol']} ({s['bias']}) — Confidence {s['confidence']:.2f}")
        st.write("Reasons:", ", ".join(s["reasons"]))
        st.write(f"**Entry:** {s['entry']:.2f}")
        if s["tp1"]: 
            st.write(f"TP1: {s['tp1']:.2f}, TP2: {s['tp2']:.2f}, TP3: {s['tp3']:.2f}, SL: {s['sl']:.2f}")
        st.plotly_chart(plot_chart(sig["data"], sig), use_container_width=True)
