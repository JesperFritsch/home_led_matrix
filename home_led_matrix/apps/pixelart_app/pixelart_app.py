from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.apps.app_interface import IAsyncApp


class PixelArtApp(IAsyncApp):
    def __init__(self, image_dir: str):
        self.image_dir = image_dir
        self.display_handler = DisplayHandler()
        self._is_running = False

    async def run(self):
        self._is_running = True

    async def stop(self):
        self._is_running = False
        self.display_handler.clear()

    async def pause(self):
        self._is_running = False
        self.display_handler.clear()

    async def resume(self):
        self._is_running = True

    async def redraw(self):
        pass

    async def is_running(self):
        return self._is_running