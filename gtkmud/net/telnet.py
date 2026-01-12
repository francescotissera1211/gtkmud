"""Async telnet client for MUD connections."""

import asyncio
import logging
from enum import Enum, auto
from typing import Callable, Optional
from dataclasses import dataclass, field

from gtkmud.net.protocols import (
    IAC, DONT, DO, WONT, WILL, SB, SE, GA, NOP,
    OPT_ECHO, OPT_SGA, OPT_TTYPE, OPT_NAWS, OPT_EOR,
    OPT_COMPRESS2, OPT_GMCP, OPT_MSP, OPT_MSDP,
    TERMINAL_TYPE, get_option_name,
)

logger = logging.getLogger(__name__)


class TelnetState(Enum):
    """State of the telnet parser."""
    DATA = auto()
    IAC = auto()
    WILL = auto()
    WONT = auto()
    DO = auto()
    DONT = auto()
    SB = auto()
    SB_DATA = auto()
    SB_IAC = auto()


@dataclass
class TelnetOption:
    """State of a telnet option."""
    local: bool = False   # We are doing this option
    remote: bool = False  # Remote is doing this option


@dataclass
class TelnetCallbacks:
    """Callbacks for telnet events."""
    on_data: Optional[Callable[[bytes], None]] = None
    on_connected: Optional[Callable[[], None]] = None
    on_disconnected: Optional[Callable[[Optional[str]], None]] = None
    on_gmcp: Optional[Callable[[str, dict], None]] = None
    on_msdp: Optional[Callable[[str, str], None]] = None
    on_compress_start: Optional[Callable[[], None]] = None


class TelnetClient:
    """Async telnet client with MUD protocol support.

    Features:
    - Standard telnet negotiation
    - MCCP v2 compression support
    - GMCP message handling
    - MSP negotiation
    - MSDP support
    """

    def __init__(self, callbacks: Optional[TelnetCallbacks] = None):
        self._callbacks = callbacks or TelnetCallbacks()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._host = ""
        self._port = 0

        # Parser state
        self._state = TelnetState.DATA
        self._sb_option = 0
        self._sb_data = bytearray()

        # Option states
        self._options: dict[int, TelnetOption] = {}

        # MCCP state
        self._mccp_enabled = False
        self._decompressor = None

        # Data buffer
        self._data_buffer = bytearray()

        # Read task
        self._read_task: Optional[asyncio.Task] = None

    @property
    def connected(self) -> bool:
        """Return whether client is connected."""
        return self._connected

    @property
    def host(self) -> str:
        """Return connected host."""
        return self._host

    @property
    def port(self) -> int:
        """Return connected port."""
        return self._port

    async def connect(self, host: str, port: int, use_ssl: bool = False) -> None:
        """Connect to a MUD server.

        Args:
            host: Server hostname or IP address.
            port: Server port number.
            use_ssl: If True, connect using SSL/TLS.
        """
        if self._connected:
            await self.disconnect()

        logger.info(
            f"Connecting to {host}:{port}{' (TLS)' if use_ssl else ''}"
        )
        self._host = host
        self._port = port

        try:
            ssl_context = None
            server_hostname = None
            if use_ssl:
                import ssl
                ssl_context = ssl.create_default_context()
                server_hostname = host
            self._reader, self._writer = await asyncio.open_connection(
                host,
                port,
                ssl=ssl_context,
                server_hostname=server_hostname,
            )
            self._connected = True
            logger.info(f"Connected to {host}:{port}")

            if self._callbacks.on_connected:
                self._callbacks.on_connected()

            # Start reading
            self._read_task = asyncio.create_task(self._read_loop())

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connected = False
            if self._callbacks.on_disconnected:
                self._callbacks.on_disconnected(str(e))
            raise

    async def disconnect(self) -> None:
        """Disconnect from the server."""
        if not self._connected:
            return

        logger.info("Disconnecting")
        self._connected = False

        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None

        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        # Reset state
        self._state = TelnetState.DATA
        self._options.clear()
        self._mccp_enabled = False
        self._decompressor = None

        if self._callbacks.on_disconnected:
            self._callbacks.on_disconnected(None)

    async def send(self, data: str) -> None:
        """Send text data to the server.

        Args:
            data: Text to send (will be encoded as UTF-8).
        """
        if not self._connected or not self._writer:
            logger.warning("Cannot send: not connected")
            return

        # Add newline if not present
        if not data.endswith("\n"):
            data += "\n"

        # Encode and escape IAC bytes
        encoded = data.encode("utf-8")
        escaped = encoded.replace(bytes([IAC]), bytes([IAC, IAC]))

        try:
            self._writer.write(escaped)
            await self._writer.drain()
        except Exception as e:
            logger.error(f"Send failed: {e}")
            await self.disconnect()

    async def send_raw(self, data: bytes) -> None:
        """Send raw bytes to the server.

        Args:
            data: Bytes to send (no escaping).
        """
        if not self._connected or not self._writer:
            return

        try:
            self._writer.write(data)
            await self._writer.drain()
        except Exception as e:
            logger.error(f"Send raw failed: {e}")
            await self.disconnect()

    async def _read_loop(self) -> None:
        """Main read loop for incoming data."""
        try:
            while self._connected and self._reader:
                data = await self._reader.read(4096)
                if not data:
                    # Connection closed
                    logger.info("Connection closed by server")
                    await self.disconnect()
                    return

                # Decompress if MCCP is enabled
                if self._mccp_enabled and self._decompressor:
                    try:
                        data = self._decompressor.decompress(data)
                    except Exception as e:
                        logger.error(f"Decompression failed: {e}")
                        self._mccp_enabled = False
                        self._decompressor = None

                # Parse telnet protocol
                self._parse(data)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Read error: {e}")
            await self.disconnect()

    def _parse(self, data: bytes) -> None:
        """Parse incoming telnet data.

        Args:
            data: Raw bytes from server.
        """
        for byte in data:
            if self._state == TelnetState.DATA:
                if byte == IAC:
                    self._state = TelnetState.IAC
                else:
                    self._data_buffer.append(byte)

            elif self._state == TelnetState.IAC:
                if byte == IAC:
                    # Escaped IAC
                    self._data_buffer.append(IAC)
                    self._state = TelnetState.DATA
                elif byte == WILL:
                    self._state = TelnetState.WILL
                elif byte == WONT:
                    self._state = TelnetState.WONT
                elif byte == DO:
                    self._state = TelnetState.DO
                elif byte == DONT:
                    self._state = TelnetState.DONT
                elif byte == SB:
                    self._state = TelnetState.SB
                elif byte == SE:
                    # Unexpected SE
                    self._state = TelnetState.DATA
                elif byte == GA:
                    # Go Ahead - flush buffer
                    self._flush_data()
                    self._state = TelnetState.DATA
                elif byte == NOP:
                    self._state = TelnetState.DATA
                else:
                    # Unknown command
                    self._state = TelnetState.DATA

            elif self._state == TelnetState.WILL:
                self._handle_will(byte)
                self._state = TelnetState.DATA

            elif self._state == TelnetState.WONT:
                self._handle_wont(byte)
                self._state = TelnetState.DATA

            elif self._state == TelnetState.DO:
                self._handle_do(byte)
                self._state = TelnetState.DATA

            elif self._state == TelnetState.DONT:
                self._handle_dont(byte)
                self._state = TelnetState.DATA

            elif self._state == TelnetState.SB:
                self._sb_option = byte
                self._sb_data.clear()
                self._state = TelnetState.SB_DATA

            elif self._state == TelnetState.SB_DATA:
                if byte == IAC:
                    self._state = TelnetState.SB_IAC
                else:
                    self._sb_data.append(byte)

            elif self._state == TelnetState.SB_IAC:
                if byte == SE:
                    self._handle_subnegotiation(self._sb_option, bytes(self._sb_data))
                    self._state = TelnetState.DATA
                elif byte == IAC:
                    # Escaped IAC in subnegotiation
                    self._sb_data.append(IAC)
                    self._state = TelnetState.SB_DATA
                else:
                    # Invalid, but try to recover
                    self._state = TelnetState.DATA

        # Flush any remaining data
        self._flush_data()

    def _flush_data(self) -> None:
        """Flush buffered data to callback."""
        if self._data_buffer and self._callbacks.on_data:
            self._callbacks.on_data(bytes(self._data_buffer))
        self._data_buffer.clear()

    def _get_option(self, option: int) -> TelnetOption:
        """Get or create option state."""
        if option not in self._options:
            self._options[option] = TelnetOption()
        return self._options[option]

    def _handle_will(self, option: int) -> None:
        """Handle WILL negotiation from server."""
        logger.debug(f"WILL {get_option_name(option)}")
        opt = self._get_option(option)

        # Options we accept from server
        accepted = {
            OPT_ECHO, OPT_SGA, OPT_EOR,
            OPT_COMPRESS2, OPT_GMCP, OPT_MSP, OPT_MSDP,
        }

        if option in accepted:
            if not opt.remote:
                opt.remote = True
                self._send_telnet(DO, option)

                # Special handling for COMPRESS2
                if option == OPT_COMPRESS2:
                    logger.info("MCCP v2 negotiated")
        else:
            self._send_telnet(DONT, option)

    def _handle_wont(self, option: int) -> None:
        """Handle WONT negotiation from server."""
        logger.debug(f"WONT {get_option_name(option)}")
        opt = self._get_option(option)
        if opt.remote:
            opt.remote = False
            self._send_telnet(DONT, option)

    def _handle_do(self, option: int) -> None:
        """Handle DO request from server."""
        logger.debug(f"DO {get_option_name(option)}")
        opt = self._get_option(option)

        # Options we can do
        if option == OPT_TTYPE:
            if not opt.local:
                opt.local = True
                self._send_telnet(WILL, option)
        elif option == OPT_NAWS:
            if not opt.local:
                opt.local = True
                self._send_telnet(WILL, option)
                # Send window size (default 80x24)
                self._send_naws(80, 24)
        elif option in (OPT_SGA, OPT_ECHO):
            if not opt.local:
                opt.local = True
                self._send_telnet(WILL, option)
        elif option == OPT_GMCP:
            if not opt.local:
                opt.local = True
                self._send_telnet(WILL, option)
                # Send GMCP hello
                self._send_gmcp_hello()
        else:
            self._send_telnet(WONT, option)

    def _handle_dont(self, option: int) -> None:
        """Handle DONT request from server."""
        logger.debug(f"DONT {get_option_name(option)}")
        opt = self._get_option(option)
        if opt.local:
            opt.local = False
            self._send_telnet(WONT, option)

    def _handle_subnegotiation(self, option: int, data: bytes) -> None:
        """Handle subnegotiation data."""
        logger.debug(f"SB {get_option_name(option)} data={data!r}")

        if option == OPT_TTYPE:
            # Terminal type request
            if data and data[0] == 1:  # SEND
                self._send_ttype()

        elif option == OPT_COMPRESS2:
            # MCCP starts now
            self._start_mccp()

        elif option == OPT_GMCP:
            # GMCP message
            self._handle_gmcp(data)

        elif option == OPT_MSDP:
            # MSDP message
            self._handle_msdp(data)

    def _send_telnet(self, command: int, option: int) -> None:
        """Send telnet negotiation command."""
        if self._writer:
            self._writer.write(bytes([IAC, command, option]))
            # Don't await, let it buffer

    def _send_subnegotiation(self, option: int, data: bytes) -> None:
        """Send telnet subnegotiation."""
        if self._writer:
            # Escape any IAC bytes in data
            escaped = data.replace(bytes([IAC]), bytes([IAC, IAC]))
            self._writer.write(bytes([IAC, SB, option]) + escaped + bytes([IAC, SE]))

    def _send_ttype(self) -> None:
        """Send terminal type."""
        data = bytes([0]) + TERMINAL_TYPE  # 0 = IS
        self._send_subnegotiation(OPT_TTYPE, data)
        logger.debug(f"Sent TTYPE: {TERMINAL_TYPE.decode()}")

    def _send_naws(self, width: int, height: int) -> None:
        """Send window size."""
        data = bytes([
            (width >> 8) & 0xFF, width & 0xFF,
            (height >> 8) & 0xFF, height & 0xFF,
        ])
        self._send_subnegotiation(OPT_NAWS, data)
        logger.debug(f"Sent NAWS: {width}x{height}")

    def _send_gmcp_hello(self) -> None:
        """Send GMCP hello message."""
        import json
        from gtkmud import __version__

        hello = {
            "client": "GTKMUD",
            "version": __version__,
        }
        message = f"Core.Hello {json.dumps(hello)}"
        self._send_subnegotiation(OPT_GMCP, message.encode("utf-8"))
        logger.debug(f"Sent GMCP: {message}")

        # Also send supported packages
        supports = ["Client.Media 1"]
        supports_msg = f"Core.Supports.Set {json.dumps(supports)}"
        self._send_subnegotiation(OPT_GMCP, supports_msg.encode("utf-8"))

    def _start_mccp(self) -> None:
        """Start MCCP v2 decompression."""
        import zlib
        self._decompressor = zlib.decompressobj()
        self._mccp_enabled = True
        logger.info("MCCP v2 compression started")

        if self._callbacks.on_compress_start:
            self._callbacks.on_compress_start()

    def _handle_gmcp(self, data: bytes) -> None:
        """Handle GMCP message."""
        import json

        try:
            text = data.decode("utf-8")
            # Split into package and data
            parts = text.split(" ", 1)
            package = parts[0]
            payload = {}
            if len(parts) > 1:
                try:
                    payload = json.loads(parts[1])
                except json.JSONDecodeError:
                    payload = {"raw": parts[1]}

            logger.debug(f"GMCP: {package} = {payload}")

            if self._callbacks.on_gmcp:
                self._callbacks.on_gmcp(package, payload)

        except Exception as e:
            logger.error(f"GMCP parse error: {e}")

    def _handle_msdp(self, data: bytes) -> None:
        """Handle MSDP message."""
        from gtkmud.net.protocols import MSDP_VAR, MSDP_VAL

        try:
            i = 0
            while i < len(data):
                if data[i] == MSDP_VAR:
                    # Find variable name
                    i += 1
                    name_start = i
                    while i < len(data) and data[i] != MSDP_VAL:
                        i += 1
                    name = data[name_start:i].decode("utf-8")

                    # Find value
                    if i < len(data) and data[i] == MSDP_VAL:
                        i += 1
                        value_start = i
                        while i < len(data) and data[i] != MSDP_VAR:
                            i += 1
                        value = data[value_start:i].decode("utf-8")

                        logger.debug(f"MSDP: {name} = {value}")
                        if self._callbacks.on_msdp:
                            self._callbacks.on_msdp(name, value)
                else:
                    i += 1

        except Exception as e:
            logger.error(f"MSDP parse error: {e}")

    def send_gmcp(self, package: str, data: dict) -> None:
        """Send a GMCP message.

        Args:
            package: GMCP package name.
            data: Data to send as JSON.
        """
        import json
        message = f"{package} {json.dumps(data)}"
        self._send_subnegotiation(OPT_GMCP, message.encode("utf-8"))
