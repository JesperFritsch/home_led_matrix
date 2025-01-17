from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.apps.app_interface import IAsyncApp


class PixelArtApp(IAsyncApp):
    def __init__(self):
        self.display_handler = DisplayHandler()

    async def run(self):
        pass

    async def stop(self):
        self.display_handler.clear()
        pass