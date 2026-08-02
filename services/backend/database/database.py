import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from typing import List, Dict, Any
from models import CryptoPriceDB, PriceUpdate
from .base import Base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Session Factory für async DB-Zugriffe
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_price_update(payload: PriceUpdate):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for coin_id, metrics in payload.coins.items():
                db_entry = CryptoPriceDB(
                    coin_id=coin_id,
                    name=coin_id.capitalize(),
                    symbol=coin_id[:3].upper(),
                    price_eur=metrics.eur
                )
                session.add(db_entry)


async def cleanup_old_prices(max_records: int = 8000):
    async with AsyncSessionLocal() as session:
        async with session.begin():
            query = text("""
                         DELETE FROM crypto_price_history
                         WHERE id NOT IN (
                             SELECT id FROM crypto_price_history
                             ORDER BY timestamp DESC
                             LIMIT :max_records
                             )
                         """)
            result = await session.execute(query, {"max_records": max_records})
            if result.rowcount > 0:
                print(f"Cleaned up {result.rowcount} old records from Postgres.")


async def get_coin_price_history(coin_id: str) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        query = text("""
                     SELECT timestamp, price_eur
                     FROM crypto_price_history
                     WHERE coin_id = :coin_id
                     ORDER BY timestamp ASC
                     """)

        result = await session.execute(query, {"coin_id": coin_id.lower()})
        return [dict(row) for row in result.mappings().all()]