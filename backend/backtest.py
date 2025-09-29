import pandas as pd
from typing import Tuple, List, Dict

def simple_backtest(df: pd.DataFrame, initial_capital: float = 10000.0) -> Tuple[pd.DataFrame, float]:
    """
    Simple long-only backtest using a 'signal' column:
      - signal == 1 : buy (full allocation) if flat
      - signal == -1: sell (close) if long
      - signal == 0 : hold
    Returns (df_with_equity, final_equity).
    Attaches a simple trades list to df.attrs['trades'] for inspection.
    """
    df = df.copy()

    if "signal" not in df.columns:
        raise ValueError("DataFrame must contain a 'signal' column before backtesting.")

    def _flatten_signal(x):
        if isinstance(x, (pd.Series, list, tuple)):
            try:
                return int(x.iloc[0]) if isinstance(x, pd.Series) else int(x[0])
            except Exception:
                return 0
        return x

    df["signal"] = df["signal"].apply(_flatten_signal).fillna(0).astype(int)

    cash = float(initial_capital)
    position = 0.0
    equity_curve: List[float] = []
    trades: List[Dict] = []

    close_arr = df["Close"].values
    sig_arr = df["signal"].values

    for i, sig in enumerate(sig_arr):
        price = float(close_arr[i])

        if sig == 1 and position == 0:
            position = cash / price
            trades.append({"type": "buy", "index": df.index[i], "price": price, "shares": position})
            cash = 0.0

        elif sig == -1 and position > 0:
            cash = position * price
            trades.append({"type": "sell", "index": df.index[i], "price": price, "shares": position})
            position = 0.0

        equity = cash + position * price
        equity_curve.append(equity)

    df["equity"] = equity_curve
    final_equity = equity_curve[-1] if equity_curve else initial_capital
    df.attrs["trades"] = trades
    return df, final_equity

