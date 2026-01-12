"""Cosmic Rage $sphook sound protocol parser.

This module handles the Cosmic Rage-specific sound protocol where the
server sends commands in the format:
    $sphook action:path:volume:pitch:pan:id

Actions:
    play - Play a sound once
    loop - Play a sound in a loop
    stop - Stop a sound by ID

The server also sends $buffer lines for screen reader announcements.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional, Literal

from gtkmud.parsers.msp import SoundTrigger

logger = logging.getLogger(__name__)


# Base URL for Cosmic Rage sounds
COSMIC_RAGE_SOUND_URL = "http://nathantech.net:3000/CosmicRage/CosmicRageSounds/raw/branch/main/"


@dataclass
class BufferAnnouncement:
    """Screen reader announcement from server."""
    text: str


class SPHookParser:
    """Parser for Cosmic Rage $sphook sound protocol.

    The protocol uses these formats:
        $sphook play:path/to/sound:volume:pitch:pan:id
        $sphook loop:path/to/sound:volume:pitch:pan:id
        $sphook stop:na:na:na:na:id

    Also handles $buffer lines for screen reader announcements.
    """

    # Pattern for $sphook lines
    # Handle trailing whitespace/carriage returns from telnet
    SPHOOK_PATTERN = re.compile(
        r'^\$sphook\s+(\w+):([^:]+):([^:]+):([^:]+):([^:]+):([^\s:]+)\s*$',
        re.MULTILINE
    )

    # Pattern for $buffer lines (screen reader announcements)
    BUFFER_PATTERN = re.compile(
        r'^\$buffer\s+(.+?)\s*$',
        re.MULTILINE
    )

    # Pattern for soundpack version check
    VERSION_PATTERN = re.compile(
        r'^\$soundpack mudlet last version:\s*(\d+)\s*$',
        re.MULTILINE
    )

    def __init__(self, file_extension: str = ".wav"):
        """Initialize parser.

        Args:
            file_extension: Sound file extension to use (.wav or .ogg).
        """
        self.file_extension = file_extension

    def extract_triggers(
        self, text: str
    ) -> tuple[str, list[SoundTrigger], list[BufferAnnouncement]]:
        """Extract $sphook triggers and $buffer announcements from text.

        Args:
            text: Input text potentially containing $sphook commands.

        Returns:
            Tuple of (cleaned text, list of sound triggers, list of announcements).
        """
        triggers = []
        announcements = []
        cleaned = text

        # Extract $sphook commands
        for match in self.SPHOOK_PATTERN.finditer(text):
            trigger = self._parse_sphook(match)
            if trigger:
                triggers.append(trigger)
                logger.info(f"SPHook: {match.group(1)} {trigger.filename} vol={trigger.volume} url={trigger.url}")

        # Remove $sphook lines (including the whole line with newline)
        cleaned = re.sub(r'^.*\$sphook\s+\w+:[^\n]*\n?', '', cleaned, flags=re.MULTILINE)

        # Extract $buffer announcements
        for match in self.BUFFER_PATTERN.finditer(cleaned):
            announcement_text = match.group(1).strip()
            if announcement_text:
                announcements.append(BufferAnnouncement(text=announcement_text))
                logger.debug(f"Buffer announcement: {announcement_text[:50]}...")

        # Remove $buffer lines (including the whole line with newline)
        cleaned = re.sub(r'^.*\$buffer\s+[^\n]*\n?', '', cleaned, flags=re.MULTILINE)

        # Remove version check lines
        cleaned = re.sub(r'^.*\$soundpack mudlet[^\n]*\n?', '', cleaned, flags=re.MULTILINE)

        # Clean up multiple consecutive newlines (including \r)
        cleaned = re.sub(r'[\r\n]+', '\n', cleaned)

        # Remove leading newline if present
        cleaned = cleaned.lstrip('\n')

        return cleaned, triggers, announcements

    def _parse_sphook(self, match: re.Match) -> Optional[SoundTrigger]:
        """Parse a $sphook match into a SoundTrigger.

        Args:
            match: Regex match object.

        Returns:
            SoundTrigger or None if invalid.
        """
        action = match.group(1).lower()
        path = match.group(2)
        volume_str = match.group(3)
        # pitch and pan (groups 4 and 5) are not used in Mudlet either
        sound_id = match.group(6)

        # Parse volume
        try:
            volume = int(volume_str)
            volume = max(0, min(100, volume))
        except (ValueError, TypeError):
            volume = 50

        # Handle actions
        if action == "stop":
            # Stop command - return a trigger with filename "off"
            return SoundTrigger(
                type="sound",
                filename="off",
                volume=volume,
                loops=0,
                sound_type=sound_id,  # Use sound_type to store the ID
            )

        elif action in ("play", "loop"):
            # Build the filename with extension
            ext = self.file_extension
            if not ext.startswith('.'):
                ext = '.' + ext

            # Determine base directory (wav or ogg)
            base_dir = "wav" if ext == ".wav" else ext[1:]
            filename = f"{path}{ext}"

            # Build full URL
            url = f"{COSMIC_RAGE_SOUND_URL}{base_dir}/"

            loops = -1 if action == "loop" else 1

            # Check if this is an ambience based on path
            # Cosmic Rage uses "ambiances/" or "ambiences/" for ambient sounds
            path_lower = path.lower()
            is_ambience = "ambiance" in path_lower or "ambience" in path_lower
            trigger_type = "ambience" if is_ambience else "sound"

            return SoundTrigger(
                type=trigger_type,
                filename=filename,
                volume=volume,
                loops=loops,
                url=url,
                sound_type=sound_id,  # Store ID for stop matching
            )

        return None


class SPHookState:
    """Tracks active sounds by ID for stop matching."""

    def __init__(self):
        self._active_sounds: dict[str, str] = {}  # id -> filename

    def register_sound(self, trigger: SoundTrigger):
        """Register a playing sound.

        Args:
            trigger: The sound trigger being played.
        """
        if trigger.sound_type and not trigger.is_stop:
            self._active_sounds[trigger.sound_type] = trigger.filename

    def unregister_sound(self, sound_id: str) -> Optional[str]:
        """Unregister and return the filename for a sound ID.

        Args:
            sound_id: The sound ID to stop.

        Returns:
            The filename that was playing, or None.
        """
        return self._active_sounds.pop(sound_id, None)

    def get_active_sounds(self) -> dict[str, str]:
        """Get all active sounds."""
        return dict(self._active_sounds)
