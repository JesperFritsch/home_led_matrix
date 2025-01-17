import logging
from pathlib import Path

import websockets

log = logging.getLogger(Path(__file__).stem)

class StreamHandler:
    def __init__(self):
        self.websocket = None

    async def connect(self, uri):
        log.debug(f'Connecting to {uri}')
        self.websocket = await websockets.connect(uri)
        log.debug('Connected to websocket')

    async def disconnect(self):
        await self.websocket.close()
        log.debug('Disconnected from websocket')

    async def recive_task(self):
        while True:
            try:
                message = await self.websocket.recv()
                log.debug(f'Received message: {message}')
                yield message
            except websockets.ConnectionClosed:
                log.debug('Connection closed')
                break

    async def send(self, message: dict):
        await self.websocket.send(message)