import logging
import aiohttp
import asyncio
import websockets
from typing import List, Tuple, Dict, Optional
from pathlib import Path
from collections import deque
from dataclasses import dataclass

from home_led_matrix.apps.snake_app.py_proto.sim_msgs_pb2 import (
    Request,
    BadRequest,
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


class OutOfOrderError(Exception):
    pass


@dataclass
class PixelChangesData:
    step: int
    pixel_data: List[Tuple[int, int, Tuple[int, int, int]]]


class StreamHandler:
    def __init__(self) -> None:
        self._websocket = None
        self._min_buffer_size = 10
        self._recieved_data: deque[PixelChangesData] = deque()
        self._staging_data: Dict[int, PixelChangesData] = {}
        self._init_data = None
        self._last_added_to_buffer = None
        self._recieved_steps = set()
        self._requested_steps = set()
        self._final_step = None
        self._init_data_recieved = asyncio.Event()
        self._stream_task = None

    async def start_stream(self, run_id, host, port):
        self._reset()
        uri = f"ws://{host}:{port}/ws/watch/{run_id}"
        await self._connect(uri)
        self._stream_task = asyncio.create_task(self._receive_task())
        await self._request_init_data()

    async def _connect(self, uri):
        log.debug(f'Connecting to {uri}')
        self._websocket = await websockets.connect(uri)

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
            except OutOfOrderError as e:
                log.error(e)
                break
            finally:
                await self.stop()

    async def process_message(self, data):
        msg = MsgWrapper()
        msg.ParseFromString(data)
        log.debug(f"recieved message: Type = {MessageType.Name(msg.type)}")
        if msg.type == MessageType.PIXEL_CHANGES:
            pixel_changes = PixelChanges()
            pixel_changes.ParseFromString(msg.payload)
            await self._handle_pixel_changes(pixel_changes)
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
        if msg.type == MessageType.BadRequest:
            bad_request = BadRequest()
            bad_request.ParseFromString(msg.payload)
            log.error(f"Bad request: {bad_request}")

    async def _handle_pixel_changes(self, pixel_changes: PixelChanges):
        self._recieved_steps.add(pixel_changes.step)
        pixel_changes_data = [(p.coord.x, p.coord.y, (p.color.r, p.color.g, p.color.b)) for p in pixel_changes.pixels]
        # If the step is the same as the last recieved step, append to the last recieved data
        # Otherwise, stage the data, and move it to the recieved data when it is the next step in the sequence
        if (self._last_added_to_buffer is None or pixel_changes.step == self._last_added_to_buffer + 1):
            self._add_to_recieved_data(
                PixelChangesData(
                    step=pixel_changes.step,
                    pixel_data=pixel_changes_data
                )
            )
        elif pixel_changes.step <= self._last_added_to_buffer:
            log.debug(f"Dropping already added step: {pixel_changes.step}")
        else:
            self._staging_data[pixel_changes.step] = PixelChangesData(
                step=pixel_changes.step,
                pixel_data=pixel_changes_data
            )
        if self._final_step is not None and max(self._recieved_steps) >= self._final_step:
            await self.stop()
        self._move_staged_data()

    def _add_to_recieved_data(self, pixel_changes_data: PixelChangesData):
        if self._last_added_to_buffer is None or pixel_changes_data.step == self._last_added_to_buffer + 1:
            self._recieved_data.append(pixel_changes_data)
            self._last_added_to_buffer = pixel_changes_data.step
        else:
            raise OutOfOrderError(f"Added step out of order: {pixel_changes_data.step} after {self._last_added_to_buffer}")

    async def _request_pixel_changes(self, start_step, end_step):
        try:
            req = Request(
                type=RequestType.PIXEL_CHANGES_REQ,
                payload=PixelChangesReq(start_step=start_step, end_step=end_step).SerializeToString()
            )
            await self.send(req.SerializeToString())
            self._requested_steps.update(range(start_step, end_step))
        except Exception as e:
            log.error(e)

    def _move_staged_data(self):
        while True:
            next_step = self._last_added_to_buffer + 1
            if next_step in self._staging_data:
                self._add_to_recieved_data(self._staging_data.pop(next_step))
            else:
                break

    def _create_request_ranges(self, from_step, to_step):
        ranges = []
        r_start, r_end = None, None
        for i in range(from_step, to_step + 1):
            if i not in self._requested_steps:
                if r_start is None:
                    r_start = i
                r_end = i
            else:
                if r_start is not None:
                    ranges.append((r_start, r_end))
                    r_start, r_end = None, None
        if r_start is not None:
            ranges.append((r_start, r_end))
        return ranges

    async def _request_more_if_needed(self):
        # check if we need to request more data, could be missing steps or just need more data
        if len(self._recieved_data) < self._min_buffer_size:
            from_step = self._last_added_to_buffer + 1 if self._last_added_to_buffer is not None else 0
            to_step = from_step + (self._min_buffer_size - len(self._recieved_data))
            ranges = self._create_request_ranges(from_step, to_step)
            for r in ranges:
                await self._request_pixel_changes(*r)

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

    async def get_next_pixel_change(self) -> Optional[PixelChangesData]:
        await self._request_more_if_needed()
        if self._recieved_data:
            return self._recieved_data.popleft()

    def get_init_data(self):
        return self._init_data

    def _reset(self):
        self._recieved_data.clear()
        self._init_data = None
        self._recieved_steps = set()
        self._requested_steps = set()
        self._staging_data = {}
        self._final_step = None
        self._stream_task = None
        self._last_added_to_buffer = None
        self._init_data_recieved.clear()

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