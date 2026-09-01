"""Opt-in loopback forward proxy that records hostname tunnel byte totals.

It does not decrypt TLS, inspect page content, or capture traffic that does not use it.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from urllib.parse import urlsplit

from netwatch.core.database import Database


class LocalUsageProxy:
    """A localhost-only proxy for browsers explicitly configured to use it."""

    def __init__(self, database: Database, host: str = "127.0.0.1", port: int = 8787) -> None:
        self.database, self.host, self.port = database, host, port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: asyncio.AbstractServer | None = None
        self._log = logging.getLogger(__name__)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="netwatch-local-proxy", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._server = self._loop.run_until_complete(asyncio.start_server(self._handle, self.host, self.port))
        try:
            self._loop.run_forever()
        finally:
            if self._server:
                self._server.close()
                self._loop.run_until_complete(self._server.wait_closed())
            self._loop.close()

    async def _copy(self, source: asyncio.StreamReader, target: asyncio.StreamWriter) -> int:
        total = 0
        try:
            while data := await source.read(64 * 1024):
                total += len(data); target.write(data); await target.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        return total

    async def _handle(self, client: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
        remote_writer = None
        try:
            request = await client.readuntil(b"\r\n\r\n")
            first = request.decode("iso-8859-1").split("\r\n", 1)[0]
            method, target, _ = first.split(" ", 2)
            if method.upper() == "CONNECT":
                host, _, raw_port = target.rpartition(":"); port = int(raw_port or 443)
                remote, remote_writer = await asyncio.open_connection(host, port)
                client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n"); await client_writer.drain()
                sent, received = await asyncio.gather(self._copy(client, remote_writer), self._copy(remote, client_writer))
                self.database.record_website_usage(datetime.now(UTC), host, received, sent)
                return
            parsed = urlsplit(target); host = parsed.hostname
            if not host:
                raise ValueError("HTTP proxy request has no hostname")
            port = parsed.port or 80
            remote, remote_writer = await asyncio.open_connection(host, port)
            # Origin servers expect origin-form, while proxies receive an absolute URI.
            path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
            outbound = (f"{method} {path} HTTP/1.1\r\n" + request.decode("iso-8859-1").split("\r\n", 1)[1]).encode("iso-8859-1")
            remote_writer.write(outbound); await remote_writer.drain()
            sent, received = await asyncio.gather(self._copy(client, remote_writer), self._copy(remote, client_writer))
            self.database.record_website_usage(datetime.now(UTC), host, received, sent + len(outbound))
        except Exception as error:
            self._log.debug("Local proxy request failed: %s", error)
        finally:
            if remote_writer: remote_writer.close()
            client_writer.close()
