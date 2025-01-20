
import logging
import aiohttp

from pathlib import Path

log = logging.getLogger(Path(__file__).stem)


class DotDict(dict):
    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError()

    def __setattr__(self, attr, value):
        self[attr] = value

    def __delattr__(self, attr):
        try:
            del self[attr]
        except KeyError:
            raise AttributeError

    def read_dict(self, other_dict):
        for k, v in other_dict.items():
            if isinstance(v, dict):
                v = DotDict(v)
            self[k] = v


class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


def convert_arg(type):
    def decorator(func):
        async def wrapper(self, value):
            try:
                value = type(value)
            except ValueError:
                log.error(f"Invalid value for {func.__name__}: {value if value is not None else 'None'}")
            return await func(self, value)
        return wrapper
    return decorator


async def async_get_request(uri):
    log.debug(f"GET request to {uri}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(uri) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    log.error(f"Server returned: {resp.status}")
                    log.debug(await resp.text())
    except Exception as e:
        log.error(e)


async def async_post_request(uri, data):
    log.debug(f"POST request to {uri}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(uri, json=data) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    log.error(f"Server returned: {resp.status}")
                    log.debug(await resp.text())
    except Exception as e:
        log.error(e)