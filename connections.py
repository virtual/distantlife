import os
import redis
import sqlite3
import threading


REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
_redis_client = redis.from_url(REDIS_URL)

SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "distantlife.db")

_thread_local = threading.local()


def _create_sqlite_connection():
    connection = sqlite3.connect(SQLITE_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


class ThreadLocalConnectionProxy:
    def _get_connection(self):
        connection = getattr(_thread_local, "connection", None)
        if connection is None:
            connection = _create_sqlite_connection()
            _thread_local.connection = connection
        return connection

    def execute(self, *args, **kwargs):
        return self._get_connection().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._get_connection().executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._get_connection().executescript(*args, **kwargs)

    def commit(self):
        return self._get_connection().commit()

    def rollback(self):
        return self._get_connection().rollback()

    def close(self):
        connection = getattr(_thread_local, "connection", None)
        if connection is not None:
            connection.close()
            _thread_local.connection = None

    def __getattr__(self, name):
        return getattr(self._get_connection(), name)


_sqlite_connection = ThreadLocalConnectionProxy()


def get_redis_client():
    return _redis_client


def get_db_connection():
    return _sqlite_connection


def close_db_connection():
    _sqlite_connection.close()
