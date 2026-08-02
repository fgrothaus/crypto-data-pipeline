import asyncio
import os

from aio_pika import IncomingMessage, connect
from dotenv import load_dotenv
from pydantic import ValidationError
from redis import asyncio as aioredis
from redis.exceptions import RedisError

from models import PriceUpdate
from database.database import init_db, save_price_update, cleanup_old_prices

load_dotenv()
redis_client = aioredis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

async def process_message(message: IncomingMessage):
    async with message.process():
        try:
            valid_payload = PriceUpdate.model_validate_json(message.body)
            json_string = valid_payload.model_dump_json()
            await redis_client.set("crypto:latest_prices", json_string)
            print("Actualisation of crypto prices in redis successful")
            await save_price_update(valid_payload)
            print("Saved price update to Postgres!")
        except ValidationError as e:
            print(f"Invalid message format, skipping: {e}")
        except RedisError as e:
            print(f"Redis write failed: {e}")


async def cleanup_loop():
    while True:
        try:
            # Alle 60 Sekunden prüfen und ggf. aufräumen
            await asyncio.sleep(60)
            await cleanup_old_prices(max_records=8000)
        except Exception as e:
            print(f"Error during DB cleanup: {e}")


async def start_listening():

    while True:
        try:
            connection = await connect(os.getenv("RABBITMQ_CONNECTION_STRING"))
            print("Successfully connected to RabbitMQ!")
            await init_db()
            break
        except Exception as e:
            print(f"RabbitMQ not ready yet ({e}), retrying in 3 seconds...")
            await asyncio.sleep(3)

    asyncio.create_task(cleanup_loop())

    channel = await connection.channel()
    queue = await channel.declare_queue("crypto_prices", durable=True)

    await queue.consume(process_message)
    try:
        await asyncio.Event().wait()
    finally:
        await connection.close()
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(start_listening())