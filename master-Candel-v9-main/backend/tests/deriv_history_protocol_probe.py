import asyncio
import json
import os

import websockets
from dotenv import dotenv_values


def env_value(key: str) -> str:
    value = os.environ.get(key)
    if value:
        return value.strip().strip("'")
    value = dotenv_values("/app/backend/.env").get(key)
    if not value:
        raise RuntimeError(f"Missing env key: {key}")
    return str(value).strip().strip("'")


async def fetch(body):
    url = env_value("DERIV_WS_URL")
    async with websockets.connect(url, open_timeout=15, close_timeout=3) as ws:
        await ws.send(json.dumps(body))
        return json.loads(await asyncio.wait_for(ws.recv(), 20))


async def main():
    symbol = "frxEURUSD"
    base = {"ticks_history": symbol, "end": "latest", "count": 300, "style": "candles", "granularity": 60}
    with_subscribe_zero = await fetch({**base, "subscribe": 0})
    without_subscribe = await fetch(base)
    print(json.dumps({
        "with_subscribe_0_has_error": bool(with_subscribe_zero.get("error") or with_subscribe_zero.get("errors")),
        "with_subscribe_0": with_subscribe_zero,
        "without_subscribe_has_error": bool(without_subscribe.get("error") or without_subscribe.get("errors")),
        "without_subscribe_msg_type": without_subscribe.get("msg_type"),
        "without_subscribe_candles": len(without_subscribe.get("candles", [])),
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
