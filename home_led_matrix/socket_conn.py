
import logging
import asyncio
import sys
import os
import json
import weakref
from configparser import ConfigParser
from pathlib import Path
from importlib import resources

conf = ConfigParser()

with open(resources.files('home_led_matrix').joinpath('config.ini')) as f:
    conf.read_file(f)

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from home_led_matrix.utils import DotDict
log = logging.getLogger(Path(__file__).stem)

class MsgHandler:
    def __init__(self, socket_file) -> None:
        self.set_handlers = DotDict()
        self.get_handlers = DotDict()
        self.socket_handler = SocketHandler(socket_file, self)
        self.default_handler = None

    def add_handlers(self, message_key, setter=None, getter=None):
        if setter is not None: self.set_handlers[message_key] = setter
        if getter is not None: self.get_handlers[message_key] = getter

    def _default_handler(self, meth_type, key, value):
        log.debug(f"Invalid/Unhandled message: {meth_type} {key} {value}")

    async def send_update(self, *msg_keys):
        message = {}
        for key in msg_keys:
            try:
                message[key] = self.get_handlers[key]()
            except KeyError:
                self._default_handler("send_update", key, None)
        await self.socket_handler.send_message(message)

    async def handle_msg(self, payload):
        tasks = []
        message = None
        for meth_type, msgs in payload.items():
            if meth_type == 'set':
                for key, value in msgs.items():
                    try:
                        tasks.append(asyncio.create_task(self.set_handlers[key](value)))
                    except KeyError:
                        if self.default_handler is not None:
                            self.default_handler(meth_type, key, value)
                        else:
                            log.debug(f'Invalid message: "{key}"')
                await asyncio.gather(*tasks)
            elif meth_type == 'get':
                if 'all' in msgs.keys():
                    message = {}
                    for get_key, getter in self.get_handlers.items():
                        try:
                            get_value = await getter()
                        except (KeyError, TypeError):
                            if self.default_handler is not None:
                                self.default_handler(meth_type, get_key, None)
                            else:
                                get_value = None
                                log.debug(f'Invalid message: "{key}"')

                        message[get_key] = get_value
                else:
                    message = {}
                    for get_key, val in msgs.items():
                        try:
                            get_value = await self.get_handlers[get_key](val)
                        except TypeError:
                            get_value = await self.get_handlers[get_key]()
                        except KeyError:
                            if self.default_handler is not None:
                                self.default_handler(meth_type, get_key, val)
                            else:
                                get_value = None
                                log.debug(f'Invalid message: "{key}"')
                    message[get_key] = get_value
        return message

    def start(self):
        return asyncio.create_task(self.socket_handler.run_loop())


class SocketHandler:
    def __init__(self, sock_file, msg_handler: MsgHandler) -> None:
        self.sock_file = sock_file
        self.connections = set()
        self.msg_handler: MsgHandler = weakref.ref(msg_handler)

    async def send_message(self, msg_dict):
        payload = json.dumps(msg_dict) + '\n'
        data = payload.encode('utf8')
        for r, w in self.connections:
            w.write(data)

    async def run_loop(self):
        while True:
            try:
                log.debug(f"Trying to connect to socket: '{self.sock_file}'")
                reader, writer = await asyncio.open_unix_connection(self.sock_file)
                self.connections.add((reader, writer))
                log.debug(f"Connected to socket: {self.sock_file}")
            except ConnectionRefusedError as e:
                log.error(f"Socket not available: {e}")
                await asyncio.sleep(20)
            except Exception as e:
                log.error(f"Error connecting: {e}")
                await asyncio.sleep(10)
            else:
                try:
                    while True:
                        data = await reader.readline()
                        if data:
                            try:
                                msg = json.loads(data)
                                log.debug(msg)
                                msg_handler = self.msg_handler()
                                response = await msg_handler.handle_msg(msg)
                                if response is not None:
                                    data_json = json.dumps(response) + '\n'
                                    data = data_json.encode('utf-8')
                                    writer.write(data)
                                    await writer.drain()
                            except Exception as e:
                                log.error('Some shit happened: ', e)
                                log.debug(response)
                        else:
                            log.debug('Connection closed')
                            break

                except asyncio.CancelledError as e:
                    log.error("Cancelled error")
                    log.error("TRACE", exc_info=True)

                finally:
                    writer.close()
                    await writer.wait_closed()
                    self.connections.remove((reader, writer))