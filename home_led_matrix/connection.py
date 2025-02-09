import logging
import zmq
import zmq.asyncio
import asyncio

from threading import Thread, Event
from pathlib import Path
from typing import Dict, Any, Callable
from importlib import resources
from configparser import ConfigParser

from home_led_matrix.message_handler import IMessageHandler, MessageHandler, Request, Response, Update

log = logging.getLogger(Path(__file__).stem)

conf = ConfigParser()

with open(resources.files('home_led_matrix').joinpath('config.ini')) as f:
    conf.read_file(f)


def setup_logging():
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    ch.setFormatter(formatter)
    log.addHandler(ch)


class ConnServer:

    def __init__(self,
            route_port=conf["CONNECTION"]["route_port"],
            pub_port=conf["CONNECTION"]["pub_port"],
            host=conf["CONNECTION"]["host"]):
        self._route_port = route_port
        self._pub_port = pub_port
        self._host = host
        self._context = zmq.asyncio.Context()
        self._route_socket = None
        self._pub_socket = None
        self._client_ids = set()
        self._is_running = False
        self._message_handler: IMessageHandler = None

    def set_message_handler(self, handler: IMessageHandler):
        self._message_handler = handler

    async def _handle_message(self, message: Request) -> Response:
        return await self._message_handler.handle_msg(message)

    async def _send_update(self, response: Response):
        update = Update()
        for key, value in response.sets.items():
            update.update(key, value)
        await self._pub_socket.send_string(update.to_json())

    async def _loop(self):
        try:
            while self._is_running:
                client_id, message = await self._route_socket.recv_multipart()
                request = Request.from_json(message.decode())
                log.debug(f"Received from '{client_id.hex()}': {request}")

                if client_id not in self._client_ids:
                    self._client_ids.add(client_id)
                    log.info(f"New client connected: {client_id.hex()}")

                response = await self._handle_message(request)
                if response.sets:
                    await self._send_update(response)

                resp = [client_id, response.to_json().encode()]
                await self._route_socket.send_multipart(resp)
        except KeyboardInterrupt:
            pass
        except zmq.ZMQError as e:
            log.error(e, exc_info=True)
        finally:
            await self._cleanup()

    async def start(self):
        try:
            if self._message_handler is None:
                raise ValueError("Message handler not set")
            log.info("Starting connection server")
            self._route_socket = self._context.socket(zmq.ROUTER)
            self._route_socket.bind(f"tcp://{self._host}:{self._route_port}")
            self._pub_socket = self._context.socket(zmq.PUB)
            self._pub_socket.bind(f"tcp://{self._host}:{self._pub_port}")
            self._is_running = True
            await self._loop()
        except Exception as e:
            log.error(e, exc_info=True)

    async def _cleanup(self):
        if self._route_socket: self._route_socket.close()
        if self._pub_socket: self._pub_socket.close()
        if self._context: self._context.term()

    def stop(self):
        log.info("Stopping connection server")
        self._is_running = False


class ConnClient():

    def __init__(self,
            route_port=conf["CONNECTION"]["route_port"],
            sub_port=conf["CONNECTION"]["pub_port"],
            host=conf["CONNECTION"]["host"]):
        self._route_port = route_port
        self._sub_port = sub_port
        self._host = host
        self._context = zmq.Context()
        self._dealer_socket = self._context.socket(zmq.DEALER)
        self._dealer_socket.setsockopt(zmq.LINGER, 5000)
        self._dealer_socket.connect(f"tcp://{self._host}:{self._route_port}")
        self._sub_socket = None
        self._update_handler: Callable = None
        self._listen_thread = None
        self._stop_listening_event = Event()

    def _listen_loop(self):
        try:
            while not self._stop_listening_event.is_set():
                message = self._sub_socket.recv_string()
                update = Update.from_json(message)
                log.debug(f"Received update: {update}")
                self._update_handler(update.updates)
        except zmq.ZMQError as e:
            log.error(e)
        finally:
            self._sub_socket.close()

    def set_update_handler(self, handler: Callable):
        """ Handler should accept a message_handler.Update object, and do whatever it needs to do with it """
        self._update_handler = handler

    def stop_listening(self):
        self._stop_listening_event.set()

    def start_listening(self):
        if self._update_handler is None:
            raise ValueError("Update handler not set, set it with 'set_update_handler'")
        self._sub_socket = self._context.socket(zmq.SUB)
        self._sub_socket.connect(f"tcp://{self._host}:{self._sub_port}")
        self._sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._listen_thread = Thread(target=self._listen_loop)
        self._listen_thread.daemon = True
        self._listen_thread.start()

    def _send_message(self, message: Request):
        try:
            self._dealer_socket.send_string(message.to_json())
        except zmq.ZMQError as e:
            log.error(e)

    def request(self, message: Request) -> Response:
        self._send_message(message)
        if self._dealer_socket.poll(3000) == zmq.POLLIN:
            frames = self._dealer_socket.recv_multipart()
            print(frames)
            if len(frames) == 2:
                response = frames[1].decode()
            else:
                response = frames[0].decode()
            log.debug(f"Received response: {response}")
            return Response.from_json(response)
        else:
            log.error("No response received")
            return Response()


if __name__ == "__main__":
    setup_logging()
    server = ConnServer()
    msg_handler = MessageHandler()
    msg_handler.add_handlers("test", action=lambda: print("test action"), getter=lambda: "test getter", setter=lambda x: print(f"test setter: {x}"))
    server.set_message_handler(msg_handler)
    asyncio.run(server.start())