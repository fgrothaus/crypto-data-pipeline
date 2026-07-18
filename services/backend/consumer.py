import os
import asyncio

from dotenv import load_dotenv
from redis import asyncio as aioredis
from aio_pika import connect, IncomingMessage
from models import PriceUpdate

load_dotenv()
redis_client = aioredis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

async def process_message(message: IncomingMessage):
    async with message.process():
        try:
            valid_payload = PriceUpdate.model_validate_json(message.body)
            json_string = valid_payload.model_dump_json()
            await redis_client.set("crypto:latest_prices", json_string)
            print("Actualisation of crypto prices in redis successful")
        except Exception as e:
            print(f"Validation failed: {e}")


async def start_listening():
    connection = await connect(os.getenv("RABBITMQ_CONNECTION_STRING"))
    channel = await connection.channel()
    queue = await channel.declare_queue("crypto_prices", durable=True)

    await queue.consume(process_message)
    try:
        await asyncio.Future()
    finally:
        await connection.close()
        await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(start_listening())