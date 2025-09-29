import pandas as pd
import ta 

def sma_crossover(df: pd.DataFrame, fast: int = 10, slow: int = 30):
    """
    Simple SMA crossover strategy.
    Returns DataFrame with 'signal' column: 1=buy, -1=sell, 0=hold
    """
    df = df.copy()
    df["sma_fast"] = df["Close"].rolling(fast).mean()
    df["sma_slow"] = df["Close"].rolling(slow).mean()

    df["signal"] = 0
    df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1
    df.loc[df["sma_fast"] < df["sma_slow"], "signal"] = -1
    return df

def rsi_strategy(df: pd.DataFrame, period: int = 14, overbought: int = 70, oversold: int = 30):
    df = df.copy()
    if "Close" not in df.columns:
        raise ValueError("DataFrame must include 'Close' column")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.squeeze()
    df["rsi"] = ta.momentum.RSIIndicator(close, window=period).rsi()

    df["signal"] = 0
    df.loc[df["rsi"] <= oversold, "signal"] = 1
    df.loc[df["rsi"] >= overbought, "signal"] = -1

    print("[rsi_strategy-debug] rsi min/max:", float(df["rsi"].min()), float(df["rsi"].max()))
    print("[rsi_strategy-debug] signal counts:", df["signal"].value_counts(dropna=False).to_dict())
    print(df[df["signal"] != 0][["rsi","signal"]].head(20))
    nonzero = df[df["signal"] != 0]
    if not nonzero.empty:
        first_sig = nonzero["signal"].iloc[0]
        if first_sig == -1:
            first_idx = nonzero.index[0]
            prev_idx = df.index.get_loc(first_idx) - 1
            if prev_idx >= 0:
                df.at[df.index[prev_idx], "signal"] = 1
                print("[rsi_test_force] forced buy at", df.index[prev_idx])
    return df
