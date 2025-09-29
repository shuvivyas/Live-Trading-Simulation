import os
import psycopg2
from psycopg2.extras import execute_values, Json
from contextlib import contextmanager
from datetime import datetime

DB_NAME = os.getenv("PG_DB", "trading")
DB_USER = os.getenv("PG_USER", "postgres")
DB_PASS = os.getenv("PG_PASS", "pass")
DB_HOST = os.getenv("PG_HOST", "localhost")
DB_PORT = int(os.getenv("PG_PORT", 5432))

def get_conn():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

@contextmanager
def get_cursor(commit: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def init_db():
    ddl = """
    CREATE TABLE IF NOT EXISTS trades (
        id SERIAL PRIMARY KEY,
        strategy VARCHAR(100),
        trade_type VARCHAR(10) NOT NULL,
        symbol VARCHAR(20),
        trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
        price NUMERIC(18,8) NOT NULL,
        shares NUMERIC(18,8) NOT NULL,
        cash_after NUMERIC(18,8),
        position_after NUMERIC(18,8),
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS equity_snapshots (
        id SERIAL PRIMARY KEY,
        strategy VARCHAR(100),
        symbol VARCHAR(20),
        snapshot_time TIMESTAMP WITH TIME ZONE NOT NULL,
        cash NUMERIC(18,8) NOT NULL,
        position_shares NUMERIC(18,8) NOT NULL,
        last_price NUMERIC(18,8) NOT NULL,
        equity NUMERIC(18,8) NOT NULL,
        extra JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    CREATE INDEX IF NOT EXISTS idx_equity_snapshot_time ON equity_snapshots(snapshot_time);
    CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(trade_time);
    """
    with get_cursor() as cur:
        cur.execute(ddl)

def insert_trades_bulk(trades, strategy=None, symbol=None):
    """
    trades: iterable of dicts with keys: type ('buy'/'sell'), date (datetime or ISO str), price, shares, optional cash_after, position_after, metadata (dict)
    """
    if not trades:
        return
    rows = []
    for t in trades:
        trade_time = t.get("date") or t.get("index") or t.get("trade_time")
        if isinstance(trade_time, str):
 
            trade_time = datetime.fromisoformat(trade_time)
        rows.append((
            strategy,
            t.get("type") or t.get("trade_type"),
            symbol or t.get("symbol"),
            trade_time,
            float(t.get("price")),
            float(t.get("shares")),
            t.get("cash_after"),
            t.get("position_after"),
            Json(t.get("metadata") or {})
        ))

    sql = """
    INSERT INTO trades (strategy, trade_type, symbol, trade_time, price, shares, cash_after, position_after, metadata)
    VALUES %s
    """
    with get_cursor() as cur:
        execute_values(cur, sql, rows)

def insert_equity_snapshots_bulk(snapshots, strategy=None, symbol=None):
    """
    snapshots: iterable of dicts with keys: snapshot_time, cash, position_shares, last_price, equity, extra (dict)
    """
    if not snapshots:
        return
    rows = []
    for s in snapshots:
        snap_time = s.get("snapshot_time") or s.get("date") or s.get("time")
        if isinstance(snap_time, str):
            snap_time = datetime.fromisoformat(snap_time)
        rows.append((
            strategy,
            symbol or s.get("symbol"),
            snap_time,
            float(s.get("cash")),
            float(s.get("position_shares")),
            float(s.get("last_price")),
            float(s.get("equity")),
            Json(s.get("extra") or {})
        ))

    sql = """
    INSERT INTO equity_snapshots (strategy, symbol, snapshot_time, cash, position_shares, last_price, equity, extra)
    VALUES %s
    """
    with get_cursor() as cur:
        execute_values(cur, sql, rows)
