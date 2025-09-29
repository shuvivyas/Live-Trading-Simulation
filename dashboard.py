import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from decimal import Decimal

API_BASE = "http://localhost:8000/api"  

st.set_page_config(page_title="Algo Trading Dashboard (Streamlit)", layout="wide")
st.title("📊 Algo Trading Dashboard (Streamlit)")

st.sidebar.header("Settings")
strategy = st.sidebar.selectbox("Choose Strategy", ["sma_crossover", "rsi"])

@st.cache_data(ttl=5)
def fetch_trades(symbol: str = None, strategy: str = None, limit: int = 2000):
    try:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if strategy:
            params["strategy"] = strategy
        r = requests.get(f"{API_BASE}/trades", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

@st.cache_data(ttl=5)
def fetch_equity(symbol: str = None, strategy: str = None, limit: int = 5000):
    try:
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if strategy:
            params["strategy"] = strategy
        r = requests.get(f"{API_BASE}/equity", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

@st.cache_data(ttl=5)
def fetch_portfolio(symbol: str = None, strategy: str = None):
    try:
        params = {}
        if symbol:
            params["symbol"] = symbol
        if strategy:
            params["strategy"] = strategy
        r = requests.get(f"{API_BASE}/portfolio", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"__error__": str(e)}

all_trades_sample = fetch_trades(limit=5000)
symbol_input_default = "All"

symbol_options = None
if not (isinstance(all_trades_sample, dict) and "__error__" in all_trades_sample):
    try:
        df_sym = pd.DataFrame(all_trades_sample)
        if "symbol" in df_sym.columns and not df_sym["symbol"].dropna().empty:
            unique_syms = sorted(df_sym["symbol"].dropna().unique().tolist())
            symbol_options = ["All"] + unique_syms
    except Exception:
        symbol_options = None

if symbol_options and len(symbol_options) > 1:
    symbol_choice = st.sidebar.selectbox("Symbol", symbol_options, index=1 if symbol_input_default in symbol_options else 0)
    if symbol_choice == "All":
        symbol = None
    else:
        symbol = symbol_choice
else:
    symbol = st.sidebar.text_input("Symbol", symbol_input_default)

st.sidebar.markdown("---")
if st.sidebar.button("Run backtest now"):
    try:
        r = requests.get(f"{API_BASE}/run_strategy", params={"symbol": symbol or symbol_input_default, "strategy": strategy}, timeout=30)
        r.raise_for_status()
        st.sidebar.success("Backtest finished (server returned 200).")
    except Exception as e:
        st.sidebar.error(f"Backtest error: {e}")

    try:
        st.cache_data.clear()
    except Exception:
        pass

st.sidebar.caption("Use 'Run backtest now' to generate or refresh data for the selected symbol/strategy.")

portfolio_json = fetch_portfolio(symbol=symbol, strategy=strategy)
trades_json = fetch_trades(symbol=symbol, strategy=strategy, limit=5000)
equity_json = fetch_equity(symbol=symbol, strategy=strategy, limit=10000)


def to_df_safe(x):
    if not x:
        return pd.DataFrame()
    if isinstance(x, dict) and "__error__" in x:
        return pd.DataFrame()
    try:
        return pd.DataFrame(x)
    except Exception:
        return pd.DataFrame()

def coerce_num(series):
    return pd.to_numeric(series, errors="coerce")


trades_df = to_df_safe(trades_json)
if not trades_df.empty:
    if "trade_time" in trades_df.columns and "date" not in trades_df.columns:
        trades_df = trades_df.rename(columns={"trade_time": "date"})
    if "created_at" in trades_df.columns and "date" not in trades_df.columns:
        trades_df = trades_df.rename(columns={"created_at": "date"})
    if "date" in trades_df.columns:
        trades_df["date"] = pd.to_datetime(trades_df["date"], errors="coerce")
    for c in ["price", "shares", "cash_after", "position_after"]:
        if c in trades_df.columns:
            trades_df[c] = coerce_num(trades_df[c])


equity_df = to_df_safe(equity_json)
if not equity_df.empty:
    if "snapshot_time" in equity_df.columns:
        equity_df["snapshot_time"] = pd.to_datetime(equity_df["snapshot_time"], errors="coerce")
    elif "created_at" in equity_df.columns:
        equity_df["snapshot_time"] = pd.to_datetime(equity_df["created_at"], errors="coerce")

    if "equity" in equity_df.columns:
        equity_df["equity"] = coerce_num(equity_df["equity"])
    if "cash" in equity_df.columns:
        equity_df["cash"] = coerce_num(equity_df["cash"])
    if "position_shares" in equity_df.columns:
        equity_df["position_shares"] = coerce_num(equity_df["position_shares"])
    if "last_price" in equity_df.columns:
        equity_df["last_price"] = coerce_num(equity_df["last_price"])
    equity_df = equity_df.dropna(subset=["snapshot_time", "equity"]).sort_values("snapshot_time").reset_index(drop=True)


left, right = st.columns([3, 1])

with right:
    st.subheader("Portfolio Summary")
    if isinstance(portfolio_json, dict) and "__error__" in portfolio_json:
        st.info("No portfolio (error contacting API). See sidebar.")
    elif portfolio_json:
        if isinstance(portfolio_json, list) and len(portfolio_json) > 0:
            p = portfolio_json[0]
        else:
            p = portfolio_json if isinstance(portfolio_json, dict) else {}
        def safef(k):
            try:
                return float(p.get(k) or 0)
            except Exception:
                return 0
        st.metric("Equity", f"${safef('equity'):,.2f}")
        st.metric("Cash", f"${safef('cash'):,.2f}")
        st.metric("Position (shares)", f"{safef('position_shares'):.4f}")
        st.metric("Last Price", f"${safef('last_price'):.2f}")
        st.caption(f"Symbol: {p.get('symbol', symbol or 'N/A')}  ·  Strategy: {p.get('strategy', strategy)}")
    else:
        st.info("No portfolio data yet")

with left:
    st.subheader("Equity Curve (from /api/equity snapshots)")
    if equity_df.empty:
        st.info("No equity snapshots available for this symbol/strategy.")
        if isinstance(equity_json, dict) and "__error__" in equity_json:
            st.code(equity_json["__error__"])
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Snapshots", f"{len(equity_df):,}")
        c2.metric("Unique equity values", f"{equity_df['equity'].nunique():,}")
        try:
            date_range = f"{equity_df['snapshot_time'].dt.date.min()} → {equity_df['snapshot_time'].dt.date.max()}"
        except Exception:
            date_range = "n/a"
        c3.metric("Date range", date_range)

        fig_eq = go.Figure()
        fig_eq.add_trace(go.Scatter(x=equity_df["snapshot_time"], y=equity_df["equity"], mode="lines", name="Equity"))
        fig_eq.update_layout(height=360, margin=dict(l=10, r=10, t=25, b=10))
        st.plotly_chart(fig_eq, use_container_width=True)

        equity0 = float(equity_df["equity"].iloc[0])
        equity_df["eq_change"] = equity_df["equity"] - equity0
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=equity_df["snapshot_time"], y=equity_df["eq_change"], mode="lines", name="Equity - Start"))
        fig2.update_layout(height=180, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig2, use_container_width=True)

st.subheader("Price Chart (with trade markers)")
if trades_df.empty:
    st.info("No trades to show for this symbol/strategy.")
else:
    trades_sorted = trades_df.sort_values("date").reset_index(drop=True)
    if "price" in trades_sorted.columns and not trades_sorted["price"].isnull().all():
        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=trades_sorted["date"], y=trades_sorted["price"], mode="lines+markers", name="Trade Price"))

        trade_type_col = "trade_type" if "trade_type" in trades_sorted.columns else ("type" if "type" in trades_sorted.columns else None)
        if trade_type_col:
            buys = trades_sorted[trades_sorted[trade_type_col].str.lower() == "buy"]
            sells = trades_sorted[trades_sorted[trade_type_col].str.lower() == "sell"]
            if not buys.empty:
                fig_p.add_trace(go.Scatter(x=buys["date"], y=buys["price"], mode="markers", marker_symbol="triangle-up", marker_color="green", marker_size=10, name="Buys"))
            if not sells.empty:
                fig_p.add_trace(go.Scatter(x=sells["date"], y=sells["price"], mode="markers", marker_symbol="triangle-down", marker_color="red", marker_size=10, name="Sells"))
        fig_p.update_layout(height=420, margin=dict(l=10, r=10, t=20, b=20))
        st.plotly_chart(fig_p, use_container_width=True)
    else:
        st.info("Trade records do not contain 'price' to plot.")


st.subheader("Trades Table")
if trades_df.empty:
    st.info("No trades to display")
else:
    display_df = trades_df.copy()
    if "date" in display_df.columns:
        display_df = display_df.rename(columns={"date": "trade_time"})
    if "symbol" in display_df.columns:
        sym_options = ["All"] + sorted(display_df["symbol"].dropna().unique().tolist())
    else:
        sym_options = ["All"]
    selected_sym = st.selectbox("Filter by symbol (table)", sym_options, index=0)
    if selected_sym != "All":
        table_df = display_df[display_df["symbol"] == selected_sym].sort_values("trade_time", ascending=False).reset_index(drop=True)
    else:
        table_df = display_df.sort_values("trade_time", ascending=False).reset_index(drop=True)
    st.dataframe(table_df)

st.markdown("---")
st.caption("Equity snapshots are read from /api/equity (snapshots logged every bar). Use 'Run backtest now' in the sidebar to generate data for a symbol/strategy.")
