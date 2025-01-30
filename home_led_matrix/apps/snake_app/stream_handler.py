import logging
import aiohttp
import asyncio
import websockets
from home_led_matrix.utils import async_post_request
from typing import List, Tuple, Dict, Optional, Deque
from pathlib import Path
from collections import deque
from dataclasses import dataclass

from home_led_matrix.apps.snake_app.py_proto.sim_msgs_pb2 import (
    Request,
    BadRequest,
    PixelChangesReq,
    PixelChanges,
    StepPixelChanges,
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
class StepPixelChangesData:
    step: int
    pixel_data: Deque[List[Tuple[int, int, Tuple[int, int, int]]]]


class StreamHandler:
    def __init__(self) -> None:
        self._websocket = None
        self._min_buffer_size = 5
        self._min_batch_size = 1
        self._recieved_data: deque[StepPixelChangesData] = deque()
        self._staging_data: Dict[int, StepPixelChangesData] = {}
        self._init_data = None
        self._last_added_to_buffer = None
        self._received_steps = set()
        self._requested_steps = set()
        self._final_step = None
        self._init_data_recieved = asyncio.Event()
        self._stream_finished_event = asyncio.Event()
        self._request_more_event = asyncio.Event()
        self._receive_task = None
        self._request_task = None

    async def start_stream(self, run_id, host, port):
        self._reset()
        uri = f"ws://{host}:{port}/ws/watch/{run_id}"
        await self._connect(uri)
        self._receive_task = asyncio.create_task(self._receive_loop())
        self._request_task = asyncio.create_task(self._request_loop())
        self._request_more_event.set()
        await self._request_init_data()

    async def _connect(self, uri):
        log.debug(f'Connecting to {uri}')
        self._websocket = await websockets.connect(uri)

    async def _disconnect(self):
        if self._websocket:
            await self._websocket.close()
        self._websocket = None
        log.debug('Disconnected from websocket')

    async def _request_loop(self):
        try:
            while not self._stream_finished_event.is_set():
                await self._request_more_event.wait()
                await self._request_more_if_needed()
                self._request_more_event.clear()
        except websockets.exceptions.ConnectionClosedOK:
            log.debug("Connection closed normally")
        except websockets.exceptions.ConnectionClosedError as e:
            log.error(f"Connection closed with error: {e}")
        except Exception as e:
            log.error(e)
            log.debug("TRACE: ", exc_info=True)
        except asyncio.CancelledError:
            pass
        finally:
            await self._disconnect()

    async def _receive_loop(self):
        try:
            while not self._stream_finished_event.is_set():
                if self._websocket is not None:
                    data = await self._websocket.recv()
                    if data == 'ping':
                        await self._websocket.send('ping'.encode())
                    else:
                        self.process_message(data)
                await asyncio.sleep(0) # yield controll to the main loop
        except websockets.exceptions.ConnectionClosedOK:
            log.debug("Connection closed normally")
        except websockets.exceptions.ConnectionClosedError as e:
            log.error(f"Connection closed with error: {e}")
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except OutOfOrderError as e:
            log.error(e)
        except Exception as e:
            log.error(e)
            log.debug("TRACE: ", exc_info=True)
        finally:
            await self._disconnect()

    def process_message(self, data):
        msg = MsgWrapper()
        msg.ParseFromString(data)
        log.debug(f"recieved message: Type = {MessageType.Name(msg.type)}")
        if msg.type == MessageType.PIXEL_CHANGES:
            pixel_changes = StepPixelChanges()
            pixel_changes.ParseFromString(msg.payload)
            self._handle_pixel_changes(pixel_changes)
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
        if msg.type == MessageType.BAD_REQUEST:
            bad_request = BadRequest()
            bad_request.ParseFromString(msg.payload)
            log.error(f"Bad request: {bad_request}")
        if self._final_step is not None and self._last_added_to_buffer >= self._final_step:
            self._finish_stream()

    def _handle_pixel_changes(self, step_pixel_changes: StepPixelChanges):
        self._received_steps.add(step_pixel_changes.step)
        pixel_changes_data = deque()
        for change in step_pixel_changes.changes:
            pixel_changes_data.append([(p.coord.x, p.coord.y, (p.color.r, p.color.g, p.color.b)) for p in change.pixels])
        step_pixel_changes_obj = StepPixelChangesData(
            step=step_pixel_changes.step,
            pixel_data=pixel_changes_data
        )
        # If the step is the same as the last recieved step, append to the last recieved data
        # Otherwise, stage the data, and move it to the recieved data when it is the next step in the sequence
        if (self._last_added_to_buffer is None or step_pixel_changes.step == self._last_added_to_buffer + 1):
            self._add_to_recieved_data(step_pixel_changes_obj)
        elif step_pixel_changes.step <= self._last_added_to_buffer:
            log.debug(f"Dropping already added step: {step_pixel_changes.step}")
        else:
            self._staging_data[step_pixel_changes.step] = step_pixel_changes_obj
        self._move_staged_data()

    def _add_to_recieved_data(self, step_pixel_changes_data: StepPixelChangesData):
        if self._last_added_to_buffer is None or step_pixel_changes_data.step == self._last_added_to_buffer + 1:
            self._recieved_data.append(step_pixel_changes_data)
            self._last_added_to_buffer = step_pixel_changes_data.step
        else:
            raise OutOfOrderError(f"Added step out of order: {step_pixel_changes_data.step} after {self._last_added_to_buffer}")

    async def _request_pixel_changes(self, start_step, end_step):
        log.debug(f"Requesting: start = {start_step}, end = {end_step}")
        try:
            req = Request(
                type=RequestType.PIXEL_CHANGES_REQ,
                payload=PixelChangesReq(start_step=start_step, end_step=end_step).SerializeToString()
            )
            await self.send(req.SerializeToString())
            self._requested_steps.update(range(start_step, end_step + 1))
        except Exception as e:
            log.error(e)
            log.debug("TRACE: ", exc_info=True)

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
        if self._final_step is not None and max(self._requested_steps) >= self._final_step:
            return
        if len(self._recieved_data) < (self._min_buffer_size - self._min_batch_size):
            from_step = max(self._requested_steps) + 1 if self._requested_steps else 0
            to_step = from_step + (self._min_buffer_size - len(self._recieved_data))
            if self._final_step is not None:
                to_step = max(to_step, self._final_step)
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
        if self._websocket is not None:
            await self._websocket.send(data)

    def get_next_step_pixel_change(self) -> Optional[StepPixelChangesData]:
        self._request_more_event.set()
        if self._recieved_data:
            return self._recieved_data.popleft()

    def get_init_data(self):
        return self._init_data

    def _reset(self):
        self._recieved_data.clear()
        self._init_data_recieved.clear()
        self._stream_finished_event.clear()
        self._init_data = None
        self._received_steps = set()
        self._requested_steps = set()
        self._staging_data = {}
        self._final_step = None
        self._receive_task = None
        self._request_task = None
        self._last_added_to_buffer = None

    def _finish_stream(self):
        log.debug("Stream is stopped internally")
        self._stream_finished_event.set()

    async def stop(self):
        if self._receive_task is not None:
            log.debug("Stream is stopped from outside")
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._request_task is not None:
            self._request_task.cancel()
            try:
                await self._request_task
            except asyncio.CancelledError:
                pass

    def is_done(self):
        return self._receive_task is None or self._receive_task.done()


async def request_run(host, port, config) -> str:
    uri = f'http://{host}:{port}/api/request_run'
    log.debug(f"Posting to: {uri}")
    resp = await async_post_request(uri, config)
    if resp and resp["result"] == "success":
        return resp.get('run_id')
    else:
        log.error(f"Failed to request run: {resp}")
        return None
