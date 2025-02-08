import logging
import json

from abc import ABC, abstractmethod
from typing import Optional, Callable, List, Dict, Any
from pathlib import Path

log = logging.getLogger(Path(__file__).stem)


class Message:

    def __init__(self):
        self.type = None

    @classmethod
    def from_json(cls, json_str: str):
        instance = cls()
        instance.__dict__ = json.loads(json_str)
        return instance

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, ensure_ascii=False)  # Pretty format

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return f"<{self.__class__.__name__} {self.__str__()}>"


class Request(Message):

    def __init__(self):
        super().__init__()
        self.type = "request"
        self.gets = []
        self.sets = {}
        self.actions = []

    def get(self, key):
        self.gets.append(key)

    def set(self, key, value):
        self.sets[key] = value

    def action(self, action):
        self.actions.append(action)


class Response(Message):

    def __init__(self):
        super().__init__()
        self.type = "response"
        self.gets = {}
        self.sets = {}
        self.actions = {}
        self.errors = {}

    def get(self, key, value):
        self.gets[key] = value

    def set(self, key, value):
        self.sets[key] = value

    def action(self, action, result):
        self.actions[action] = result

    def error(self, key, type, error):
        self.errors[key] = {"type": type, "error": error}


class Update(Message):

    def __init__(self):
        super().__init__()
        self.type = "update"
        self.updates = {}

    def update(self, key, value):
        self.updates[key] = value


class NoHandlerError(Exception):
    pass


class IMessageHandler(ABC):

    @abstractmethod
    async def handle_msg(self, message: Request) -> Response:
        pass

    @abstractmethod
    def add_handlers(
            self,
            message_key: str,
            setter: Optional[Callable]=None,
            getter: Optional[Callable]=None,
            action: Optional[Callable]=None):
        pass


class MessageHandler:
    def __init__(self):
        self._get_handlers = {}
        self._set_handlers = {}
        self._action_handlers = {}

    def add_handlers(
            self,
            message_key: str,
            setter: Optional[Callable]=None,
            getter: Optional[Callable]=None,
            action: Optional[Callable]=None):

        if setter is not None:
            self._set_handlers[message_key] = setter
        if getter is not None:
            self._get_handlers[message_key] = getter
        if action is not None:
            self._action_handlers[message_key] = action

    async def handle_msg(self, message: Request) -> Response:
        response = Response()
        if "all" in message.gets:
            await self._handle_gets(self._get_handlers.keys(), response)
        else:
            await self._handle_gets(message.gets, response)
        await self._handle_sets(message.sets, response)
        await self._handle_actions(message.actions, response)
        return response

    async def _handle_gets(self, get_list: List[str], response: Response):
        for get in get_list:
            try:
                get_value = await self._get(get)
                response.get(get, get_value)
            except Exception as e:
                response.error(get, "get", str(e))

    async def _handle_sets(self, set_dict: Dict[str, Any], response: Response):
        for key, value in set_dict.items():
            try:
                await self._set(key, value)
                response.set(key, value)
            except Exception as e:
                response.error(key, "set", str(e))

    async def _handle_actions(self, action_list: List[str], response: Response):
        for action in action_list:
            try:
                await self._action(action)
                response.action(action, "result")
            except Exception as e:
                response.error(action, "action", str(e))

    def _get_handler(self, handlers, key):
        handler = handlers.get(key)
        if handler is not None:
            return handler
        else:
            log.error(f"No handler for {key}")
            raise NoHandlerError(f"No handler for {key}")

    async def _call_handler(self, handler, *args):
        try:
            return await handler(*args)
        except Exception as e:
            log.error(e, exc_info=True)
            raise e

    async def _set(self, key, value):
        handler = self._get_handler(self._set_handlers, key)
        await self._call_handler(handler, value)

    async def _get(self, key):
        handler = self._get_handler(self._get_handlers, key)
        return await self._call_handler(handler)

    async def _action(self, action):
        handler = self._get_handler(self._action_handlers, action)
        await self._call_handler(handler)