"""Connection manager bridging asyncio and GTK."""

import asyncio
import logging
from typing import Callable, Optional
from gi.repository import GLib

from gtkmud.net.telnet import TelnetClient, TelnetCallbacks

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages MUD connections with GTK main loop integration.

    Bridges the asyncio-based TelnetClient with GTK's GLib main loop,
    ensuring thread-safe callbacks to the UI.
    """

    def __init__(self):
        self._client: Optional[TelnetClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # UI callbacks (called on GTK main thread)
        self.on_data: Optional[Callable[[bytes], None]] = None
        self.on_connected: Optional[Callable[[], None]] = None
        self.on_disconnected: Optional[Callable[[Optional[str]], None]] = None
        self.on_gmcp: Optional[Callable[[str, dict], None]] = None

    @property
    def connected(self) -> bool:
        """Return whether currently connected."""
        return self._client is not None and self._client.connected

    @property
    def host(self) -> str:
        """Return connected host."""
        return self._client.host if self._client else ""

    @property
    def port(self) -> int:
        """Return connected port."""
        return self._client.port if self._client else 0

    def connect(self, host: str, port: int, use_ssl: bool = False) -> None:
        """Initiate connection to a MUD server.

        Args:
            host: Server hostname.
            port: Server port.
            use_ssl: If True, connect using SSL/TLS.
        """
        if self.connected:
            self.disconnect()

        # Set up callbacks that marshal to GTK main thread
        callbacks = TelnetCallbacks(
            on_data=self._on_data,
            on_connected=self._on_connected,
            on_disconnected=self._on_disconnected,
            on_gmcp=self._on_gmcp,
        )

        self._client = TelnetClient(callbacks)

        # Run connection in asyncio
        self._ensure_loop()
        asyncio.run_coroutine_threadsafe(
            self._async_connect(host, port, use_ssl),
            self._loop
        )

    def disconnect(self) -> None:
        """Disconnect from the server."""
        if self._client and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._client.disconnect(),
                self._loop
            )

    def send(self, text: str) -> None:
        """Send text to the server.

        Args:
            text: Command text to send.
        """
        if self._client and self._client.connected and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._client.send(text),
                self._loop
            )

    def send_gmcp(self, package: str, data: dict) -> None:
        """Send a GMCP message.

        Args:
            package: GMCP package name.
            data: Data payload.
        """
        if self._client and self._client.connected:
            self._client.send_gmcp(package, data)

    def _ensure_loop(self) -> None:
        """Ensure asyncio event loop is running."""
        if self._loop is None or not self._loop.is_running():
            import threading

            def run_loop():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                self._loop.run_forever()

            thread = threading.Thread(target=run_loop, daemon=True)
            thread.start()

            # Wait for loop to start
            import time
            while self._loop is None or not self._loop.is_running():
                time.sleep(0.01)

    async def _async_connect(self, host: str, port: int, use_ssl: bool) -> None:
        """Async connection handler."""
        try:
            await self._client.connect(host, port, use_ssl=use_ssl)
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            GLib.idle_add(self._marshal_disconnected, str(e))

    def _on_data(self, data: bytes) -> None:
        """Handle incoming data from telnet client."""
        GLib.idle_add(self._marshal_data, data)

    def _on_connected(self) -> None:
        """Handle connection established."""
        GLib.idle_add(self._marshal_connected)

    def _on_disconnected(self, reason: Optional[str]) -> None:
        """Handle disconnection."""
        GLib.idle_add(self._marshal_disconnected, reason)

    def _on_gmcp(self, package: str, data: dict) -> None:
        """Handle GMCP message."""
        GLib.idle_add(self._marshal_gmcp, package, data)

    def _marshal_data(self, data: bytes) -> bool:
        """Marshal data callback to GTK main thread."""
        if self.on_data:
            self.on_data(data)
        return False  # Don't repeat

    def _marshal_connected(self) -> bool:
        """Marshal connected callback to GTK main thread."""
        if self.on_connected:
            self.on_connected()
        return False

    def _marshal_disconnected(self, reason: Optional[str]) -> bool:
        """Marshal disconnected callback to GTK main thread."""
        if self.on_disconnected:
            self.on_disconnected(reason)
        return False

    def _marshal_gmcp(self, package: str, data: dict) -> bool:
        """Marshal GMCP callback to GTK main thread."""
        if self.on_gmcp:
            self.on_gmcp(package, data)
        return False
