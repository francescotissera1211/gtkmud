"""Main GTK Application class for GTK MUD client."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gio, GLib, Adw

from gtkmud import __app_id__, __app_name__, __version__
from gtkmud.ui.main_window import MainWindow


class GtkMudApp(Adw.Application):
    """Main application class for GTK MUD client.

    Handles application lifecycle, global actions, and window management.
    Uses libadwaita for modern GNOME styling while maintaining accessibility.
    """

    def __init__(self):
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None

        GLib.set_application_name(__app_name__)

    def do_startup(self):
        """Called when the application starts up."""
        Adw.Application.do_startup(self)
        self._setup_actions()
        self._setup_accels()

    def do_activate(self):
        """Called when the application is activated."""
        if not self.window:
            self.window = MainWindow(application=self)
        self.window.present()
        GLib.idle_add(self.window.maybe_auto_connect)

    def _setup_actions(self):
        """Set up application-level actions."""
        # Quit action
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self._on_quit)
        self.add_action(action)

        # About action
        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self._on_about)
        self.add_action(action)

        # Connect action
        action = Gio.SimpleAction.new("connect", None)
        action.connect("activate", self._on_connect)
        self.add_action(action)

        # Disconnect action
        action = Gio.SimpleAction.new("disconnect", None)
        action.connect("activate", self._on_disconnect)
        self.add_action(action)

        # Preferences action
        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self._on_preferences)
        self.add_action(action)

    def _setup_accels(self):
        """Set up keyboard accelerators."""
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.connect", ["<Control>o"])
        self.set_accels_for_action("app.disconnect", ["<Control>d"])
        self.set_accels_for_action("app.preferences", ["<Control>comma"])

    def _on_quit(self, action, param):
        """Handle quit action."""
        self.quit()

    def _on_about(self, action, param):
        """Show about dialog."""
        about = Adw.AboutDialog(
            application_name=__app_name__,
            application_icon=__app_id__,
            version=__version__,
            developer_name="Harley",
            copyright="Copyright 2025 Harley",
            license_type=Gtk.License.GPL_3_0,
            comments="An accessible GTK4 MUD client with scripting support",
            website="https://github.com/harley/gtkmud",
        )
        about.present(self.window)

    def _on_connect(self, action, param):
        """Handle connect action."""
        if self.window:
            self.window.show_connect_dialog()

    def _on_disconnect(self, action, param):
        """Handle disconnect action."""
        if self.window:
            self.window.disconnect_from_server()

    def _on_preferences(self, action, param):
        """Handle preferences action."""
        if self.window:
            self.window.show_preferences_dialog()


def run():
    """Run the GTK MUD application."""
    app = GtkMudApp()
    return app.run(None)
