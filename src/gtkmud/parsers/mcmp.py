"""MUD Client Media Protocol (MCMP) parser.

MCMP is a GMCP-based protocol for media playback that provides
more features than MSP, including video, captions, and fade effects.
"""

from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class MediaPlayCommand:
    """MCMP Client.Media.Play command."""
    name: str
    type: Literal["sound", "music", "video"] = "sound"
    volume: int = 50
    loops: int = 1        # -1 for infinite
    priority: int = 50
    key: str = ""         # Unique identifier for this playback
    tag: str = ""         # Category tag
    url: str = ""         # Base URL for download
    fadein: int = 0       # Fade in duration (ms)
    fadeout: int = 0      # Fade out duration (ms)
    start: int = 0        # Start position (ms)
    finish: int = 0       # End position (ms), 0 = to end
    continue_: bool = True  # For music, continue or restart

    @property
    def is_stop(self) -> bool:
        """Return True if this is a stop command (name is empty or 'off')."""
        return not self.name or self.name.lower() == "off"

    @property
    def download_url(self) -> Optional[str]:
        """Get full download URL if available."""
        if self.url and self.name and not self.is_stop:
            base = self.url.rstrip('/')
            return f"{base}/{self.name}"
        return None


@dataclass
class MediaStopCommand:
    """MCMP Client.Media.Stop command."""
    name: str = ""        # Specific file to stop, empty = all
    type: Literal["sound", "music", "video", ""] = ""  # Type to stop
    key: str = ""         # Specific key to stop
    tag: str = ""         # Specific tag to stop
    fadeout: int = 0      # Fade out duration (ms)
    priority: int = -1    # Stop sounds at or below this priority


@dataclass
class MediaLoadCommand:
    """MCMP Client.Media.Load command for preloading."""
    name: str
    url: str = ""


class MCMPParser:
    """Parser for MCMP (MUD Client Media Protocol) messages.

    MCMP uses GMCP to send media commands. The relevant packages are:
    - Client.Media.Play: Start playing media
    - Client.Media.Stop: Stop playing media
    - Client.Media.Load: Preload media file
    """

    def parse_play(self, data: dict) -> Optional[MediaPlayCommand]:
        """Parse a Client.Media.Play message.

        Args:
            data: GMCP message payload as dict.

        Returns:
            Parsed MediaPlayCommand or None if invalid.
        """
        name = data.get("name", "")
        if not name:
            return None

        cmd = MediaPlayCommand(name=name)

        if "type" in data:
            type_val = data["type"].lower()
            if type_val in ("sound", "music", "video"):
                cmd.type = type_val

        if "volume" in data:
            try:
                cmd.volume = max(0, min(100, int(data["volume"])))
            except (ValueError, TypeError):
                pass

        if "loops" in data:
            try:
                cmd.loops = int(data["loops"])
            except (ValueError, TypeError):
                pass

        if "priority" in data:
            try:
                cmd.priority = max(0, min(100, int(data["priority"])))
            except (ValueError, TypeError):
                pass

        if "key" in data:
            cmd.key = str(data["key"])

        if "tag" in data:
            cmd.tag = str(data["tag"])

        if "url" in data:
            cmd.url = str(data["url"])

        if "fadein" in data:
            try:
                cmd.fadein = max(0, int(data["fadein"]))
            except (ValueError, TypeError):
                pass

        if "fadeout" in data:
            try:
                cmd.fadeout = max(0, int(data["fadeout"]))
            except (ValueError, TypeError):
                pass

        if "start" in data:
            try:
                cmd.start = max(0, int(data["start"]))
            except (ValueError, TypeError):
                pass

        if "finish" in data:
            try:
                cmd.finish = max(0, int(data["finish"]))
            except (ValueError, TypeError):
                pass

        if "continue" in data:
            cmd.continue_ = bool(data["continue"])

        return cmd

    def parse_stop(self, data: dict) -> MediaStopCommand:
        """Parse a Client.Media.Stop message.

        Args:
            data: GMCP message payload as dict.

        Returns:
            Parsed MediaStopCommand.
        """
        cmd = MediaStopCommand()

        if "name" in data:
            cmd.name = str(data["name"])

        if "type" in data:
            type_val = str(data["type"]).lower()
            if type_val in ("sound", "music", "video"):
                cmd.type = type_val

        if "key" in data:
            cmd.key = str(data["key"])

        if "tag" in data:
            cmd.tag = str(data["tag"])

        if "fadeout" in data:
            try:
                cmd.fadeout = max(0, int(data["fadeout"]))
            except (ValueError, TypeError):
                pass

        if "priority" in data:
            try:
                cmd.priority = int(data["priority"])
            except (ValueError, TypeError):
                pass

        return cmd

    def parse_load(self, data: dict) -> Optional[MediaLoadCommand]:
        """Parse a Client.Media.Load message.

        Args:
            data: GMCP message payload as dict.

        Returns:
            Parsed MediaLoadCommand or None if invalid.
        """
        name = data.get("name", "")
        if not name:
            return None

        return MediaLoadCommand(
            name=name,
            url=data.get("url", ""),
        )
