from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import yfinance as yf
import pandas as pd
import asyncio
import json
from .api import router

app = FastAPI(title="Trading Data Feed")

@app.get("/historical")
def get_historical(symbol: str = "AAPL", period: str = "1mo", interval: str = "1d"):
    """
    Fetch historical OHLCV data from Yahoo Finance.
    Example: /historical?symbol=AAPL&period=1mo&interval=1d
    """
    import numpy as np

    data = yf.download(symbol, period=period, interval=interval)

    if data.empty:
        return {"error": "No data found"}

    data = data.reset_index()

    records = []
    for _, row in data.iterrows():
        records.append({
            "date": str(row[0]),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0
        })

    return records

@app.websocket("/ws/market/{symbol}")
async def market_feed(ws: WebSocket, symbol: str):
    await ws.accept()
    try:
        df = yf.download(symbol, period="5d", interval="1m").reset_index()

        for _, row in df.iterrows():
            tick = {
                "time": str(row["Datetime"]),
                "open": row["Open"],
                "high": row["High"],
                "low": row["Low"],
                "close": row["Close"],
                "volume": int(row["Volume"])
            }
            await ws.send_text(json.dumps(tick))
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print(f"Client disconnected from {symbol} feed")

