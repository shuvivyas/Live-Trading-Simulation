from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sqlalchemy.orm import Session
from decimal import Decimal
import json
from datetime import datetime

from .database import SessionLocal, get_db  
from .models import Trade, EquitySnapshot   

app = FastAPI(title="Algo Trader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _decimal_to_float(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return v

def _iso(dt):
    try:
        return dt.isoformat()
    except Exception:
        return None
    
def serialize_trade(row):
    meta = getattr(row, "meta", None) or getattr(row, "extra", None)
    if not isinstance(meta, dict):
        meta = {}
    return {
        "id": getattr(row, "id", None),
        "strategy": getattr(row, "strategy", None),
        "trade_type": getattr(row, "trade_type", None),
        "symbol": getattr(row, "symbol", None),
        "trade_time": _iso(getattr(row, "trade_time", None)),
        "price": _decimal_to_float(getattr(row, "price", None)),
        "shares": _decimal_to_float(getattr(row, "shares", None)),
        "cash_after": _decimal_to_float(getattr(row, "cash_after", None)),
        "position_after": _decimal_to_float(getattr(row, "position_after", None)),
        "metadata": meta,
        "created_at": _iso(getattr(row, "created_at", None))
    }

def serialize_snapshot(row: EquitySnapshot):
    return {
        "id": row.id,
        "strategy": row.strategy,
        "symbol": row.symbol,
        "snapshot_time": row.snapshot_time.isoformat() if row.snapshot_time else None,
        "cash": _decimal_to_float(row.cash),
        "position_shares": _decimal_to_float(row.position_shares),
        "last_price": _decimal_to_float(row.last_price),
        "equity": _decimal_to_float(row.equity),
        "extra": row.extra or {},
        "created_at": row.created_at.isoformat() if row.created_at else None
    }

@app.get("/api/trades", summary="Get trades", response_model=List[dict])
def get_trades(
    symbol: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    since: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(Trade)
    if symbol:
        q = q.filter(Trade.symbol == symbol)
    if strategy:
        q = q.filter(Trade.strategy == strategy)
    if since:
        q = q.filter(Trade.trade_time >= since)
    q = q.order_by(Trade.trade_time.asc()).limit(limit)
    rows = q.all()
    return [serialize_trade(r) for r in rows]

@app.get("/api/equity", summary="Get equity snapshots", response_model=List[dict])
def get_equity(
    symbol: Optional[str] = Query(None),
    strategy: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=20000),
    since: Optional[datetime] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(EquitySnapshot)
    if symbol:
        q = q.filter(EquitySnapshot.symbol == symbol)
    if strategy:
        q = q.filter(EquitySnapshot.strategy == strategy)
    if since:
        q = q.filter(EquitySnapshot.snapshot_time >= since)
    q = q.order_by(EquitySnapshot.snapshot_time.asc()).limit(limit)
    rows = q.all()
    return [serialize_snapshot(r) for r in rows]

@app.get("/api/portfolio", summary="Latest portfolio snapshot")
def get_portfolio(symbol: Optional[str] = None, strategy: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(EquitySnapshot)
    if symbol:
        q = q.filter(EquitySnapshot.symbol == symbol)
    if strategy:
        q = q.filter(EquitySnapshot.strategy == strategy)
    row = q.order_by(EquitySnapshot.snapshot_time.desc()).first()
    if not row:
        raise HTTPException(404, detail="No snapshots found")
    return serialize_snapshot(row)


from .paper_trading import PaperTrader
from .strategies import sma_crossover, rsi_strategy
import yfinance as yf

@app.get("/api/run_strategy")
def run_strategy(symbol: str = "AAPL", strategy: str = "sma_crossover"):
    
    data = yf.download(symbol, period="6mo", interval="1d")
    trader = PaperTrader(initial_cash=10000, strategy=strategy, symbol=symbol)
    portfolio, trades = trader.run_strategy(data)

    return {
        "symbol": symbol,
        "strategy": strategy,
        "portfolio": portfolio,
        "trades": trades
    }
    
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    async def broadcast(self, message: str):
        for conn in self.active_connections:
            try:
                await conn.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.websocket("/ws/snapshots")
async def ws_snapshots(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(ws)
