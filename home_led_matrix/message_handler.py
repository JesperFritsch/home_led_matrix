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
        return json.dumps(self.__dict__)

    def __str__(self):
        return f"Message: {self.__dict__}"


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
    def handle_msg(self, message: Request) -> Response:
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

    def handle_msg(self, message: Request) -> Response:
        log.debug(f"Handling message: {message}")
        response = Response()
        if "all" in message.gets:
            self._handle_gets(self._get_handlers.keys(), response)
        else:
            self._handle_gets(message.gets, response)
        self._handle_sets(message.sets, response)
        self._handle_actions(message.actions, response)
        return response

    def _handle_gets(self, get_list: List[str], response: Response):
        for get in get_list:
            try:
                get_value = self._get(get)
                response.get(get, get_value)
            except NoHandlerError as e:
                response.error(get, "get", str(e))
            except Exception as e:
                response.error(get, "get", str(e))

    def _handle_sets(self, set_dict: Dict[str, Any], response: Response):
        for key, value in set_dict.items():
            try:
                self._set(key, value)
                response.set(key, value)
            except NoHandlerError as e:
                response.error(key, "set", str(e))
            except Exception as e:
                response.error(key, "set", str(e))

    def _handle_actions(self, action_list: List[str], response: Response):
        for action in action_list:
            try:
                self._action(action)
                response.action(action, "result")
            except NoHandlerError as e:
                response.error(action, "action", str(e))
            except Exception as e:
                response.error(action, "action", str(e))

    def _set(self, key, value):
        handler = self._set_handlers.get(key)
        if handler is not None:
            log.debug(f"Setting {key} to {value}")
            handler(value)
        else:
            log.error(f"No handler for {key}")
            raise NoHandlerError(f"No handler for {key}")

    def _get(self, key):
        handler = self._get_handlers.get(key)
        if handler is not None:
            log.debug(f"Getting {key}")
            return handler()
        else:
            log.error(f"No handler for {key}")
            raise NoHandlerError(f"No handler for {key}")

    def _action(self, action):
        handler = self._action_handlers.get(action)
        if handler is not None:
            log.debug(f"Executing action {action}")
            handler()
        else:
            log.error(f"No handler for {action}")
            raise NoHandlerError(f"No handler for {action}")