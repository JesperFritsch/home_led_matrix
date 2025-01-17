
from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.apps.app_interface import IAsyncApp
from home_led_matrix.apps.snake_app.stream_handler import StreamHandler


class SnakeApp(IAsyncApp):
    def __init__(self):
        self.display_handler = DisplayHandler()
        self.stream_handler = StreamHandler()
        self.nr_snakes = 7
        self.food = 15
        self.food_decay = None
        self.fps = 10
        self.map = None

    async def run(self):
        pass

    async def stop(self):
        self.display_handler.clear()
        pass

    async def set_food(self, value):
        self.food = value

    async def get_food(self):
        return self.food

    async def set_food_decay(self, value):
        self.food_decay = value

    async def get_food_decay(self):
        return self.food_decay

    async def set_fps(self, value):
        self.fps = value

    async def get_fps(self):
        return self.fps

    async def set_map(self, value):
        self.map = value

    async def get_map(self):
        return self.map

    async def set_nr_snakes(self, value):
        self.nr_snakes = value

    async def get_nr_snakes(self):
        return self.nr_snakes

    async def get_maps(self):
        raise NotImplementedError

    async def restart(self):
        raise NotImplementedError




