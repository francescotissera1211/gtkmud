"""Main application window for GTK MUD client."""

import gi
import logging

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib

from gtkmud.ui.output_view import OutputView
from gtkmud.ui.input_line import InputLine
from gtkmud.net.connection import ConnectionManager
from gtkmud.parsers import TextProcessor
from gtkmud.parsers.mcmp import MCMPParser
from gtkmud.sound import SoundManager
from gtkmud.scripting import DSLParser, ScriptInterpreter

logger = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """Main window containing the MUD interface.

    Layout:
    - Header bar with connection controls
    - Main content area with output view
    - Input line at the bottom
    - Status bar showing connection state
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.set_title("GTK MUD")
        self.set_default_size(800, 600)

        # Connection manager
        self._connection = ConnectionManager()
        self._connection.on_data = self._on_server_data
        self._connection.on_connected = self._on_connected
        self._connection.on_disconnected = self._on_disconnected
        self._connection.on_gmcp = self._on_gmcp

        # Text processor for ANSI colors and MSP sounds
        self._text_processor = TextProcessor()

        # Sound manager
        self._sound_manager = SoundManager()

        # MCMP parser for GMCP media messages
        self._mcmp_parser = MCMPParser()

        # Scripting interpreter
        self._script_interpreter = ScriptInterpreter()
        self._setup_scripting()

        # Auto-connect guard
        self._auto_connect_attempted = False

        self._setup_ui()
        self._setup_actions()

    def _setup_ui(self):
        """Set up the main window UI."""
        # Main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        # Header bar
        header = Adw.HeaderBar()
        main_box.append(header)

        # Connection button in header
        self._connect_button = Gtk.Button(label="Connect")
        self._connect_button.set_action_name("app.connect")
        self._connect_button.add_css_class("suggested-action")
        self._connect_button.set_tooltip_text("Connect to a MUD server (Ctrl+O)")
        header.pack_start(self._connect_button)

        # Menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(self._create_menu())
        menu_button.set_tooltip_text("Main menu")
        menu_button.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Main menu"],
        )
        header.pack_end(menu_button)

        # Content area with output and input
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.set_vexpand(True)
        main_box.append(content_box)

        # Output view in scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        content_box.append(scrolled)

        self._output_view = OutputView()
        scrolled.set_child(self._output_view)

        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        content_box.append(separator)

        # Input line
        self._input_line = InputLine()
        self._input_line.connect("command-entered", self._on_command_entered)
        content_box.append(self._input_line)

        # Status bar
        self._status_bar = Gtk.Label(label="Disconnected")
        self._status_bar.set_halign(Gtk.Align.START)
        self._status_bar.set_margin_start(6)
        self._status_bar.set_margin_end(6)
        self._status_bar.set_margin_top(3)
        self._status_bar.set_margin_bottom(3)
        self._status_bar.add_css_class("dim-label")
        self._status_bar.set_selectable(True)  # Makes it focusable
        self._status_bar.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Connection status"],
        )
        main_box.append(self._status_bar)

        # Set up accessibility
        self._setup_accessibility()

        # Focus input on start
        self._input_line.grab_focus()

    def _setup_accessibility(self):
        """Configure accessibility properties."""
        # Set accessible labels
        self._output_view.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["MUD output window"],
        )
        self._input_line.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["Command input"],
        )

    def _create_menu(self):
        """Create the main menu."""
        menu = Gio.Menu()

        # Connection section
        connection_section = Gio.Menu()
        connection_section.append("Connect...", "app.connect")
        connection_section.append("Disconnect", "app.disconnect")
        menu.append_section(None, connection_section)

        # Settings section
        settings_section = Gio.Menu()
        settings_section.append("Preferences", "app.preferences")
        menu.append_section(None, settings_section)

        # Help section
        help_section = Gio.Menu()
        help_section.append("About GTK MUD", "app.about")
        help_section.append("Quit", "app.quit")
        menu.append_section(None, help_section)

        return menu

    def _setup_scripting(self):
        """Set up the scripting system."""
        # Connect text processor to script interpreter for gag checking
        self._text_processor.set_gag_checker(self._script_interpreter.check_gag)

        # Connect script interpreter callbacks
        self._script_interpreter.on_send = self._on_script_send
        self._script_interpreter.on_sound = self._on_script_sound
        self._script_interpreter.on_sound_stop = self._on_script_sound_stop
        self._script_interpreter.on_ambience = self._on_script_ambience

    def _on_script_send(self, command: str):
        """Handle send action from script."""
        if self._connection.connected:
            self._connection.send(command)

    def _on_script_sound(self, filename: str, options: dict):
        """Handle sound action from script."""
        from gtkmud.parsers.msp import SoundTrigger

        # Generate an ID for this sound if not provided
        # Use explicit ID if given, otherwise generate based on filename
        sound_id = options.get("id")
        if not sound_id:
            # Auto-generate ID based on filename for tracking
            if not hasattr(self, "_dsl_sound_counter"):
                self._dsl_sound_counter = 0
            self._dsl_sound_counter += 1
            sound_id = f"dsl_{filename}_{self._dsl_sound_counter}"

        trigger = SoundTrigger(
            type="sound",
            filename=filename,
            volume=options.get("volume", 100),
            loops=options.get("loops", 1),
            priority=options.get("priority", 50),
            sound_type=sound_id,  # Track by ID
        )
        self._sound_manager.handle_msp_trigger(trigger)

    def _on_script_sound_stop(self, sound_id: str | None):
        """Handle sound stop action from script."""
        from gtkmud.parsers.msp import SoundTrigger
        if sound_id is None:
            # Stop all sounds
            self._sound_manager._sound_channel.stop_all()
        else:
            # Stop specific sound by ID
            self._sound_manager._sound_channel.stop_by_id(sound_id)

    def _on_script_ambience(self, filename, options: dict):
        """Handle ambience action from script."""
        if filename is None:
            self._sound_manager.stop_ambience()
        else:
            self._sound_manager.play_ambience(
                filename,
                volume=options.get("volume", 100),
                fadein=options.get("fadein", 0),
            )

    def load_script(self, script_path: str):
        """Load a script from a file.

        Args:
            script_path: Path to the script file.
        """
        from pathlib import Path
        try:
            parser = DSLParser()
            script = parser.parse_file(Path(script_path))
            self._script_interpreter.set_script(script)
            self._output_view.append_text(
                f"Loaded script: {script_path}\n", tags=["system"]
            )
            logger.info(f"Loaded script: {script_path}")
        except Exception as e:
            self._output_view.append_text(
                f"Error loading script: {e}\n", tags=["system"]
            )
            logger.error(f"Error loading script: {e}")

    def _setup_actions(self):
        """Set up window-level actions."""
        pass

    def maybe_auto_connect(self):
        """Auto-connect to a configured profile if available."""
        if self._auto_connect_attempted:
            return False
        self._auto_connect_attempted = True

        if self._connection.connected:
            return False

        from gtkmud.config import get_profile_manager

        profiles = get_profile_manager().list_profiles()
        auto_profiles = [profile for profile in profiles if profile.auto_connect]

        if not auto_profiles:
            return False

        if len(auto_profiles) > 1:
            self._output_view.append_text(
                "Multiple auto-connect profiles configured. Open Connect to choose one.\n",
                tags=["system"],
            )
            logger.info("Auto-connect skipped: multiple profiles configured")
            return False

        profile = auto_profiles[0]
        profile_label = profile.name or f"{profile.host}:{profile.port}"
        if not profile.host:
            self._output_view.append_text(
                f"Auto-connect skipped: profile '{profile_label}' has no host.\n",
                tags=["system"],
            )
            logger.warning("Auto-connect skipped: profile missing host")
            return False

        script_path = profile.script_file or None
        self._connect_to_server(
            profile.host,
            profile.port,
            script_path,
            use_ssl=profile.use_ssl,
        )
        return False

    def _on_command_entered(self, input_line, command):
        """Handle command entered by user."""
        from gtkmud.config import get_settings

        # Expand aliases
        expanded = self._script_interpreter.expand_alias(command)
        settings = get_settings()

        if self._connection.connected:
            # Echo command if enabled
            if settings.display.echo_commands:
                self._output_view.append_text(f"> {command}\n", echo=True)
            self._connection.send(expanded)
        else:
            # Echo locally when not connected (always show for feedback)
            if settings.display.echo_commands:
                self._output_view.append_text(f"> {command}\n")
            self._output_view.append_text("Not connected to a server.\n", tags=["system"])

    def _on_server_data(self, data: bytes):
        """Handle data received from the server."""
        try:
            # Decode as UTF-8 with fallback
            text = data.decode("utf-8", errors="replace")

            # Process through text pipeline (ANSI colors, MSP sounds, gags)
            result = self._text_processor.process(text)

            # Display styled text (if not gagged)
            if result.spans and not result.gagged:
                self._output_view.append_spans(result.spans)

            # Handle MSP and SPHook sound triggers
            for trigger in result.sound_triggers:
                self._handle_sound_trigger(trigger)

            # Handle SPHook buffer announcements (screen reader)
            for announcement in result.announcements:
                self._output_view.announce_text(announcement.text)

            # Process script triggers for each line
            if not result.gagged:
                plain_text = "".join(span.text for span in result.spans)
                for line in plain_text.split("\n"):
                    if line.strip():
                        trigger_result = self._script_interpreter.process_line(line)

                        # Handle script sounds
                        for filename, options in trigger_result.sounds_to_play:
                            self._on_script_sound(filename, options)

                        # Handle script sound stops
                        for sound_id in trigger_result.sounds_to_stop:
                            self._on_script_sound_stop(sound_id)

                        # Handle script ambience
                        if trigger_result.ambience:
                            filename, options = trigger_result.ambience
                            self._on_script_ambience(filename, options)

        except Exception as e:
            logger.error(f"Error processing server data: {e}")

    def _handle_sound_trigger(self, trigger):
        """Handle an MSP sound trigger."""
        logger.debug(f"Sound trigger: {trigger.type} {trigger.filename}")
        self._sound_manager.handle_msp_trigger(trigger)

    def _on_connected(self):
        """Handle successful connection."""
        host = self._connection.host
        port = self._connection.port
        self._status_bar.set_label(f"Connected to {host}:{port}")
        self._connect_button.set_label("Disconnect")
        self._connect_button.set_action_name("app.disconnect")
        self._connect_button.remove_css_class("suggested-action")
        self._connect_button.add_css_class("destructive-action")
        self._output_view.append_text(f"Connected to {host}:{port}\n", tags=["system"])

    def _on_disconnected(self, reason):
        """Handle disconnection."""
        self._status_bar.set_label("Disconnected")
        self._connect_button.set_label("Connect")
        self._connect_button.set_action_name("app.connect")
        self._connect_button.remove_css_class("destructive-action")
        self._connect_button.add_css_class("suggested-action")

        if reason:
            self._output_view.append_text(f"Disconnected: {reason}\n", tags=["system"])
        else:
            self._output_view.append_text("Disconnected from server.\n", tags=["system"])

    def _on_gmcp(self, package: str, data: dict):
        """Handle GMCP message from server."""
        logger.debug(f"GMCP received: {package} = {data}")

        # Handle MCMP (Client.Media.*) messages
        if package == "Client.Media.Play":
            cmd = self._mcmp_parser.parse_play(data)
            if cmd:
                self._sound_manager.handle_mcmp_play(cmd)
        elif package == "Client.Media.Stop":
            cmd = self._mcmp_parser.parse_stop(data)
            self._sound_manager.handle_mcmp_stop(cmd)
        elif package == "Client.Media.Load":
            # Preload - we can handle this by just triggering a download
            cmd = self._mcmp_parser.parse_load(data)
            if cmd and cmd.url:
                # Just cache the file
                logger.debug(f"Preloading media: {cmd.name}")

    def show_connect_dialog(self):
        """Show the connection dialog."""
        from gtkmud.config import get_profile_manager

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Connect to MUD",
            body="Enter server details:",
        )

        # Use a ListBox for proper keyboard navigation of rows
        listbox = Gtk.ListBox()
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        listbox.set_margin_top(12)
        listbox.set_margin_bottom(12)
        listbox.set_margin_start(12)
        listbox.set_margin_end(12)

        # Profile selector (if profiles exist)
        profile_manager = get_profile_manager()
        profiles = profile_manager.list_profiles()

        profile_combo = None
        if profiles:
            profile_list = Gtk.StringList()
            profile_list.append("(New Connection)")
            for profile in profiles:
                profile_list.append(profile.name)

            profile_combo = Adw.ComboRow(title="Profile")
            profile_combo.set_model(profile_list)
            listbox.append(profile_combo)

        # Host entry
        host_row = Adw.EntryRow(title="Host")
        host_row.set_text("localhost")
        listbox.append(host_row)

        # Port entry
        port_row = Adw.EntryRow(title="Port")
        port_row.set_text("4000")
        listbox.append(port_row)

        # SSL/TLS option
        ssl_row = Adw.SwitchRow(
            title="Use SSL/TLS",
            subtitle="Encrypt the connection to the server",
        )
        listbox.append(ssl_row)

        # Script file row with browse button
        script_row = Adw.EntryRow(title="Script File")

        browse_button = Gtk.Button(icon_name="document-open-symbolic")
        browse_button.set_valign(Gtk.Align.CENTER)
        browse_button.set_tooltip_text("Browse for script file")
        browse_button.add_css_class("flat")
        script_row.add_suffix(browse_button)

        listbox.append(script_row)

        # Auto-connect option
        auto_connect_row = Adw.SwitchRow(
            title="Auto-connect",
            subtitle="Connect automatically on startup using this profile",
        )
        listbox.append(auto_connect_row)

        # File chooser callback
        def on_browse_clicked(button):
            file_dialog = Gtk.FileDialog()
            file_dialog.set_title("Select Script File")

            # Set up file filter for .mud files
            filter_mud = Gtk.FileFilter()
            filter_mud.set_name("MUD Scripts (*.mud)")
            filter_mud.add_pattern("*.mud")

            filter_all = Gtk.FileFilter()
            filter_all.set_name("All Files")
            filter_all.add_pattern("*")

            filters = Gio.ListStore.new(Gtk.FileFilter)
            filters.append(filter_mud)
            filters.append(filter_all)
            file_dialog.set_filters(filters)
            file_dialog.set_default_filter(filter_mud)

            def on_file_selected(dialog, result):
                try:
                    file = dialog.open_finish(result)
                    if file:
                        script_row.set_text(file.get_path())
                except GLib.Error:
                    pass  # User cancelled

            file_dialog.open(self, None, on_file_selected)

        browse_button.connect("clicked", on_browse_clicked)

        # Profile selection callback
        if profile_combo:
            def on_profile_changed(combo, _pspec):
                selected = combo.get_selected()
                if selected > 0:  # Not "(New Connection)"
                    profile = profiles[selected - 1]
                    host_row.set_text(profile.host)
                    port_row.set_text(str(profile.port))
                    ssl_row.set_active(profile.use_ssl)
                    script_row.set_text(profile.script_file or "")
                    auto_connect_row.set_active(profile.auto_connect)
                else:
                    ssl_row.set_active(False)
                    auto_connect_row.set_active(False)

            profile_combo.connect("notify::selected", on_profile_changed)

        # Save profile option
        save_profile_row = Adw.SwitchRow(title="Save as Profile")
        listbox.append(save_profile_row)

        profile_name_row = Adw.EntryRow(title="Profile Name")
        profile_name_row.set_visible(False)
        listbox.append(profile_name_row)

        def on_save_toggle(row, _pspec):
            profile_name_row.set_visible(row.get_active())

        save_profile_row.connect("notify::active", on_save_toggle)

        dialog.set_extra_child(listbox)

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("connect", "Connect")
        dialog.set_response_appearance("connect", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("connect")

        def on_response(dialog, response):
            if response == "connect":
                host = host_row.get_text().strip()
                try:
                    port = int(port_row.get_text())
                except ValueError:
                    port = 4000
                script_path = script_row.get_text().strip()
                auto_connect = auto_connect_row.get_active()
                use_ssl = ssl_row.get_active()

                selected_profile = None
                if profile_combo:
                    selected = profile_combo.get_selected()
                    if selected > 0:
                        selected_profile = profiles[selected - 1]

                # Save profile if requested
                if save_profile_row.get_active():
                    profile_name = profile_name_row.get_text().strip()
                    if selected_profile:
                        if profile_name:
                            selected_profile.name = profile_name
                        selected_profile.host = host
                        selected_profile.port = port
                        selected_profile.use_ssl = use_ssl
                        selected_profile.script_file = script_path
                        selected_profile.auto_connect = auto_connect
                        profile_manager.save_profile(selected_profile)
                        self._output_view.append_text(
                            f"Updated profile: {selected_profile.name}\n", tags=["system"]
                        )
                    elif profile_name:
                        from gtkmud.config import MudProfile
                        profile = MudProfile(
                            name=profile_name,
                            host=host,
                            port=port,
                            use_ssl=use_ssl,
                            script_file=script_path,
                            auto_connect=auto_connect,
                        )
                        profile_manager.save_profile(profile)
                        self._output_view.append_text(
                            f"Saved profile: {profile_name}\n", tags=["system"]
                        )
                elif selected_profile and selected_profile.auto_connect != auto_connect:
                    selected_profile.auto_connect = auto_connect
                    profile_manager.save_profile(selected_profile)

                self._connect_to_server(
                    host,
                    port,
                    script_path if script_path else None,
                    use_ssl=use_ssl,
                )

        dialog.connect("response", on_response)
        dialog.present()

    def _connect_to_server(self, host, port, script_path=None, use_ssl: bool = False):
        """Initiate connection to a MUD server.

        Args:
            host: Server hostname or IP.
            port: Server port number.
            script_path: Optional path to script file to load.
            use_ssl: If True, connect using SSL/TLS.
        """
        # Load script if specified
        if script_path:
            self.load_script(script_path)

        self._output_view.append_text(f"Connecting to {host}:{port}...\n", tags=["system"])
        self._status_bar.set_label(f"Connecting to {host}:{port}...")
        self._connection.connect(host, port, use_ssl=use_ssl)

    def disconnect_from_server(self):
        """Disconnect from the current MUD server."""
        if self._connection.connected:
            self._connection.disconnect()

    def show_preferences_dialog(self):
        """Show the preferences dialog."""
        from gtkmud.config import get_settings, save_settings

        settings = get_settings()

        # Create preferences window
        prefs_window = Adw.PreferencesWindow(
            transient_for=self,
            title="Preferences",
        )

        # === Display Page ===
        display_page = Adw.PreferencesPage(
            title="Display",
            icon_name="video-display-symbolic",
        )
        prefs_window.add(display_page)

        # Display group
        display_group = Adw.PreferencesGroup(title="Display Options")
        display_page.add(display_group)

        # Echo commands setting
        echo_row = Adw.SwitchRow(
            title="Echo Commands",
            subtitle="Show your typed commands in the output window",
        )
        echo_row.set_active(settings.display.echo_commands)
        display_group.add(echo_row)

        def on_echo_changed(row, _pspec):
            settings.display.echo_commands = row.get_active()
            save_settings()

        echo_row.connect("notify::active", on_echo_changed)

        # Max lines setting
        max_lines_row = Adw.SpinRow.new_with_range(1000, 100000, 1000)
        max_lines_row.set_title("Maximum Lines")
        max_lines_row.set_subtitle("Maximum lines to keep in output buffer")
        max_lines_row.set_value(settings.display.max_lines)
        display_group.add(max_lines_row)

        def on_max_lines_changed(row, _pspec):
            settings.display.max_lines = int(row.get_value())
            save_settings()

        max_lines_row.connect("notify::value", on_max_lines_changed)

        # === Sound Page ===
        sound_page = Adw.PreferencesPage(
            title="Sound",
            icon_name="audio-speakers-symbolic",
        )
        prefs_window.add(sound_page)

        # Sound group
        sound_group = Adw.PreferencesGroup(title="Sound Options")
        sound_page.add(sound_group)

        # Sound enabled
        sound_enabled_row = Adw.SwitchRow(
            title="Enable Sound",
            subtitle="Play sounds from the MUD",
        )
        sound_enabled_row.set_active(settings.sound.enabled)
        sound_group.add(sound_enabled_row)

        def on_sound_enabled_changed(row, _pspec):
            settings.sound.enabled = row.get_active()
            save_settings()

        sound_enabled_row.connect("notify::active", on_sound_enabled_changed)

        # Master volume
        master_vol_row = Adw.SpinRow.new_with_range(0, 100, 5)
        master_vol_row.set_title("Master Volume")
        master_vol_row.set_value(settings.sound.master_volume)
        sound_group.add(master_vol_row)

        def on_master_vol_changed(row, _pspec):
            settings.sound.master_volume = int(row.get_value())
            save_settings()

        master_vol_row.connect("notify::value", on_master_vol_changed)

        # Sound effects volume
        sound_vol_row = Adw.SpinRow.new_with_range(0, 100, 5)
        sound_vol_row.set_title("Sound Effects Volume")
        sound_vol_row.set_value(settings.sound.sound_volume)
        sound_group.add(sound_vol_row)

        def on_sound_vol_changed(row, _pspec):
            settings.sound.sound_volume = int(row.get_value())
            save_settings()

        sound_vol_row.connect("notify::value", on_sound_vol_changed)

        # Music volume
        music_vol_row = Adw.SpinRow.new_with_range(0, 100, 5)
        music_vol_row.set_title("Music Volume")
        music_vol_row.set_value(settings.sound.music_volume)
        sound_group.add(music_vol_row)

        def on_music_vol_changed(row, _pspec):
            settings.sound.music_volume = int(row.get_value())
            save_settings()

        music_vol_row.connect("notify::value", on_music_vol_changed)

        # Ambience volume
        ambience_vol_row = Adw.SpinRow.new_with_range(0, 100, 5)
        ambience_vol_row.set_title("Ambience Volume")
        ambience_vol_row.set_value(settings.sound.ambience_volume)
        sound_group.add(ambience_vol_row)

        def on_ambience_vol_changed(row, _pspec):
            settings.sound.ambience_volume = int(row.get_value())
            save_settings()

        ambience_vol_row.connect("notify::value", on_ambience_vol_changed)

        # === Accessibility Page ===
        a11y_page = Adw.PreferencesPage(
            title="Accessibility",
            icon_name="preferences-desktop-accessibility-symbolic",
        )
        prefs_window.add(a11y_page)

        # Accessibility group
        a11y_group = Adw.PreferencesGroup(title="Screen Reader")
        a11y_page.add(a11y_group)

        # Announce incoming text
        announce_row = Adw.SwitchRow(
            title="Announce Incoming Text",
            subtitle="Read new text aloud via screen reader",
        )
        announce_row.set_active(settings.accessibility.announce_incoming)
        a11y_group.add(announce_row)

        def on_announce_changed(row, _pspec):
            settings.accessibility.announce_incoming = row.get_active()
            save_settings()

        announce_row.connect("notify::active", on_announce_changed)

        # Announcement interval
        interval_row = Adw.SpinRow.new_with_range(50, 1000, 50)
        interval_row.set_title("Announcement Delay (ms)")
        interval_row.set_subtitle("Time to batch text before announcing")
        interval_row.set_value(settings.accessibility.announce_interval_ms)
        a11y_group.add(interval_row)

        def on_interval_changed(row, _pspec):
            settings.accessibility.announce_interval_ms = int(row.get_value())
            save_settings()

        interval_row.connect("notify::value", on_interval_changed)

        prefs_window.present()

    def append_server_text(self, text):
        """Append text received from the server to the output."""
        self._output_view.append_text(text)
