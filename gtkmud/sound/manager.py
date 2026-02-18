"""Sound manager coordinating all audio playback."""

import asyncio
import logging
import random
import re
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

from gtkmud.sound.channels import SoundChannel, MusicChannel, AmbienceChannel
from gtkmud.sound.downloader import SoundDownloader
from gtkmud.parsers.msp import SoundTrigger
from gtkmud.parsers.mcmp import MediaPlayCommand, MediaStopCommand

logger = logging.getLogger(__name__)


class SoundManager:
    """Central manager for all audio playback.

    Coordinates three audio channels:
    - Sound: Short effects, can overlap (supports looping)
    - Music: Background music, single track
    - Ambience: Looping ambient sounds (for scripting)

    Handles MSP triggers, MCMP commands, and SPHook protocol.
    Supports ID-based sound control for SPHook protocol.
    """

    def __init__(self, cache_dir: Optional[Path] = None, sounds_dir: Optional[Path] = None):
        """Initialize the sound manager.

        Args:
            cache_dir: Directory for caching downloaded sounds.
            sounds_dir: Directory for local sound files.
        """
        # Initialize GStreamer
        Gst.init(None)

        # Set up directories
        if cache_dir is None:
            from gtkmud.config.paths import get_cache_dir
            cache_dir = get_cache_dir() / "sounds"
        if sounds_dir is None:
            from gtkmud.config.paths import get_sounds_dir
            sounds_dir = get_sounds_dir()

        self._cache_dir = cache_dir
        self._sounds_dir = sounds_dir
        self._sounds_dir.mkdir(parents=True, exist_ok=True)

        # Create channels
        self._sound_channel = SoundChannel()
        self._music_channel = MusicChannel()
        self._ambience_channel = AmbienceChannel()

        # Create downloader
        self._downloader = SoundDownloader(cache_dir)

        # Master volume and mute state
        self._master_volume = 1.0
        self._sound_volume = 1.0
        self._music_volume = 0.8
        self._ambience_volume = 0.6
        self._muted = False

        # Async event loop for downloads
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Track pending downloads and stopped IDs
        # If a sound is stopped while downloading, we add its ID here
        # to prevent it from playing when the download completes
        self._stopped_ids: set[str] = set()
        self._pending_downloads: dict[str, str] = {}  # sound_id -> filename
        self._max_stopped_ids = 100  # Limit to prevent memory buildup

        # Track current ambience ID for SPHook stop matching
        self._current_ambience_id: Optional[str] = None

        # Apply initial volumes
        self._update_volumes()

    def _update_volumes(self):
        """Update all channel volumes based on master and individual settings."""
        if self._muted:
            self._sound_channel.set_volume(0)
            self._music_channel.set_volume(0)
            self._ambience_channel.set_volume(0)
        else:
            self._sound_channel.set_volume(self._master_volume * self._sound_volume)
            self._music_channel.set_volume(self._master_volume * self._music_volume)
            self._ambience_channel.set_volume(self._master_volume * self._ambience_volume)

    def set_master_volume(self, volume: float):
        """Set master volume (0.0 to 1.0)."""
        self._master_volume = max(0.0, min(1.0, volume))
        self._update_volumes()

    def set_sound_volume(self, volume: float):
        """Set sound effects volume (0.0 to 1.0)."""
        self._sound_volume = max(0.0, min(1.0, volume))
        self._update_volumes()

    def set_music_volume(self, volume: float):
        """Set music volume (0.0 to 1.0)."""
        self._music_volume = max(0.0, min(1.0, volume))
        self._update_volumes()

    def set_ambience_volume(self, volume: float):
        """Set ambience volume (0.0 to 1.0)."""
        self._ambience_volume = max(0.0, min(1.0, volume))
        self._update_volumes()

    def set_muted(self, muted: bool):
        """Set mute state."""
        self._muted = muted
        self._update_volumes()

    def _find_sound_file(self, filename: str) -> Optional[Path]:
        """Find a sound file in local directories.

        Supports three levels of fallback:
        1. Exact path match
        2. Case-insensitive match (for cross-platform soundpacks)
        3. Numbered variant random selection (e.g. "theme.ogg" matches
           "theme1.ogg", "theme2.ogg", etc. and picks one at random)

        Args:
            filename: Filename or relative path.

        Returns:
            Path to file if found, None otherwise.
        """
        # 1. Exact match
        local_path = self._sounds_dir / filename
        if local_path.exists():
            return local_path

        # Try with common extensions appended
        for ext in [".wav", ".ogg", ".mp3", ".flac"]:
            test_path = self._sounds_dir / (filename + ext)
            if test_path.exists():
                return test_path

        # 2. Case-insensitive match
        result = self._find_case_insensitive(filename)
        if result:
            return result

        # 3. Numbered variant random selection
        result = self._find_numbered_variant(filename)
        if result:
            return result

        # Note: Don't scan cache directory here - cached files use hash names
        # and should be looked up via the downloader's get_cache_path method
        return None

    def _find_case_insensitive(self, filename: str) -> Optional[Path]:
        """Find a file using case-insensitive matching.

        Walks the path components and matches each directory/file
        case-insensitively.

        Args:
            filename: Relative path to find.

        Returns:
            Path if found, None otherwise.
        """
        parts = Path(filename).parts
        current = self._sounds_dir

        for part in parts:
            if not current.is_dir():
                return None
            part_lower = part.lower()
            match = None
            try:
                for entry in current.iterdir():
                    if entry.name.lower() == part_lower:
                        match = entry
                        break
            except OSError:
                return None
            if match is None:
                return None
            current = match

        return current if current.is_file() else None

    def _find_numbered_variant(self, filename: str) -> Optional[Path]:
        """Find numbered variants of a sound file and pick one randomly.

        When "theme.ogg" is requested but doesn't exist, looks for files
        like "theme1.ogg", "theme2.ogg", etc. in the same directory.
        This is a common pattern in MUD soundpacks for random variation.

        The search is case-insensitive to handle mixed-case filenames
        (e.g. "command.ogg" matching "Command1.ogg").

        Args:
            filename: Relative path like "miriani/music/theme.ogg".

        Returns:
            Randomly selected path if variants found, None otherwise.
        """
        file_path = Path(filename)
        stem = file_path.stem
        suffix = file_path.suffix or ".ogg"

        # Resolve the parent directory (case-insensitive)
        parent_parts = file_path.parent.parts
        parent_dir = self._sounds_dir
        for part in parent_parts:
            if not parent_dir.is_dir():
                return None
            part_lower = part.lower()
            match = None
            try:
                for entry in parent_dir.iterdir():
                    if entry.is_dir() and entry.name.lower() == part_lower:
                        match = entry
                        break
            except OSError:
                return None
            if match is None:
                return None
            parent_dir = match

        if not parent_dir.is_dir():
            return None

        # Look for files matching stem + digits + suffix (case-insensitive)
        stem_lower = stem.lower()
        suffix_lower = suffix.lower()
        pattern = re.compile(
            rf'^{re.escape(stem_lower)}\d+{re.escape(suffix_lower)}$',
            re.IGNORECASE,
        )

        variants = []
        try:
            for entry in parent_dir.iterdir():
                if entry.is_file() and pattern.match(entry.name):
                    variants.append(entry)
        except OSError:
            return None

        if variants:
            chosen = random.choice(variants)
            logger.debug(
                f"Random sound selection: {filename} -> {chosen.name} "
                f"(from {len(variants)} variants)"
            )
            return chosen

        return None

    def handle_msp_trigger(self, trigger: SoundTrigger):
        """Handle an MSP sound/music trigger.

        Args:
            trigger: Parsed MSP trigger.
        """
        sound_id = trigger.sound_type  # SPHook uses sound_type as ID

        if trigger.is_stop:
            # Stop command
            if sound_id:
                # SPHook: Stop by specific ID
                logger.debug(f"Stop command for sound ID: {sound_id}")
                # Add to stopped IDs in case download is pending
                # Trim if too large (FIFO-ish, though sets don't preserve order)
                if len(self._stopped_ids) >= self._max_stopped_ids:
                    # Remove about half to avoid frequent trimming
                    to_remove = list(self._stopped_ids)[:self._max_stopped_ids // 2]
                    for sid in to_remove:
                        self._stopped_ids.discard(sid)
                self._stopped_ids.add(sound_id)
                # Remove from pending downloads
                self._pending_downloads.pop(sound_id, None)
                # Try to stop sound if already playing
                stopped = self._sound_channel.stop_by_id(sound_id)
                # Also check if this is the current ambience
                if not stopped and self._current_ambience_id == sound_id:
                    logger.debug(f"Stopping ambience by ID: {sound_id}")
                    self._ambience_channel.stop()
                    self._current_ambience_id = None
            elif trigger.type == "sound":
                # Generic stop all sounds
                self._sound_channel.stop_all()
                self._stopped_ids.clear()
                self._pending_downloads.clear()
            elif trigger.type == "ambience":
                # Stop ambience
                self._ambience_channel.stop()
                self._current_ambience_id = None
            else:
                # Stop music
                self._music_channel.stop()
            return

        # Check if this sound was stopped before we could play it
        if sound_id and sound_id in self._stopped_ids:
            logger.debug(f"Sound {sound_id} was stopped before play, ignoring")
            self._stopped_ids.discard(sound_id)
            return

        # Try to find the file locally first
        local_path = self._find_sound_file(trigger.filename)

        if local_path:
            logger.info(f"Playing local sound: {local_path}")
            self._play_local(trigger, str(local_path))
        elif trigger.url:
            # Need to download - track pending
            if sound_id:
                self._pending_downloads[sound_id] = trigger.filename
            logger.info(f"Downloading sound: {trigger.url}{trigger.filename}")
            self._download_and_play(trigger)
        else:
            logger.warning(f"Sound file not found and no URL: {trigger.filename}")

    def _play_local(self, trigger: SoundTrigger, path: str):
        """Play a local sound file.

        Args:
            trigger: The MSP trigger.
            path: Local file path.
        """
        sound_id = trigger.sound_type

        # Check if this sound was stopped while we were setting up
        if sound_id and sound_id in self._stopped_ids:
            logger.debug(f"Sound {sound_id} was stopped, not playing")
            self._stopped_ids.discard(sound_id)
            self._pending_downloads.pop(sound_id, None)
            return

        if trigger.type == "sound":
            self._sound_channel.play(
                path,
                volume=trigger.volume,
                loops=trigger.loops,
                priority=trigger.priority,
                sound_id=sound_id,
            )
            # Remove from pending since it's now playing
            if sound_id:
                self._pending_downloads.pop(sound_id, None)
        elif trigger.type == "ambience":
            # Ambience: single track, replaces previous
            self._ambience_channel.play(
                path,
                volume=trigger.volume,
                fadein=0,
            )
            self._current_ambience_id = sound_id
            logger.debug(f"Playing ambience with ID: {sound_id}")
            # Remove from pending since it's now playing
            if sound_id:
                self._pending_downloads.pop(sound_id, None)
        else:  # music
            self._music_channel.play(
                path,
                volume=trigger.volume,
                loops=trigger.loops,
                continue_=trigger.continue_,
            )

    def _download_and_play(self, trigger: SoundTrigger):
        """Download a sound file and play it.

        Args:
            trigger: The MSP trigger with URL.
        """
        # Check if already cached
        cache_path = self._downloader.get_cache_path(trigger.url, trigger.filename)
        if cache_path.exists():
            self._play_local(trigger, str(cache_path))
            return

        # Download asynchronously
        def download_complete(path: Optional[Path]):
            if path:
                GLib.idle_add(lambda: self._play_local(trigger, str(path)))

        self._async_download(trigger.url, trigger.filename, download_complete)

    def _async_download(self, url: str, filename: str, callback):
        """Start async download.

        Args:
            url: Base URL.
            filename: Filename to download.
            callback: Called with path on completion.
        """
        import threading

        def do_download():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                path = loop.run_until_complete(
                    self._downloader.get_sound(url, filename)
                )
                callback(path)
            finally:
                loop.close()

        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()

    def handle_mcmp_play(self, cmd: MediaPlayCommand):
        """Handle an MCMP play command.

        Args:
            cmd: Parsed MCMP play command.
        """
        if cmd.is_stop:
            return

        # Find or download the file
        local_path = self._find_sound_file(cmd.name)

        if not local_path and cmd.url:
            cache_path = self._downloader.get_cache_path(cmd.url, cmd.name)
            if cache_path.exists():
                local_path = cache_path

        if not local_path:
            if cmd.url:
                # Download and play
                def on_download(path):
                    if path:
                        GLib.idle_add(lambda: self._play_mcmp(cmd, str(path)))

                self._async_download(cmd.url, cmd.name, on_download)
            else:
                logger.warning(f"MCMP file not found: {cmd.name}")
            return

        self._play_mcmp(cmd, str(local_path))

    def _play_mcmp(self, cmd: MediaPlayCommand, path: str):
        """Play an MCMP file.

        Args:
            cmd: The MCMP command.
            path: Local file path.
        """
        if cmd.type == "sound":
            self._sound_channel.play(
                path,
                volume=cmd.volume,
                loops=cmd.loops,
                priority=cmd.priority,
            )
        elif cmd.type == "music":
            self._music_channel.play(
                path,
                volume=cmd.volume,
                loops=cmd.loops,
                continue_=cmd.continue_,
            )
        # Note: video type not supported

    def handle_mcmp_stop(self, cmd: MediaStopCommand):
        """Handle an MCMP stop command.

        Args:
            cmd: Parsed MCMP stop command.
        """
        fadeout = cmd.fadeout

        if cmd.type == "sound" or not cmd.type:
            self._sound_channel.stop_all()

        if cmd.type == "music" or not cmd.type:
            self._music_channel.stop(fadeout=fadeout)

    def play_ambience(self, path: str, volume: int = 100, fadein: int = 0):
        """Play ambient sound (for scripting).

        Args:
            path: Path or filename of ambient sound.
            volume: Volume 0-100.
            fadein: Fade in duration in ms.
        """
        local_path = self._find_sound_file(path)
        if local_path:
            self._ambience_channel.play(str(local_path), volume, fadein)
        else:
            logger.warning(f"Ambience file not found: {path}")

    def stop_ambience(self, fadeout: int = 0):
        """Stop ambient sound.

        Args:
            fadeout: Fade out duration in ms.
        """
        self._ambience_channel.stop(fadeout=fadeout)
        self._current_ambience_id = None

    def stop_all(self):
        """Stop all audio."""
        self._sound_channel.stop_all()
        self._music_channel.stop()
        self._ambience_channel.stop()
        # Clear all tracking state
        self._stopped_ids.clear()
        self._pending_downloads.clear()
        self._current_ambience_id = None

    @property
    def current_ambience(self) -> Optional[str]:
        """Get current ambience path."""
        return self._ambience_channel.current

    @property
    def is_music_playing(self) -> bool:
        """Return True if music is playing."""
        return self._music_channel.is_playing

    @property
    def is_ambience_playing(self) -> bool:
        """Return True if ambience is playing."""
        return self._ambience_channel.is_playing
