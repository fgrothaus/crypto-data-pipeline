import asyncio
import json
import httpx
import os
from dotenv import load_dotenv
from aio_pika import connect, Message, DeliveryMode
from models import PriceUpdate

load_dotenv()

FETCH_INTERVAL = 10

API_KEY = os.getenv("API_KEY")

BASE_URL = "https://api.coingecko.com/api/v3/simple/price"

HEADERS = {
    "accept": "application/json",
    "x-cg-demo-api-key": API_KEY
}

PARAMS = {
    "ids": "bitcoin,ethereum,solana,cardano,ripple,polkadot,dogecoin",
    "vs_currencies": "eur",
    "include_24hr_change": "true"
}

async def get_crypto_data():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(BASE_URL, headers=HEADERS, params=PARAMS)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        err_msg = json.dumps({"event": "coingecko_api_error", "status_code": e.response.status_code})
        print(err_msg)
    except Exception as e:
        err_msg = json.dumps({"event": "unexpected_error", "details": str(e)})
        print(err_msg)



async def send_rabbitmq_message():

    connection = await connect(os.getenv("RABBITMQ_CONNECTION_STRING"))

    try:
        channel = await connection.channel()
        await channel.declare_queue("crypto_prices", durable=True)

        while True:
            crypto_data = await get_crypto_data()

            if crypto_data:
                try:
                    valid_crypto_data = PriceUpdate(coins=crypto_data)
                    payload = valid_crypto_data.model_dump_json()

                    await channel.default_exchange.publish(
                            Message(
                                body=payload.encode(),
                                delivery_mode=DeliveryMode.PERSISTENT,
                                ),
                            routing_key="crypto_prices"
                        )

                    print("Sent CoinGecko Data to RabbitMQ!")
                except Exception as e:
                    print(f"Validation failed: {e}")
            else:
                print("No data received from CoinGecko, skipping RabbitMQ publish.")
            await asyncio.sleep(FETCH_INTERVAL)

    except Exception as e:
        print(f"Ingestion Loop encountered a critical error: {e}")
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(send_rabbitmq_message())
