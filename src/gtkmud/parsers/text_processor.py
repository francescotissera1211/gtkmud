"""Text processing pipeline for MUD output."""

import logging
from typing import Callable, Optional
from dataclasses import dataclass

from gtkmud.parsers.ansi import ANSIParser, TextSpan
from gtkmud.parsers.msp import MSPParser, MSPState, SoundTrigger
from gtkmud.parsers.sphook import SPHookParser, SPHookState, BufferAnnouncement

logger = logging.getLogger(__name__)


@dataclass
class ProcessedText:
    """Result of processing MUD text."""
    spans: list[TextSpan]
    sound_triggers: list[SoundTrigger]
    announcements: list[BufferAnnouncement] = None
    gagged: bool = False

    def __post_init__(self):
        if self.announcements is None:
            self.announcements = []


class TextProcessor:
    """Main text processing pipeline for MUD output.

    Pipeline stages:
    1. Extract MSP triggers (!!SOUND, !!MUSIC)
    2. Extract SPHook triggers ($sphook) and announcements ($buffer)
    3. Check gags (if scripting engine available)
    4. Parse ANSI color codes
    5. Check triggers (if scripting engine available)
    """

    def __init__(self):
        self._ansi_parser = ANSIParser()
        self._msp_parser = MSPParser()
        self._msp_state = MSPState()
        self._sphook_parser = SPHookParser()
        self._sphook_state = SPHookState()

        # Optional callbacks
        self._gag_checker: Optional[Callable[[str], bool]] = None
        self._trigger_checker: Optional[Callable[[str], None]] = None

    def set_sphook_extension(self, extension: str):
        """Set the file extension for SPHook sounds.

        Args:
            extension: File extension (.wav or .ogg).
        """
        self._sphook_parser.file_extension = extension

    def set_gag_checker(self, checker: Callable[[str], bool]):
        """Set callback to check if text should be gagged.

        Args:
            checker: Function that takes text and returns True if gagged.
        """
        self._gag_checker = checker

    def set_trigger_checker(self, checker: Callable[[str], None]):
        """Set callback to check triggers against text.

        Args:
            checker: Function that takes text and processes triggers.
        """
        self._trigger_checker = checker

    def process(self, text: str) -> ProcessedText:
        """Process incoming MUD text through the pipeline.

        Args:
            text: Raw text from MUD server.

        Returns:
            ProcessedText with styled spans and extracted triggers.
        """
        # Stage 1: Extract MSP triggers
        cleaned_text, sound_triggers = self._msp_parser.extract_triggers(text)

        # Apply MSP state (default URLs)
        sound_triggers = [
            self._msp_state.apply_trigger(t) for t in sound_triggers
        ]

        # Stage 2: Extract SPHook triggers and announcements
        cleaned_text, sphook_triggers, announcements = (
            self._sphook_parser.extract_triggers(cleaned_text)
        )

        # Track SPHook sounds for stop matching
        for trigger in sphook_triggers:
            if trigger.is_stop:
                # Handle stop by ID
                self._sphook_state.unregister_sound(trigger.sound_type)
            else:
                self._sphook_state.register_sound(trigger)

        # Combine all sound triggers
        sound_triggers.extend(sphook_triggers)

        # Stage 3: Check gags (per line)
        if self._gag_checker:
            lines = cleaned_text.split('\n')
            ungagged_lines = []
            for line in lines:
                if not self._gag_checker(line):
                    ungagged_lines.append(line)
            cleaned_text = '\n'.join(ungagged_lines)

            if not cleaned_text.strip() and text.strip():
                # All content was gagged
                return ProcessedText(
                    spans=[],
                    sound_triggers=sound_triggers,
                    announcements=announcements,
                    gagged=True,
                )

        # Stage 4: Parse ANSI codes
        spans = self._ansi_parser.parse(cleaned_text)

        # Stage 5: Run triggers (side effects only)
        if self._trigger_checker:
            # Get plain text for trigger matching
            plain_text = ''.join(span.text for span in spans)
            self._trigger_checker(plain_text)

        return ProcessedText(
            spans=spans,
            sound_triggers=sound_triggers,
            announcements=announcements,
        )

    def process_simple(self, text: str) -> list[TextSpan]:
        """Process text with just ANSI parsing (no MSP or triggers).

        Args:
            text: Text to parse.

        Returns:
            List of styled TextSpan objects.
        """
        return self._ansi_parser.parse(text)

    def reset(self):
        """Reset processor state."""
        self._ansi_parser.reset()
        self._msp_state = MSPState()
        self._sphook_state = SPHookState()
