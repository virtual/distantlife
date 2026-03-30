import os
import redis
import sqlite3


REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
_redis_client = redis.from_url(REDIS_URL)

_sqlite_connection = sqlite3.connect("distantlife.db", check_same_thread=False)
_sqlite_connection.row_factory = sqlite3.Row


def get_redis_client():
    return _redis_client


def get_db_connection():
    return _sqlite_connection
