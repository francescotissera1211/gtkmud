"""Command input line with history support."""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, GObject, Gdk


class InputLine(Gtk.Entry):
    """Text entry for MUD commands with history support.

    Features:
    - Command history navigation with Up/Down arrows
    - Enter to submit command
    - History persists during session
    - Accessible labeling
    """

    __gsignals__ = {
        "command-entered": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    # Maximum history size
    MAX_HISTORY = 500

    def __init__(self):
        super().__init__()

        # Command history
        self._history = []
        self._history_index = -1
        self._current_input = ""

        # Configure entry
        self.set_placeholder_text("Enter command...")
        self.set_hexpand(True)

        # Margins
        self.set_margin_start(6)
        self.set_margin_end(6)
        self.set_margin_top(6)
        self.set_margin_bottom(6)

        # Connect signals
        self.connect("activate", self._on_activate)

        # Set up key controller for history navigation
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)

        # Set up accessibility
        self._setup_accessibility()

    def _setup_accessibility(self):
        """Configure accessibility properties."""
        self.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Command input"],
        )

    def _on_activate(self, entry):
        """Handle Enter key press."""
        command = self.get_text().strip()
        if command:
            # Add to history
            self._add_to_history(command)

            # Emit signal
            self.emit("command-entered", command)

        # Clear input
        self.set_text("")
        self._history_index = -1

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events for history navigation."""
        if keyval == Gdk.KEY_Up:
            self._navigate_history(1)
            return True
        elif keyval == Gdk.KEY_Down:
            self._navigate_history(-1)
            return True
        elif keyval == Gdk.KEY_Escape:
            # Clear input and reset history position
            self.set_text("")
            self._history_index = -1
            return True
        return False

    def _navigate_history(self, direction):
        """Navigate through command history.

        Args:
            direction: 1 for older, -1 for newer
        """
        if not self._history:
            return

        # Save current input if we're starting navigation
        if self._history_index == -1 and direction == 1:
            self._current_input = self.get_text()

        new_index = self._history_index + direction

        if new_index < -1:
            # Already at oldest
            return
        elif new_index >= len(self._history):
            # Beyond newest, restore current input
            self._history_index = -1
            self.set_text(self._current_input)
            self.set_position(-1)  # Move cursor to end
            return

        self._history_index = new_index

        if new_index == -1:
            # Back to current input
            self.set_text(self._current_input)
        else:
            # Show history entry (newer entries are at higher indices)
            history_entry = self._history[-(new_index + 1)]
            self.set_text(history_entry)

        self.set_position(-1)  # Move cursor to end

    def _add_to_history(self, command):
        """Add a command to history.

        Args:
            command: The command string to add.
        """
        # Don't add duplicates of the last command
        if self._history and self._history[-1] == command:
            return

        self._history.append(command)

        # Trim history if too long
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY :]

    def get_history(self):
        """Get the command history list."""
        return list(self._history)

    def set_history(self, history):
        """Set the command history list.

        Args:
            history: List of command strings.
        """
        self._history = list(history)[-self.MAX_HISTORY :]
        self._history_index = -1

    def clear_history(self):
        """Clear the command history."""
        self._history.clear()
        self._history_index = -1
