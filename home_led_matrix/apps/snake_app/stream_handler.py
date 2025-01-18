import logging
import aiohttp
import asyncio
import websockets
from pathlib import Path
from collections import deque

from home_led_matrix.apps.snake_app.py_proto.sim_msgs_pb2 import (
    Request,
    PixelChangesReq,
    PixelChanges,
    MsgWrapper,
    MessageType,
    RunMetaData,
    RequestType,
    RunMetaDataRequest,
    RunUpdate
)

log = logging.getLogger(Path(__file__).stem)

class StreamHandler:
    def __init__(self) -> None:
        self._websocket = None
        self._min_buffer_size = 10
        self._recieved_data: deque = deque()
        self._init_data = None
        self._highest_used_step = 0
        self._last_requested_step = 0
        self._recieved_steps = 0
        self._final_step = None
        self._init_data_recieved = asyncio.Event()
        self._stream_task = None

    async def start_stream(self, run_id, host, port):
        uri = f"ws://{host}:{port}/ws/watch/{run_id}"
        await self._connect(uri)
        self._stream_task = asyncio.create_task(self._receive_task())
        await self._request_init_data()

    async def _connect(self, uri):
        log.debug(f'Connecting to {uri}')
        self._websocket = await websockets.connect(uri)
        log.debug('Connected to websocket')

    async def _disconnect(self):
        if self._websocket:
            await self._websocket.close()
        self._websocket = None
        log.debug('Disconnected from websocket')

    async def _receive_task(self):
        while True:
            try:
                data = await self._websocket.recv()
                if data == 'ping':
                    await self._websocket.send('ping'.encode())
                else:
                    await self.process_message(data)
            except websockets.exceptions.ConnectionClosed as e:
                print(f"Connection closed: {e}")
                break
            except (asyncio.CancelledError, KeyboardInterrupt):
                break

    async def process_message(self, data):
        msg = MsgWrapper()
        msg.ParseFromString(data)
        log.debug(f"recieved message: {msg}")
        if msg.type == MessageType.PIXEL_CHANGES:
            pixel_changes = PixelChanges()
            pixel_changes.ParseFromString(msg.data)
            pixel_changes = [(p.coord.x, p.coord.y, (p.color.r, p.color.g, p.color.b)) for p in pixel_changes.pixels]
            self._recieved_data.append(pixel_changes)
            self._recieved_steps += 1
            if self._recieved_steps >= self._final_step:
                await self.stop()
        if msg.type == MessageType.RUN_META_DATA:
            global meta_data
            meta_data = RunMetaData()
            meta_data.ParseFromString(msg.payload)
            self._init_data = meta_data
            self._init_data_recieved.set()
        if msg.type == MessageType.RUN_UPDATE:
            run_update = RunUpdate()
            run_update.ParseFromString(msg.payload)
            self._final_step = run_update.final_step
            log.debug(f"Final step: {self._final_step}")

    async def _request_pixel_changes(self):
        try:
            start_step = self._last_requested_step
            end_step = start_step + 10
            self._last_requested_step = end_step
            req = Request(
                type=RequestType.PIXEL_CHANGES_REQ,
                payload=PixelChangesReq(start_step=start_step, end_step=end_step).SerializeToString()
            )
            await self.send(req.SerializeToString())
        except Exception as e:
            log.error(e)

    async def _request_init_data(self):
        self._init_data_recieved.clear()
        await self.send(
            Request(
                type=RequestType.RUN_META_DATA_REQ,
                payload=RunMetaDataRequest().SerializeToString()
            ).SerializeToString()
        )
        await self._init_data_recieved.wait()

    async def send(self, data: bytes):
        await self._websocket.send(data)

    async def get_next_pixel_change(self):
        if len(self._recieved_data) < self._min_buffer_size:
            await self._request_pixel_changes()
        if self._recieved_data:
            return self._recieved_data.popleft()

    def get_init_data(self):
        return self._init_data

    async def stop(self):
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        await self._disconnect()

    def is_done(self):
        return self._stream_task is None or self._stream_task.done()

async def request_run(host, port, config) -> str:
    uri = f'http://{host}:{port}/api/request_run'
    log.debug(f"Posting to: {uri}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(uri, json=config) as resp:
                if resp.status == 200:
                    resp_json = await resp.json()
                    if resp_json['result'] != 'success':
                        log.error(f"Server could not start run with config: {config}")
                        return None
                    else:
                        return resp_json['run_id']
                else:
                    log.error(f"Server returned: {resp.status}")
                    log.debug(await resp.text())
    except Exception as e:
        log.error(e)