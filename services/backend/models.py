from pydantic import BaseModel
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Numeric, String, Integer

from database.base import Base


class CoinMetrics(BaseModel):
    eur: float
    eur_24h_change: float

class PriceUpdate(BaseModel):
    coins: dict[str, CoinMetrics]

class CryptoPriceDB(Base):
    __tablename__ = "crypto_price_history"

    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(String(50), index=True, nullable=False)
    symbol = Column(String(10), nullable=False)
    name = Column(String(100), nullable=False)
    price_eur = Column(Numeric(18, 8), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)