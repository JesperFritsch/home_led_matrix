import argparse
import asyncio
import logging
import sys
from configparser import ConfigParser
from importlib import resources
from pathlib import Path

from home_led_matrix.display.display_handler import DisplayHandler
from home_led_matrix.message_handler import MessageHandler
from home_led_matrix.connection import ConnServer
from home_led_matrix.apps.snake_app.snake_app import SnakeApp
from home_led_matrix.apps.pixelart_app.pixelart_app import PixelArtApp
from home_led_matrix.apps.app_handler import AppHandler

conf = ConfigParser()

with open(resources.files('home_led_matrix').joinpath('config.ini')) as f:
    conf.read_file(f)

log = logging.getLogger(Path(__file__).stem)

DEFAULT_LOG_FILE = conf["LOGGING"]["file"]
DEFAULT_LOG_LEVEL = conf["LOGGING"]["level"]
DEFAULT_CONN_HOST = conf["CONNECTION"]["host"]
DEFAULT_ROUTE_PORT = conf["CONNECTION"]["route_port"]
DEFAULT_PUB_PORT = conf["CONNECTION"]["pub_port"]
# SNAKE APP
DEFAULT_HOST = conf["SNAKE_APP"]["host"]
DEFAULT_PORT = conf["SNAKE_APP"]["port"]
# PIXEL APP
DEFAULT_IMAGE_DIR = conf["PIXELART_APP"]["image_dir"]

# Global singletons
display_handler = DisplayHandler()

def setup_logging(log_level, log_out, log_file):
    log_level = getattr(logging, log_level.upper())
    handlers = [logging.FileHandler(log_file)]
    if log_out:
        handlers.append(logging.StreamHandler(sys.stdout))
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers
    )


def cli(args):
    p = argparse.ArgumentParser(description="Home LED Matrix")
    snake_app = p.add_argument_group("Snake app")
    snake_app.add_argument("--host", default=DEFAULT_HOST, help=f"Host, default: {DEFAULT_HOST}")
    snake_app.add_argument("--port", default=DEFAULT_PORT, help=f"Port, default: {DEFAULT_PORT}")

    pixel_app = p.add_argument_group("Pixel Art app")
    pixel_app.add_argument("--image-dir", default=DEFAULT_IMAGE_DIR, help=f"Image directory, default: {DEFAULT_IMAGE_DIR}")

    conn = p.add_argument_group("Connection")
    conn.add_argument("--ctl-host", default=DEFAULT_CONN_HOST, help=f"Socket file, default: {DEFAULT_CONN_HOST}")
    conn.add_argument("--route-port", default=DEFAULT_ROUTE_PORT, help=f"Route port, default: {DEFAULT_ROUTE_PORT}")
    conn.add_argument("--pub-port", default=DEFAULT_PUB_PORT, help=f"Publish port, default: {DEFAULT_PUB_PORT}")

    logging = p.add_argument_group("Logging")
    logging.add_argument("--log-level", default=DEFAULT_LOG_LEVEL, help=f"Log level, default: {DEFAULT_LOG_LEVEL}")
    logging.add_argument("--log-file", default=DEFAULT_LOG_FILE, help=f"Log file, default: {DEFAULT_LOG_FILE}")
    logging.add_argument("--log-out", action="store_true", help="Log to stdout")
    return p.parse_args(args)


async def main(args):
    try:
        msg_handler = MessageHandler()
        conn_server = ConnServer(args.route_port, args.pub_port, args.ctl_host)
        conn_server.set_message_handler(msg_handler)
        snake_app = SnakeApp(args.host, args.port)
        pixelart_app = PixelArtApp(args.image_dir)
        app_handler = AppHandler()

        app_handler.add_app("snakes", snake_app)
        app_handler.add_app("pixelart", pixelart_app)

        # Common message handlers
        msg_handler.add_handlers("current_app", app_handler.switch_app, app_handler.get_current_app)
        msg_handler.add_handlers("apps", getter=app_handler.get_apps)
        msg_handler.add_handlers("brightness", app_handler.set_brightness, app_handler.get_brightness)
        msg_handler.add_handlers("display_on", app_handler.display_on, app_handler.get_display_on)

        # Snake app message handlers
        msg_handler.add_handlers('food', snake_app.set_food, snake_app.get_food)
        msg_handler.add_handlers('food_decay', snake_app.set_food_decay, snake_app.get_food_decay)
        msg_handler.add_handlers('snakes_fps', snake_app.set_fps, snake_app.get_fps)
        msg_handler.add_handlers('snake_map', snake_app.set_map, snake_app.get_map)
        msg_handler.add_handlers('snake_maps', getter=snake_app.get_maps)
        msg_handler.add_handlers('restart_snakes', action=snake_app.restart)
        msg_handler.add_handlers('food_decay', snake_app.set_food_decay, snake_app.get_food_decay)
        msg_handler.add_handlers('nr_snakes', snake_app.set_nr_snakes, snake_app.get_nr_snakes)

        # Pixel Art app message handlers

        await app_handler.switch_app("snakes")
        await conn_server.start()
    finally:
        display_handler.clear()
        try:
            await app_handler.shutdown()
        except Exception as e:
            log.error(e)


if __name__ == "__main__":
    args = cli(sys.argv[1:])
    setup_logging(args.log_level, args.log_out, args.log_file)
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass