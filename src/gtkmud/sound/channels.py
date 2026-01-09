"""Audio channels for different types of sound playback."""

import logging
from typing import Optional
from pathlib import Path

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GLib

logger = logging.getLogger(__name__)


class SoundChannel:
    """Channel for sound effects - can play multiple overlapping sounds.

    Uses multiple playbin elements to allow concurrent playback.
    Supports tracking sounds by ID for individual stop control.
    """

    MAX_CONCURRENT = 8  # Maximum concurrent sounds

    def __init__(self):
        self._players: list[Gst.Element] = []
        self._players_by_id: dict[str, Gst.Element] = {}  # sound_id -> player
        self._buses: dict[Gst.Element, Gst.Bus] = {}  # player -> bus (for cleanup)
        self._volume = 1.0

    def _dispose_player(self, player: Gst.Element, player_id: Optional[str] = None):
        """Properly dispose of a player and its resources."""
        # Remove signal watch from bus to prevent leaks
        if player in self._buses:
            bus = self._buses[player]
            bus.remove_signal_watch()
            del self._buses[player]

        player.set_state(Gst.State.NULL)

        if player in self._players:
            self._players.remove(player)
        if player_id and player_id in self._players_by_id:
            del self._players_by_id[player_id]

    def play(self, path: str, volume: int = 100, loops: int = 1, priority: int = 50,
             sound_id: Optional[str] = None):
        """Play a sound effect.

        Args:
            path: Path to sound file.
            volume: Volume 0-100.
            loops: Number of times to play (1 = once, -1 = infinite).
            priority: Priority 0-100 (higher can interrupt lower).
            sound_id: Optional ID for stopping this specific sound later.
        """
        # Clean up finished players
        self._cleanup()

        # Check if we need to stop a lower priority sound
        if len(self._players) >= self.MAX_CONCURRENT:
            # TODO: Implement priority-based eviction
            logger.debug("Max concurrent sounds reached, skipping")
            return

        player = Gst.ElementFactory.make("playbin", None)
        if not player:
            logger.error("Failed to create playbin element")
            return

        # Set up the player
        uri = Path(path).as_uri() if not path.startswith(("http://", "https://", "file://")) else path
        player.set_property("uri", uri)
        player.set_property("volume", (volume / 100.0) * self._volume)

        # Handle looping and end-of-stream
        bus = player.get_bus()
        bus.add_signal_watch()
        self._buses[player] = bus  # Track for cleanup

        loop_count = [loops]  # Mutable container for closure
        player_id = sound_id  # Capture for closure

        def on_message(bus, message):
            if message.type == Gst.MessageType.EOS:
                if loop_count[0] == -1 or loop_count[0] > 1:
                    # Loop
                    if loop_count[0] > 1:
                        loop_count[0] -= 1
                    player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
                else:
                    # Done - properly dispose
                    self._dispose_player(player, player_id)
            elif message.type == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                logger.error(f"Sound playback error: {err.message}")
                self._dispose_player(player, player_id)

        bus.connect("message", on_message)

        self._players.append(player)
        if sound_id:
            self._players_by_id[sound_id] = player
        player.set_state(Gst.State.PLAYING)
        logger.debug(f"Playing sound: {path} (id={sound_id})")

    def stop_by_id(self, sound_id: str) -> bool:
        """Stop a specific sound by its ID.

        Args:
            sound_id: The ID of the sound to stop.

        Returns:
            True if a sound was stopped, False if ID not found.
        """
        if sound_id in self._players_by_id:
            player = self._players_by_id[sound_id]
            self._dispose_player(player, sound_id)
            logger.debug(f"Stopped sound by ID: {sound_id}")
            return True
        return False

    def stop_all(self):
        """Stop all currently playing sounds."""
        # Copy list since _dispose_player modifies it
        for player in list(self._players):
            # Find ID if any
            player_id = None
            for sid, p in list(self._players_by_id.items()):
                if p is player:
                    player_id = sid
                    break
            self._dispose_player(player, player_id)

    def set_volume(self, volume: float):
        """Set master volume for this channel (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))
        for player in self._players:
            current = player.get_property("volume") / self._volume if self._volume > 0 else 0
            player.set_property("volume", current * self._volume)

    def _cleanup(self):
        """Remove finished players and release their resources."""
        # Find players in NULL state
        to_remove = []
        for player in self._players:
            if player.get_state(0)[1] == Gst.State.NULL:
                to_remove.append(player)

        # Dispose each finished player
        for player in to_remove:
            # Find ID if any
            player_id = None
            for sid, p in list(self._players_by_id.items()):
                if p is player:
                    player_id = sid
                    break
            self._dispose_player(player, player_id)


class MusicChannel:
    """Channel for background music - single track with crossfade support."""

    def __init__(self):
        self._player: Optional[Gst.Element] = None
        self._bus: Optional[Gst.Bus] = None
        self._volume = 1.0
        self._current_path: Optional[str] = None
        self._fade_timer: Optional[int] = None

    def _dispose_player(self):
        """Properly dispose of the current player."""
        if self._bus:
            self._bus.remove_signal_watch()
            self._bus = None
        if self._player:
            self._player.set_state(Gst.State.NULL)
            self._player = None
        self._current_path = None

    def play(self, path: str, volume: int = 100, loops: int = 1, continue_: bool = True):
        """Play background music.

        Args:
            path: Path to music file.
            volume: Volume 0-100.
            loops: Number of times to play (-1 = infinite).
            continue_: If True and same track, continue; if False, restart.
        """
        # Check if already playing this track
        if continue_ and self._current_path == path and self._player:
            state = self._player.get_state(0)[1]
            if state == Gst.State.PLAYING:
                return  # Already playing

        # Stop current music
        self._dispose_player()

        self._player = Gst.ElementFactory.make("playbin", None)
        if not self._player:
            logger.error("Failed to create playbin for music")
            return

        uri = Path(path).as_uri() if not path.startswith(("http://", "https://", "file://")) else path
        self._player.set_property("uri", uri)
        self._player.set_property("volume", (volume / 100.0) * self._volume)
        self._current_path = path

        # Handle looping
        self._bus = self._player.get_bus()
        self._bus.add_signal_watch()

        loop_count = [loops]

        def on_message(bus, message):
            if message.type == Gst.MessageType.EOS:
                if loop_count[0] == -1 or loop_count[0] > 1:
                    if loop_count[0] > 1:
                        loop_count[0] -= 1
                    if self._player:
                        self._player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
                else:
                    self._dispose_player()
            elif message.type == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                logger.error(f"Music playback error: {err.message}")
                self._dispose_player()

        self._bus.connect("message", on_message)

        self._player.set_state(Gst.State.PLAYING)
        logger.debug(f"Playing music: {path}")

    def stop(self, fadeout: int = 0):
        """Stop the current music.

        Args:
            fadeout: Fade out duration in milliseconds.
        """
        if not self._player:
            return

        if fadeout > 0:
            self._fade_out(fadeout)
        else:
            self._dispose_player()

    def _fade_out(self, duration_ms: int):
        """Gradually fade out the music."""
        if not self._player:
            return

        steps = 20
        step_time = duration_ms // steps
        current_volume = self._player.get_property("volume")
        step_volume = current_volume / steps

        def fade_step():
            if not self._player:
                return False
            vol = self._player.get_property("volume")
            new_vol = vol - step_volume
            if new_vol <= 0:
                self._dispose_player()
                return False
            self._player.set_property("volume", new_vol)
            return True

        GLib.timeout_add(step_time, fade_step)

    def set_volume(self, volume: float):
        """Set master volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))
        if self._player:
            self._player.set_property("volume", self._volume)

    @property
    def is_playing(self) -> bool:
        """Return True if music is currently playing."""
        if not self._player:
            return False
        return self._player.get_state(0)[1] == Gst.State.PLAYING


class AmbienceChannel:
    """Channel for ambient sounds - seamless looping background."""

    def __init__(self):
        self._player: Optional[Gst.Element] = None
        self._bus: Optional[Gst.Bus] = None
        self._volume = 1.0
        self._current_path: Optional[str] = None
        self._fade_timer: Optional[int] = None

    def _dispose_player(self):
        """Properly dispose of the current player."""
        if self._bus:
            self._bus.remove_signal_watch()
            self._bus = None
        if self._player:
            self._player.set_state(Gst.State.NULL)
            self._player = None
        self._current_path = None

    def play(self, path: str, volume: int = 100, fadein: int = 0):
        """Play ambient sound (always loops).

        Args:
            path: Path to ambient sound file.
            volume: Volume 0-100.
            fadein: Fade in duration in milliseconds.
        """
        # Check if already playing this ambience
        if self._current_path == path and self._player:
            state = self._player.get_state(0)[1]
            if state == Gst.State.PLAYING:
                return

        # Stop current ambience
        self._dispose_player()

        self._player = Gst.ElementFactory.make("playbin", None)
        if not self._player:
            logger.error("Failed to create playbin for ambience")
            return

        uri = Path(path).as_uri() if not path.startswith(("http://", "https://", "file://")) else path
        self._player.set_property("uri", uri)

        target_volume = (volume / 100.0) * self._volume
        if fadein > 0:
            self._player.set_property("volume", 0.0)
        else:
            self._player.set_property("volume", target_volume)

        self._current_path = path

        # Set up infinite looping
        self._bus = self._player.get_bus()
        self._bus.add_signal_watch()

        def on_message(bus, message):
            if message.type == Gst.MessageType.EOS:
                # Always loop ambience
                if self._player:
                    self._player.seek_simple(Gst.Format.TIME, Gst.SeekFlags.FLUSH, 0)
            elif message.type == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                logger.error(f"Ambience playback error: {err.message}")
                self._dispose_player()

        self._bus.connect("message", on_message)

        self._player.set_state(Gst.State.PLAYING)
        logger.debug(f"Playing ambience: {path}")

        # Handle fade in
        if fadein > 0:
            self._fade_in(target_volume, fadein)

    def _fade_in(self, target_volume: float, duration_ms: int):
        """Gradually fade in the ambience."""
        if not self._player:
            return

        steps = 20
        step_time = duration_ms // steps
        step_volume = target_volume / steps

        def fade_step():
            if not self._player:
                return False
            vol = self._player.get_property("volume")
            new_vol = vol + step_volume
            if new_vol >= target_volume:
                self._player.set_property("volume", target_volume)
                return False
            self._player.set_property("volume", new_vol)
            return True

        GLib.timeout_add(step_time, fade_step)

    def stop(self, fadeout: int = 0):
        """Stop the ambient sound.

        Args:
            fadeout: Fade out duration in milliseconds.
        """
        if not self._player:
            return

        if fadeout > 0:
            self._fade_out(fadeout)
        else:
            self._dispose_player()

    def _fade_out(self, duration_ms: int):
        """Gradually fade out the ambience."""
        if not self._player:
            return

        steps = 20
        step_time = duration_ms // steps
        current_volume = self._player.get_property("volume")
        step_volume = current_volume / steps

        def fade_step():
            if not self._player:
                return False
            vol = self._player.get_property("volume")
            new_vol = vol - step_volume
            if new_vol <= 0:
                self._dispose_player()
                return False
            self._player.set_property("volume", new_vol)
            return True

        GLib.timeout_add(step_time, fade_step)

    def set_volume(self, volume: float):
        """Set master volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))
        if self._player:
            self._player.set_property("volume", self._volume)

    @property
    def is_playing(self) -> bool:
        """Return True if ambience is currently playing."""
        if not self._player:
            return False
        return self._player.get_state(0)[1] == Gst.State.PLAYING

    @property
    def current(self) -> Optional[str]:
        """Return the current ambience path."""
        return self._current_path
