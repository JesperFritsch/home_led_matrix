import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional

from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.apps.app_interface import IAsyncApp
from home_led_matrix.apps.snake_app.snake_app import SnakeApp
from home_led_matrix.apps.pixelart_app.pixelart_app import PixelArtApp

log = logging.getLogger(Path(__file__).stem)

display_handler = DisplayHandler()

class MissingAppError(Exception):
    pass


class AppHandler:
    def __init__(self):
        self._apps: Dict[str, IAsyncApp] = {}
        self._current_app_task: Optional[asyncio.Task] = None
        self._current_app_name: Optional[str] = None

    def add_app(self, app_name, app: IAsyncApp):
        if not isinstance(app, IAsyncApp):
            raise ValueError("App must implement IAsyncApp")
        self._apps[app_name] = app

    def _get_current_app(self) -> Optional[IAsyncApp]:
        if self._current_app_name is not None:
            app = self._apps.get(self._current_app_name)
            if app is not None:
                return app
        return None

    async def _stop_current_app(self):
        if app := self._get_current_app():
            await app.stop()
            if self._current_app_task is not None:
                self._current_app_task.cancel()
                try:
                    await self._current_app_task
                except asyncio.CancelledError:
                    pass
            self._is_running = False
            self._current_app_task = None
            self._current_app_name = None

    async def switch_app(self, app_name):
        next_app = self._apps.get(app_name)
        if next_app is None:
            raise MissingAppError(f"App {app_name} not found")
        await self._stop_current_app()
        self._current_app_name = app_name
        self._current_app_task = asyncio.create_task(next_app.run())

    async def pause_current_app(self):
        if app := self._get_current_app():
            await app.pause()

    async def resume_current_app(self):
        if app := self._get_current_app():
            await app.resume()

    async def set_brightness(self, value):
        display_handler.set_brightness(value)
        if app := self._get_current_app():
            await app.redraw()

    async def get_brightness(self):
        return display_handler.get_brightness()

    async def display_on(self):
        if app := self._get_current_app():
            if await app.is_running():
                await app.pause()
                display_handler.clear()
            else:
                await app.resume()
                await app.redraw()

    async def get_display_on(self):
        if app := self._get_current_app():
            return await app.is_running()

    async def get_apps(self) -> List[str]:
        return list(self._apps.keys())

    async def get_current_app(self):
        return self._current_app_name

    async def shutdown(self):
        await self._stop_current_app()