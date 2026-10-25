"""Canonical API simulation only. Never opens serial, USB, GPIO or HVAC interfaces."""

import argparse
import asyncio
import json
import ssl
from pathlib import Path

import aiohttp


async def simulate(device_file, ca_file, steps):
    path = Path(device_file)
    if path.is_symlink() or path.stat().st_mode & 0o077:
        raise ValueError("private device file required")
    device = json.loads(path.read_text())
    origin = device["endpoint"]
    if not origin.startswith("https://"):
        raise ValueError("TLS endpoint required")
    context = ssl.create_default_context(cafile=ca_file)
    auth = aiohttp.BasicAuth(device["serial"], device["credential"])
    state = {
        "temperature": 21.0,
        "target_temperature": 21.0,
        "humidity": 40,
        "mode": "off",
        "action": "idle",
        "firmware": "simulator-0.1.0",
    }
    applied = set()
    async with aiohttp.ClientSession(
        auth=auth,
        connector=aiohttp.TCPConnector(ssl=context),
        timeout=aiohttp.ClientTimeout(total=10),
        raise_for_status=True,
    ) as client:
        for _ in range(steps):
            async with client.post(origin + "/v1/device/state", json=state):
                pass
            async with client.get(origin + "/v1/device/commands") as response:
                commands = (await response.json())["commands"]
            for item in commands:
                if item["id"] not in applied:
                    field = {"temperature": "target_temperature", "mode": "mode", "fan": "fan"}[
                        item["operation"]
                    ]
                    state[field] = item["value"]
                    applied.add(item["id"])
            async with client.post(origin + "/v1/device/ack", json=[c["id"] for c in commands]):
                pass
            await asyncio.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-file", required=True)
    parser.add_argument("--ca", required=True)
    parser.add_argument("--steps", type=int, default=120)
    args = parser.parse_args()
    asyncio.run(simulate(args.device_file, args.ca, args.steps))
