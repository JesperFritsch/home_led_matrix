import logging
from pathlib import Path

from rgbmatrix import RGBMatrix, RGBMatrixOptions

from home_led_matrix.utils import SingletonMeta

log = logging.getLogger(Path(__file__).stem)

class DisplayHandler(metaclass=SingletonMeta):
    def __init__(self) -> None:
        options = RGBMatrixOptions()
        options.rows = 64
        options.cols = 64
        options.brightness = 40
        options.gpio_slowdown = 0
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = 'regular'
        self._matrix = RGBMatrix(options = options)

    def set_pixels(self, pixels):
        for (x, y), color in pixels:
            self._matrix.SetPixel(x, y, *color)

    async def clear(self):
        self._matrix.Clear()

    async def set_image(self, image):
        self._matrix.Clear()
        self._matrix.SetImage(image, unsafe=False)

    async def set_brightness(self, value):
        try:
            self._matrix.brightness = int(value)
        except Exception as e:
            log.error(e)

    def get_brightness(self):
        return self._matrix.brightness
