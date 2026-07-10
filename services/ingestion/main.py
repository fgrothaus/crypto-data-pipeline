import asyncio
import json
from aio_pika import connect, Message

async def send_test_message():

    connection = await connect("amqp://guest:guest@localhost:5672/")
    channel = await connection.channel()

    queue = await channel.declare_queue("crypto_prices", durable=True)

    data = {"coin": "bitcoin", "price_eur": 58000.0, "change_24h": 1.5}

    await channel.default_exchange.publish(
            Message(body=json.dumps(data).encode()),
            routing_key="crypto_prices",
        )
    
    print(" [x] Sent Test Data to RabbitMQ!")

if __name__ == "__main__":
    asyncio.run(send_test_message())