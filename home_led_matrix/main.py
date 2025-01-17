import argparse
import asyncio
import logging
import sys
from typing import List, Dict
from configparser import ConfigParser
from importlib import resources
from pathlib import Path

from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.socket_conn import MsgHandler
from home_led_matrix.apps.app_interface import IAsyncApp
from home_led_matrix.apps.snake_app.snake_app import SnakeApp
from home_led_matrix.apps.pixelart_app.pixelart_app import PixelArtApp

conf = ConfigParser()

with open(resources.files('home_led_matrix').joinpath('config.ini')) as f:
    conf.read_file(f)

log = logging.getLogger(Path(__file__).stem)

DEFAULT_LOG_FILE = conf["LOGGING"]["file"]
DEFAULT_LOG_LEVEL = conf["LOGGING"]["level"]
DEFAULT_SOCKET_FILE = conf["SOCKET"]["file"]
# SNAKE APP
DEFAULT_HOST = conf["SNAKE_APP"]["host"]
# PIXEL APP
DEFAULT_IMAGE_DIR = conf["PIXELART_APP"]["image_dir"]


class MissingAppError(Exception):
    pass


class AppHandler:
    def __init__(self):
        self._apps: Dict[IAsyncApp] = {}
        self._current_app: IAsyncApp = None

    def add_app(self, app_name, app: IAsyncApp):
        self._apps[app_name] = app

    def stop_current_app(self):
        self._current_app.stop()

    def set_app(self, app_name):
        next_app = self._apps.get(app_name)
        if next_app is None:
            raise MissingAppError(f"App {app_name} not found")
        self._current_app.stop()
        self._current_app = next_app
        self._current_app.run()

    def get_apps(self) -> List[str]:
        return list(self._apps.keys())

    def get_current_app(self):
        for app_name, app in self._apps.items():
            if app == self._current_app:
                return app_name


def setup_logging(log_level, log_out):
    log_level = getattr(logging, log_level.upper())
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(DEFAULT_LOG_FILE),
            logging.StreamHandler(sys.stdout) if log_out else None
        ]
    )


def cli(args):
    p = argparse.ArgumentParser(description="Home LED Matrix")
    snake_app = p.add_argument_group("Snake app")
    snake_app.add_argument("--host", default=DEFAULT_HOST, help=f"Host, default: {DEFAULT_HOST}")

    pixel_app = p.add_argument_group("Pixel Art app")
    pixel_app.add_argument("--image-dir", default=DEFAULT_IMAGE_DIR, help=f"Image directory, default: {DEFAULT_IMAGE_DIR}")

    conn = p.add_argument_group("Connection")
    conn.add_argument("--socket-file", default=DEFAULT_SOCKET_FILE, help=f"Socket file, default: {DEFAULT_SOCKET_FILE}")

    logging = p.add_argument_group("Logging")
    logging.add_argument("--log-level", default=DEFAULT_LOG_LEVEL, help=f"Log level, default: {DEFAULT_LOG_LEVEL}")
    logging.add_argument("--log-file", default=DEFAULT_LOG_FILE, help=f"Log file, default: {DEFAULT_LOG_FILE}")
    logging.add_argument("--log-out", action="store_true", help="Log to stdout")
    return p.parse_args(args)


def main():
    args = cli(sys.argv[1:])
    setup_logging(args.log_level)
    msg_handler = MsgHandler(args.socket_file)
    snake_app = SnakeApp()
    pixelart_app = PixelArtApp()
    app_handler = AppHandler()
    display_handler = DisplayHandler()
    app_handler.add_app("snake", snake_app)
    app_handler.add_app("pixelart", pixelart_app)
    app_handler.set_app("snake")

    msg_handler.add_handlers("app", app_handler.set_app, app_handler.get_current_app)
    msg_handler.add_handlers("apps", app_handler.get_apps)
    msg_handler.add_handlers("brightness", display_handler.set_brightness, display_handler.get_brightness)
    msg_handler.add_handlers("display_on", app_handler.stop_current_app)

    # Snake app message handlers
    msg_handler.add_handlers('food', snake_app.set_food, snake_app.get_food)
    msg_handler.add_handlers('food_decay', snake_app.set_food_decay, snake_app.get_food_decay)
    msg_handler.add_handlers('snakes_fps', snake_app.set_fps, snake_app.get_fps)
    msg_handler.add_handlers('snake_map', snake_app.set_map, snake_app.get_map)
    msg_handler.add_handlers('snake_maps', getter=snake_app.get_maps)
    msg_handler.add_handlers('restart_snakes', setter=snake_app.restart)
    msg_handler.add_handlers('food_decay', snake_app.set_food_decay, snake_app.get_food_decay)

    # Pixel Art app message handlers



