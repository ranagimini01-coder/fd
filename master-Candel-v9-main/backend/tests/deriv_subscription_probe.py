import asyncio
import json
import os
import time

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


async def main():
    url = env_value("DERIV_WS_URL")
    symbols = [s.strip() for s in env_value("DERIV_SYMBOLS").split(",") if s.strip()]
    accepted = set()
    rejected = []
    start = time.time()

    async with websockets.connect(url, open_timeout=15, close_timeout=3, ping_interval=20, ping_timeout=20) as ws:
        for symbol in symbols:
            await ws.send(json.dumps({"ticks": symbol, "subscribe": 1}))
            await asyncio.sleep(0.03)

        deadline = time.time() + 12
        while time.time() < deadline and len(accepted) + len(rejected) < len(symbols):
            msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
            if msg.get("tick") and msg["tick"].get("symbol"):
                accepted.add(msg["tick"]["symbol"])
                continue
            if msg.get("error") or msg.get("errors"):
                error = msg.get("error") or msg.get("errors")
                echo = msg.get("echo_req", {})
                rejected.append(
                    {
                        "requested_symbol": echo.get("ticks"),
                        "code": error.get("code") if isinstance(error, dict) else str(error),
                        "message": error.get("message") if isinstance(error, dict) else str(error),
                        "raw": msg,
                    }
                )

    requested = set(symbols)
    print(json.dumps({
        "duration_seconds": round(time.time() - start, 2),
        "requested_count": len(symbols),
        "accepted_count": len(accepted),
        "accepted_symbols": sorted(accepted),
        "rejected_count": len(rejected),
        "rejected": rejected,
        "missing_without_response": sorted(list(requested - accepted - {r.get('requested_symbol') for r in rejected if r.get('requested_symbol')})),
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
