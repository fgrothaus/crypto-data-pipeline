from pydantic import BaseModel

class PriceUpdate(BaseModel):
    coin: str
    price_eur: float
    change_24h: float