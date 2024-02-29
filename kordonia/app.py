import asyncio
import json
import logging
import random
import uuid
from datetime import datetime
from typing import Mapping

import aiohttp_cors
from aiohttp import web
from aiohttp_sse import sse_response
from redis.asyncio import Redis as redis

logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger(__name__)

_tasklist = {}


async def _publish_event(message: Mapping, *, stream_key: str = "task_progress") -> None:
    r = redis.from_url("redis://redis:6379")
    await r.xadd(stream_key, message)


async def _subscribe_event(stream_key: str = "task_progress") -> int | None:
    r = redis.from_url("redis://redis:6379")

    if (await r.xlen(stream_key)) == 0:
        log.warning(f"XLEN({stream_key}) == 0")
        return None
    
    last_stream_id = "0-0"
    streams = {stream_key: last_stream_id}
    if not (messages := await r.xread(streams, count=1)):
        log.warning(f"MSG({stream_key}): {messages}")
        return None
    
    progress = 0
    for stream_id, value in messages[0][1]:
        progress = int(value[b"progress"])
        last_stream_id = stream_id

    await r.xdel(stream_key, last_stream_id)

    return progress


async def _task(task_id: str) -> None:
    progress = 0
    while progress < 100:
        await asyncio.sleep(1)
        progress = min(100, progress + random.randrange(5, 15))
        message = {
            "time": "Server Time: " + str(datetime.now()),
            "progress": progress,
        }
        log.info(f"Task({task_id}) {message}")
        await _publish_event(message, stream_key=f"task_progress/{task_id}")
    log.info(f"Task({task_id}) done!")
    if task := _tasklist.pop(task_id, None):
        await task


async def handle(request: web.Request, *args, **kwargs) -> web.Response:
    _ = request.match_info.get("name", "Anonymous")
    return web.Response(text="Hi")


async def push(request: web.Request) -> web.Response:
    headers = {}
    headers["Access-Control-Allow-Origin"] = "*"
    task_id = str(uuid.uuid4())
    _tasklist[task_id] = asyncio.create_task(_task(task_id))
    return web.json_response({"task_id": task_id}, headers=headers)


async def stream(request: web.Request) -> web.StreamResponse:
    task_id = request.query.get("task_id", "")
    headers = {}
    headers["Access-Control-Allow-Origin"] = "*"
    # headers["Connection"] = "keep-alive"
    # headers["Content-Type"] = "text/event-stream; charset=utf-8"
    # headers["Cache-Control"] = "no-cache"
    # headers["Content-Encoding"] = "none"
    async with sse_response(request, headers=headers) as resp:
        # TODO: Subscribe redis
        progress = 0
        while progress < 100:
            progress = await _subscribe_event(f"task_progress/{task_id}") or progress
            message = json.dumps({
                "time": "Server Time: " + str(datetime.now()),
                "progress": progress,
            })
            await resp.send(message)
            await asyncio.sleep(1)
    return resp


if __name__ == "__main__":
    app = web.Application()
    cors = aiohttp_cors.setup(app, defaults={
        "*": aiohttp_cors.ResourceOptions(
            allow_credentials=False, expose_headers="*", allow_headers="*",
        ),
    })
    app.router.add_route("GET", "/", handle)
    app.router.add_route("POST", "/push", push)
    app.router.add_route("GET", "/stream", stream)
    web.run_app(app)
