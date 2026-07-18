import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from redis import asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
redis_client = aioredis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

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
        print("Frontend hat die WebSocket-Verbindung getrennt.")