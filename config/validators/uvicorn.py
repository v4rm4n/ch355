# - ch355/config/validators/uvicorn.py

import os

def log_level(key: str, default: str) -> str:
    valid = {"DEBUG", "INFO", "WARNING", "CRITICAL"}
    val = os.getenv(key, default).upper()
    if val not in valid:
        raise ValueError(f"{key}={val!r} invalid, must be one of {valid}")
    return val

def host(key: str, default: str) -> str:
    import socket
    val = os.getenv(key, default)
    try:
        socket.inet_pton(socket.AF_INET, val)
        return val
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, val)
        return val
    except OSError:
        pass
    raise ValueError(f"{key}={val!r} is not a valid IPv4 or IPv6 address")

def port(key: str, default: int) -> int:
    val = os.getenv(key, str(default))
    try:
        port = int(val)
    except ValueError:
        raise ValueError(f"{key}={val!r} is not a valid integer")
    if not (1 <= port <= 65535):
        raise ValueError(f"{key}={port} out of range, must be 1-65535")
    return port


def reload(key: str, default: bool) -> bool:
    valid_true = {"true", "1", "yes"}
    valid_false = {"false", "0", "no"}
    val = os.getenv(key, str(default)).lower()
    if val in valid_true:
        return True
    if val in valid_false:
        return False
    raise ValueError(f"{key}={val!r} invalid, must be one of {valid_true | valid_false}")