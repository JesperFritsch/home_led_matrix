import asyncio
import numpy as np
import logging
from pathlib import Path
from typing import Optional

from home_led_matrix.utils import convert_arg
from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.apps.app_interface import IAsyncApp
from home_led_matrix.apps.snake_app.stream_handler import StreamHandler, request_run

log = logging.getLogger(Path(__file__).stem)

display_handler = DisplayHandler()

class SnakeApp(IAsyncApp):
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._stream_handler = StreamHandler()
        self._nr_snakes = 7
        self._food = 15
        self._food_decay = None
        self._fps = 10
        self._map = None
        self._current_run_id = None
        self._unpaused_event = asyncio.Event()
        self._restart_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._stream_task: Optional[asyncio.Task] = None
        self._last_frame = None

    async def main_loop(self):
        self._stop_event.clear()
        try:
            while True:
                if self._stop_event.is_set():
                    break
                if not self._unpaused_event.is_set():
                    await self._unpaused_event.wait()
                self._restart_event.clear()
                await self._request_new_run()
                await self._start_stream(self._current_run_id)
                await self._display_loop()
                # Let the final state be displayed for 10 seconds
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            self.stop()

    async def _request_new_run(self):
        config = {
            'nr_snakes': self._nr_snakes,
            'food': self._food,
            'food_decay': self._food_decay,
            'fps': self._fps,
            'map': self._map
        }
        self._current_run_id = await request_run(self._host, self._port, config)
        if self._current_run_id is None:
            raise Exception("Could not start run")

    async def _start_stream(self, run_id):
        await self._stream_handler.start_stream(run_id, self._host, self._port)
        init_data = self._stream_handler.get_init_data()
        await self.load_map(init_data)

    async def _display_frame(self, frame: np.ndarray):
        for y in range(frame.shape[0]):
            for x in range(frame.shape[1]):
                display_handler.set_pixel(x, y, frame[y, x])

    async def load_map(self, init_data):
        base_map = np.frombuffer(bytes(init_data.base_map), dtype=np.uint8).reshape(init_data.height, init_data.width)
        color_mapping = self.get_color_mapping(init_data)
        self._last_frame = np.zeros((init_data.height, init_data.width, 3), dtype=np.uint8)
        for y in range(init_data.height):
            for x in range(init_data.width):
                color = color_mapping[base_map[y, x]]
                self._last_frame[y, x] = color
        await self._display_frame(self._last_frame)

    def get_color_mapping(self, init_data):
        return {int(k): (v.r, v.g, v.b) for k, v in init_data.color_mapping.items()}

    async def _display_loop(self):
        while True:
            if self._restart_event.is_set() or self._stop_event.is_set():
                break
            if not self._unpaused_event.is_set():
                await self._unpaused_event.wait()
            pixel_changes = await self._stream_handler.get_next_pixel_change()
            if pixel_changes is None:
                if self._stream_handler.is_done():
                    break
                await asyncio.sleep(0.1)
                continue
            self._update_display(pixel_changes)

    def _update_display(self, pixel_changes):
        for x, y, color in pixel_changes:
            display_handler.set_pixel(x, y, color)
            self._last_frame[y, x] = color

    async def run(self):
        log.debug("Starting snake app")
        try:
            await self.main_loop()
        except asyncio.CancelledError:
            pass

    async def stop(self):
        self._stop_event.set()
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass

    async def pause(self):
        self._unpaused_event.clear()

    async def resume(self):
        self._unpaused_event.set()

    async def redraw(self):
        display_handler.clear()
        self._display_frame(self._last_frame)

    async def is_running(self):
        return self._unpaused_event is None or self._unpaused_event.is_set()

    @convert_arg(int)
    async def set_food(self, value):
        self._food = value

    async def get_food(self):
        return self._food

    @convert_arg(int)
    async def set_food_decay(self, value):
        self._food_decay = value

    async def get_food_decay(self):
        return self._food_decay

    @convert_arg(int)
    async def set_fps(self, value):
        self._fps = value

    async def get_fps(self):
        return self._fps

    @convert_arg(str)
    async def set_map(self, value):
        self._map = value

    async def get_map(self):
        return self._map

    @convert_arg(int)
    async def set_nr_snakes(self, value):
        self._nr_snakes = value

    async def get_nr_snakes(self):
        return self._nr_snakes

    async def get_maps(self):
        return ["default"]

    async def restart(self):
        self._restart_event.set()




