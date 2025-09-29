from sqlalchemy import Column, Integer, String, Numeric, TIMESTAMP, JSON
from sqlalchemy.sql import func
from .database import Base

class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True, index=True)
    strategy = Column(String(100))
    trade_type = Column(String(10), nullable=False)
    symbol = Column(String(20))
    trade_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    price = Column(Numeric(18,8), nullable=False)
    shares = Column(Numeric(18,8), nullable=False)
    cash_after = Column(Numeric(18,8))
    position_after = Column(Numeric(18,8))
   
    meta = Column("metadata", JSON, default={})

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    strategy = Column(String(100))
    symbol = Column(String(20))
    snapshot_time = Column(TIMESTAMP(timezone=True), server_default=func.now())
    cash = Column(Numeric(18,8), nullable=False)
    position_shares = Column(Numeric(18,8), nullable=False)
    last_price = Column(Numeric(18,8), nullable=False)
    equity = Column(Numeric(18,8), nullable=False)
    extra = Column(JSON)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
