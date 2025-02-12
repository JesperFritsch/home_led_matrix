import logging
from pathlib import Path


try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
except ImportError:

    class RGBMatrixOptions:
        def __init__(self):
            self.rows = 64
            self.cols = 64
            self.chain_length = 1
            self.parallel = 1
            self.hardware_mapping = 'regular'
            self.brightness = 40
            self.gpio_slowdown = 0

    class RGBMatrix:
        def __init__(self, options):
            self.brightness = 40
        def SetPixel(self, x, y, r, g, b):
            pass
        def Clear(self):
            pass
        def SetImage(self, image, unsafe):
            pass


from home_led_matrix.utils import SingletonMeta

log = logging.getLogger(Path(__file__).stem)

class DisplayHandler(metaclass=SingletonMeta):
    def __init__(self) -> None:
        options = RGBMatrixOptions()
        options.rows = 64
        options.cols = 64
        options.brightness = 40
        options.gpio_slowdown = 1
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = 'regular'
        options.drop_privileges = False
        self._matrix = RGBMatrix(options = options)

    def set_pixels(self, pixels):
        for (x, y), color in pixels:
            self._matrix.SetPixel(x, y, *color)

    def set_pixel(self, x, y, color):
        self._matrix.SetPixel(x, y, *color)

    def clear(self):
        self._matrix.Clear()

    def set_image(self, image):
        self._matrix.SetImage(image, unsafe=False)

    def set_brightness(self, value):
        try:
            self._matrix.brightness = int(value)
        except Exception as e:
            log.error(e)

    def get_brightness(self):
        return self._matrix.brightness
