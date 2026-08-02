import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from redis import asyncio as aioredis
from dotenv import load_dotenv
from redis.exceptions import RedisError
from database.database import get_coin_price_history

load_dotenv()
app = FastAPI()
redis_client = aioredis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            data_string = await redis_client.get("crypto:latest_prices")

            if data_string:
                await websocket.send_text(data_string)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print("Frontend disconnected the WebSocket-Connection.")


@app.get("/prices/history/{coin_id}")
async def get_history(coin_id: str):
    history = await get_coin_price_history(coin_id)

    if not history:
        raise HTTPException(status_code=404, detail=f"No price history found for coin '{coin_id}'")

    return history


# Liveness-Check (Anwendung lebt)
@app.get("/live")
async def liveness_check():
    return {"status": "ok"}

# Deep Readiness-Check (Abhängigkeiten prüfen)
@app.get("/ready")
async def readiness_check():
    try:
        await asyncio.wait_for(redis_client.ping(), timeout=2.0)
        return {"status": "ok", "redis": "connected"}
    except (RedisError, asyncio.TimeoutError) as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Redis connection missing: {e}",
        )