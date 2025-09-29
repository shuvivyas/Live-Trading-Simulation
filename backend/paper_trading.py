from typing import List, Dict, Optional
import pandas as pd
from .strategies import sma_crossover, rsi_strategy
from datetime import datetime
from .models import Trade, EquitySnapshot
from .database import SessionLocal
from pathlib import Path
import json
import os
import tempfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = PROJECT_ROOT / "portfolio_state"
DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)

print(f"[paper_trading] PROJECT_ROOT={PROJECT_ROOT}, DEFAULT_STATE_DIR={DEFAULT_STATE_DIR}")

def _state_filename(symbol: str, strategy: str, state_dir: Path = DEFAULT_STATE_DIR) -> Path:
    safe_symbol = symbol.replace("/", "_").replace(" ", "_")
    safe_strategy = strategy.replace("/", "_").replace(" ", "_")
    return state_dir / f"{safe_symbol}__{safe_strategy}.json"

def load_portfolio_state(symbol: str, strategy: str, state_dir: Path = DEFAULT_STATE_DIR) -> Optional[Dict]:
    path = _state_filename(symbol, strategy, state_dir)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"[load_portfolio_state] failed to read {path}: {e}")
        return None

def save_portfolio_state(symbol: str, strategy: str, cash: float, position: float,
                         last_price: Optional[float], equity: float,
                         state_dir: Path = DEFAULT_STATE_DIR) -> bool:
    """
    Save current portfolio state to JSON file (atomic write).
    Overwrites existing file.
    """
    path = _state_filename(symbol, strategy, state_dir)
    payload = {
        "symbol": symbol,
        "strategy": strategy,
        "cash": float(cash),
        "position": float(position),
        "last_price": (float(last_price) if last_price is not None else None),
        "equity": float(equity),
        "updated_at": datetime.utcnow().isoformat()
    }
    tmpname = None
    try:
        fd, tmpname = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            json.dump(payload, tmpf, indent=2)
            tmpf.flush()
            os.fsync(tmpf.fileno())
        os.replace(tmpname, str(path))
        return True
    except Exception as e:
        print(f"[save_portfolio_state] failed to write {path}: {e}")
        try:
            if tmpname and os.path.exists(tmpname):
                os.remove(tmpname)
        except Exception:
            pass
        return False

def create_initial_state_file(symbol: str, strategy: str, initial_cash: float,
                              last_price: Optional[float] = None,
                              state_dir: Path = DEFAULT_STATE_DIR) -> bool:
    """
    Create the JSON state file with initial cash/position if missing.
    No-op if file already exists.
    """
    path = _state_filename(symbol, strategy, state_dir)
    if path.exists():
        return True
    equity = float(initial_cash if last_price is None else initial_cash)
    payload = {
        "symbol": symbol,
        "strategy": strategy,
        "cash": float(initial_cash),
        "position": 0.0,
        "last_price": (float(last_price) if last_price is not None else None),
        "equity": equity,
        "updated_at": datetime.utcnow().isoformat()
    }
    tmpname = None
    try:
        fd, tmpname = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            json.dump(payload, tmpf, indent=2)
            tmpf.flush()
            os.fsync(tmpf.fileno())
        os.replace(tmpname, str(path))
        return True
    except Exception as e:
        print(f"[create_initial_state_file] failed to create {path}: {e}")
        try:
            if tmpname and os.path.exists(tmpname):
                os.remove(tmpname)
        except Exception:
            pass
        return False

class PaperTrader:
    def __init__(self, initial_cash: float = 10000.0,
                 strategy: str = "sma_crossover", symbol: str = "AAPL",
                 resume_from_json: bool = True, state_dir: Path = DEFAULT_STATE_DIR):
        self.initial_cash = float(initial_cash)
        self.cash: float = float(initial_cash)
        self.position: float = 0.0
        self.trades: List[Dict] = []
        self.strategy = strategy
        self.symbol = symbol
        self.session = SessionLocal()
        self.state_dir = state_dir

        self.state_dir.mkdir(parents=True, exist_ok=True)

        state = None
        if resume_from_json:
            state = load_portfolio_state(symbol=self.symbol, strategy=self.strategy, state_dir=self.state_dir)
            if state:
                try:
                    self.cash = float(state.get("cash", self.cash))
                    self.position = float(state.get("position", self.position))
                    print(f"[PaperTrader] Resumed from JSON state: cash={self.cash}, position={self.position}")
                except Exception as e:
                    print("[PaperTrader] failed to parse JSON state, starting fresh:", e)

        if not state:
            created = create_initial_state_file(self.symbol, self.strategy, self.initial_cash,
                                                last_price=None, state_dir=self.state_dir)
            if created:
                print(f"[PaperTrader] Created initial JSON state for {self.symbol}/{self.strategy} at {self.state_dir}")
            else:
                print(f"[PaperTrader] Could not create initial JSON state for {self.symbol}/{self.strategy}")

    def log_trade(self, trade_type, date, price, shares):
        try:
            trade = Trade(
                strategy=self.strategy,
                trade_type=trade_type,
                symbol=self.symbol,
                trade_time=date,
                price=price,
                shares=shares,
                cash_after=self.cash,
                position_after=self.position
            )
            self.session.add(trade)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print("[log_trade] DB error:", e)

    def log_snapshot(self, date, price, equity):
        try:
            snapshot = EquitySnapshot(
                strategy=self.strategy,
                symbol=self.symbol,
                snapshot_time=date,
                cash=self.cash,
                position_shares=self.position,
                last_price=price,
                equity=equity
            )
            self.session.add(snapshot)
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print("[log_snapshot] DB error:", e)

    def on_signal(self, date, price, signal):
        if isinstance(price, pd.Series):
            price = float(price.iloc[0])
        else:
            price = float(price)

        if isinstance(signal, (pd.Series, list, tuple)):
            try:
                signal = int(signal.iloc[0]) if isinstance(signal, pd.Series) else int(signal[0])
            except Exception:
                signal = int(signal)
        else:
            signal = int(signal)

        if signal == 1 and self.position == 0:
            shares = self.cash / price if price > 0 else 0.0
            self.position = shares
            self.cash = 0.0
            self.trades.append({
                "type": "buy",
                "date": date,
                "price": price,
                "shares": shares,
                "symbol": self.symbol
            })
            self.log_trade("buy", date, price, shares)

        elif signal == -1 and self.position > 0:
            shares = self.position
            proceeds = shares * price
            self.cash = proceeds
            self.trades.append({
                "type": "sell",
                "date": date,
                "price": price,
                "shares": shares,
                "symbol": self.symbol
            })
            self.log_trade("sell", date, price, shares)
            self.position = 0.0

        equity = float(self.cash + self.position * price)

        try:
            self.log_snapshot(date, price, equity)
        except Exception as e:
            print("[on_signal] log_snapshot error:", e)

        saved = save_portfolio_state(symbol=self.symbol,
                                     strategy=self.strategy,
                                     cash=self.cash,
                                     position=self.position,
                                     last_price=price,
                                     equity=equity,
                                     state_dir=self.state_dir)
        if not saved:
            print("[PaperTrader] Warning: failed to persist JSON portfolio state.")

    def get_portfolio(self, price: float):
        equity = float(self.cash + self.position * price)
        return {"cash": self.cash, "position": self.position, "equity": equity}

    def run_strategy(self, data: pd.DataFrame):
        """
        Runs the selected strategy (SMA or RSI) on historical data.
        Feeds signals into on_signal for simulated execution.
        Writes a snapshot (DB + JSON) for every bar so equity curve is continuous.
        """
        data = data.copy()
        if isinstance(data["Close"], pd.DataFrame):
            data["Close"] = data["Close"].iloc[:, 0]

        if self.strategy == "sma_crossover":
            signals_df = sma_crossover(data)
        elif self.strategy == "rsi":
            signals_df = rsi_strategy(data)
        else:
            raise ValueError("Unknown strategy")
        
        for i, row in signals_df.iterrows():
            price = row["Close"]
            if isinstance(price, pd.Series):
                price = float(price.iloc[0])
            else:
                price = float(price)

            self.on_signal(row.name, price, row["signal"])

            try:
                equity = float(self.cash + self.position * price)
                snap_time = row.name if hasattr(row, "name") else datetime.utcnow()
                self.log_snapshot(snap_time, price, equity)
                save_portfolio_state(symbol=self.symbol, strategy=self.strategy,
                                     cash=self.cash, position=self.position,
                                     last_price=price, equity=equity, state_dir=self.state_dir)
            except Exception as e:
                print("[run_strategy] snapshot save error:", e)

        print("Signals df head:", signals_df.head() if not signals_df.empty else "empty")
        print("Generated trades:", self.trades)

        final_price = data["Close"].iloc[-1]
        portfolio = self.get_portfolio(final_price)
        return portfolio, self.trades
