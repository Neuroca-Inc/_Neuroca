"""Threaded WSGI server used by the Prometheus exporter."""

from __future__ import annotations

from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer

__all__ = ["ThreadedWSGIServer"]


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    """WSGI server mixin enabling multi-threaded request handling."""

    daemon_threads = True
    allow_reuse_address = True
