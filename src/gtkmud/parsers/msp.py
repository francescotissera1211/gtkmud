"""MUD Sound Protocol (MSP) parser."""

import re
from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class SoundTrigger:
    """Represents a parsed MSP sound or music trigger."""
    type: Literal["sound", "music"]
    filename: str
    volume: int = 100        # V: 0-100
    loops: int = 1           # L: -1 for infinite, 0 for no play
    priority: int = 50       # P: 0-100 (sound only)
    continue_: bool = True   # C: music only, whether to continue or restart
    sound_type: str = ""     # T: category/type
    url: str = ""            # U: base URL for download

    @property
    def is_stop(self) -> bool:
        """Return True if this is a stop command."""
        return self.filename.lower() == "off"

    @property
    def download_url(self) -> Optional[str]:
        """Get full download URL if available."""
        if self.url and self.filename and not self.is_stop:
            # Combine base URL with filename
            base = self.url.rstrip('/')
            return f"{base}/{self.filename}"
        return None


class MSPParser:
    """Parser for MUD Sound Protocol triggers.

    MSP triggers have the format:
        !!SOUND(filename V=volume L=loops P=priority T=type U=url)
        !!MUSIC(filename V=volume L=loops C=continue T=type U=url)

    Triggers must appear at the start of a line for security reasons.
    """

    # Pattern for MSP triggers
    # Must be at start of line (after optional CR/LF)
    SOUND_PATTERN = re.compile(
        r'^!!SOUND\(([^)]+)\)',
        re.MULTILINE | re.IGNORECASE
    )
    MUSIC_PATTERN = re.compile(
        r'^!!MUSIC\(([^)]+)\)',
        re.MULTILINE | re.IGNORECASE
    )

    # Pattern for parameters within the trigger
    PARAM_PATTERN = re.compile(r'([VLPCTU])=([^\s]+)', re.IGNORECASE)

    def extract_triggers(self, text: str) -> tuple[str, list[SoundTrigger]]:
        """Extract MSP triggers from text.

        Args:
            text: Input text potentially containing MSP triggers.

        Returns:
            Tuple of (cleaned text without triggers, list of triggers found).
        """
        triggers = []
        cleaned = text

        # Extract SOUND triggers
        for match in self.SOUND_PATTERN.finditer(text):
            trigger = self._parse_trigger("sound", match.group(1))
            if trigger:
                triggers.append(trigger)

        # Remove SOUND triggers from text
        cleaned = self.SOUND_PATTERN.sub('', cleaned)

        # Extract MUSIC triggers
        for match in self.MUSIC_PATTERN.finditer(text):
            trigger = self._parse_trigger("music", match.group(1))
            if trigger:
                triggers.append(trigger)

        # Remove MUSIC triggers from text
        cleaned = self.MUSIC_PATTERN.sub('', cleaned)

        return cleaned, triggers

    def _parse_trigger(
        self, trigger_type: Literal["sound", "music"], content: str
    ) -> Optional[SoundTrigger]:
        """Parse the content of an MSP trigger.

        Args:
            trigger_type: Either "sound" or "music".
            content: The content inside the parentheses.

        Returns:
            Parsed SoundTrigger or None if invalid.
        """
        parts = content.split()
        if not parts:
            return None

        # First part is the filename
        filename = parts[0]

        # Parse parameters
        params = {}
        param_str = ' '.join(parts[1:]) if len(parts) > 1 else ''
        for match in self.PARAM_PATTERN.finditer(param_str):
            key = match.group(1).upper()
            value = match.group(2)
            params[key] = value

        # Build trigger
        trigger = SoundTrigger(
            type=trigger_type,
            filename=filename,
        )

        # Volume (V)
        if 'V' in params:
            try:
                trigger.volume = max(0, min(100, int(params['V'])))
            except ValueError:
                pass

        # Loops (L)
        if 'L' in params:
            try:
                trigger.loops = int(params['L'])
            except ValueError:
                pass

        # Priority (P) - sound only
        if 'P' in params and trigger_type == "sound":
            try:
                trigger.priority = max(0, min(100, int(params['P'])))
            except ValueError:
                pass

        # Continue (C) - music only
        if 'C' in params and trigger_type == "music":
            trigger.continue_ = params['C'] != '0'

        # Type (T)
        if 'T' in params:
            trigger.sound_type = params['T']

        # URL (U)
        if 'U' in params:
            trigger.url = params['U']

        return trigger


class MSPState:
    """Tracks MSP state including default URL."""

    def __init__(self):
        self.default_sound_url: str = ""
        self.default_music_url: str = ""

    def apply_trigger(self, trigger: SoundTrigger) -> SoundTrigger:
        """Apply state defaults to a trigger.

        If a trigger is a stop command with a URL, that sets the default URL.
        If a trigger has no URL, use the default.

        Args:
            trigger: The trigger to process.

        Returns:
            Updated trigger with URL filled in if applicable.
        """
        if trigger.is_stop and trigger.url:
            # Stop command with URL sets the default
            if trigger.type == "sound":
                self.default_sound_url = trigger.url
            else:
                self.default_music_url = trigger.url
        elif not trigger.url:
            # Use default URL
            if trigger.type == "sound" and self.default_sound_url:
                trigger.url = self.default_sound_url
            elif trigger.type == "music" and self.default_music_url:
                trigger.url = self.default_music_url

        return trigger
