# validators/db.py

import os
import re

def redis_url(key: str, default: str) -> str:
    val = os.getenv(key, default)
    pattern = r"^rediss?://(?:[^:@]*(?::[^@]*)?@)?[^:/]+(:\d+)?(/\d+)?$"
    if not re.match(pattern, val):
        raise ValueError(f"{key}={val!r} is not a valid Redis URL, expected redis://[:password@]host[:port][/db]")
    return val

def postgres_url(key: str, default: str) -> str:
    val = os.getenv(key, default)
    pattern = r"^postgres(?:ql)?(?:\+\w+)?://(?:[^:@]*(?::[^@]*)?@)?[^:/]+(:\d+)?/[^/]+$"
    if not re.match(pattern, val):
        raise ValueError(f"{key}={val!r} is not a valid Postgres URL, expected postgresql://[user[:password]@]host[:port]/dbname")
    return val

def pool_size(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is not None:
        return int(val)
    return default

def max_overflow(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is not None:
        return int(val)
    return default