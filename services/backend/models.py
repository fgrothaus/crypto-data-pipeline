from pydantic import BaseModel

class CoinMetrics(BaseModel):
    eur: float
    eur_24h_change: float

class PriceUpdate(BaseModel):
    coins: dict[str, CoinMetrics]