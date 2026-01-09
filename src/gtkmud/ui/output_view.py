"""Accessible text output view for displaying MUD content."""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango, GLib


class OutputView(Gtk.TextView):
    """Text view for displaying MUD output with accessibility support.

    Features:
    - Read-only display of MUD output
    - ANSI color code rendering via text tags
    - Screen reader announcements for new content
    - Auto-scrolling to bottom on new content
    - Maximum buffer size to prevent memory issues
    """

    # Maximum number of lines to keep in buffer
    MAX_LINES = 10000

    def __init__(self):
        super().__init__()

        self.set_editable(False)
        self.set_cursor_visible(True)  # Enable cursor for arrow key navigation
        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_monospace(True)

        # Margins for readability
        self.set_left_margin(6)
        self.set_right_margin(6)
        self.set_top_margin(6)
        self.set_bottom_margin(6)

        # Get buffer and set up tags
        self._buffer = self.get_buffer()
        self._setup_tags()

        # Track if we should auto-scroll
        self._auto_scroll = True

        # Announcement buffer for screen readers
        self._announcement_buffer = []
        self._announcement_timer = None

        # Set up accessibility
        self._setup_accessibility()

    def _setup_accessibility(self):
        """Configure accessibility properties."""
        # Set the accessible role to a document for better navigation
        # GtkTextView already implements GtkAccessibleText
        self.update_property(
            [Gtk.AccessibleProperty.LABEL],
            ["MUD output"],
        )

    def _setup_tags(self):
        """Set up text tags for ANSI colors."""
        # Create tag table for colors
        tag_table = self._buffer.get_tag_table()

        # Standard ANSI colors (foreground)
        ansi_colors = {
            "black": "#000000",
            "red": "#CC0000",
            "green": "#4E9A06",
            "yellow": "#C4A000",
            "blue": "#3465A4",
            "magenta": "#75507B",
            "cyan": "#06989A",
            "white": "#D3D7CF",
            # Bright variants
            "bright_black": "#555753",
            "bright_red": "#EF2929",
            "bright_green": "#8AE234",
            "bright_yellow": "#FCE94F",
            "bright_blue": "#729FCF",
            "bright_magenta": "#AD7FA8",
            "bright_cyan": "#34E2E2",
            "bright_white": "#EEEEEC",
        }

        # Create foreground color tags
        for name, color in ansi_colors.items():
            tag = Gtk.TextTag(name=f"fg_{name}")
            tag.set_property("foreground", color)
            tag_table.add(tag)

        # Create background color tags
        for name, color in ansi_colors.items():
            tag = Gtk.TextTag(name=f"bg_{name}")
            tag.set_property("background", color)
            tag_table.add(tag)

        # Style tags
        bold_tag = Gtk.TextTag(name="bold")
        bold_tag.set_property("weight", Pango.Weight.BOLD)
        tag_table.add(bold_tag)

        italic_tag = Gtk.TextTag(name="italic")
        italic_tag.set_property("style", Pango.Style.ITALIC)
        tag_table.add(italic_tag)

        underline_tag = Gtk.TextTag(name="underline")
        underline_tag.set_property("underline", Pango.Underline.SINGLE)
        tag_table.add(underline_tag)

        # Echo tag for user commands
        echo_tag = Gtk.TextTag(name="echo")
        echo_tag.set_property("foreground", "#888888")
        tag_table.add(echo_tag)

        # System message tag
        system_tag = Gtk.TextTag(name="system")
        system_tag.set_property("foreground", "#4E9A06")
        system_tag.set_property("style", Pango.Style.ITALIC)
        tag_table.add(system_tag)

    def append_text(self, text, tags=None, echo=False, announce=True):
        """Append text to the output view.

        Args:
            text: The text to append.
            tags: Optional list of tag names to apply.
            echo: If True, style as user echo (dimmed).
            announce: If True, queue for screen reader announcement.
        """
        end_iter = self._buffer.get_end_iter()

        if echo:
            tags = ["echo"]

        if tags:
            # Apply tags
            mark = self._buffer.create_mark(None, end_iter, True)
            self._buffer.insert(end_iter, text)
            start_iter = self._buffer.get_iter_at_mark(mark)
            end_iter = self._buffer.get_end_iter()
            for tag_name in tags:
                tag = self._buffer.get_tag_table().lookup(tag_name)
                if tag:
                    self._buffer.apply_tag(tag, start_iter, end_iter)
            self._buffer.delete_mark(mark)
        else:
            self._buffer.insert(end_iter, text)

        # Prune old content if needed
        self._prune_buffer()

        # Auto-scroll to bottom
        if self._auto_scroll:
            self._scroll_to_bottom()

        # Queue for screen reader announcement
        if announce and text.strip():
            self._queue_announcement(text)

    def append_ansi_text(self, text, active_tags=None):
        """Append text with ANSI formatting already parsed.

        Args:
            text: Plain text content.
            active_tags: List of active tag names from ANSI parsing.
        """
        self.append_text(text, tags=active_tags, announce=True)

    def append_spans(self, spans, announce=True):
        """Append a list of TextSpan objects.

        Args:
            spans: List of TextSpan objects from ANSI parser.
            announce: If True, queue for screen reader announcement.
        """
        from gtkmud.parsers.ansi import TextSpan

        announcement_text = []

        for span in spans:
            if not span.text:
                continue

            tags = span.get_tag_names()

            # Handle custom RGB colors that don't have predefined tags
            if span.style.fg_color and not span.style.fg_name:
                self._ensure_color_tag("fg", span.style.fg_color)
                tags.append(self._color_tag_name("fg", span.style.fg_color))

            if span.style.bg_color and not span.style.bg_name:
                self._ensure_color_tag("bg", span.style.bg_color)
                tags.append(self._color_tag_name("bg", span.style.bg_color))

            self.append_text(span.text, tags=tags if tags else None, announce=False)
            announcement_text.append(span.text)

        # Prune and scroll once after all spans
        self._prune_buffer()
        if self._auto_scroll:
            self._scroll_to_bottom()

        # Announce combined text
        if announce:
            combined = "".join(announcement_text)
            if combined.strip():
                self._queue_announcement(combined)

    def _color_tag_name(self, prefix: str, rgb: tuple) -> str:
        """Generate tag name for custom RGB color."""
        r, g, b = rgb
        return f"{prefix}_rgb_{r:02x}{g:02x}{b:02x}"

    def _ensure_color_tag(self, prefix: str, rgb: tuple):
        """Ensure a tag exists for a custom RGB color."""
        tag_name = self._color_tag_name(prefix, rgb)
        tag_table = self._buffer.get_tag_table()

        if tag_table.lookup(tag_name):
            return  # Already exists

        r, g, b = rgb
        color_str = f"#{r:02x}{g:02x}{b:02x}"

        tag = Gtk.TextTag(name=tag_name)
        if prefix == "fg":
            tag.set_property("foreground", color_str)
        else:
            tag.set_property("background", color_str)

        tag_table.add(tag)

    def _prune_buffer(self):
        """Remove old lines if buffer exceeds maximum."""
        line_count = self._buffer.get_line_count()
        if line_count > self.MAX_LINES:
            # Remove oldest lines
            lines_to_remove = line_count - self.MAX_LINES
            start = self._buffer.get_start_iter()
            end = self._buffer.get_iter_at_line(lines_to_remove)
            self._buffer.delete(start, end)

    def _scroll_to_bottom(self):
        """Scroll the view to the bottom."""
        # Use idle_add to ensure scroll happens after text is rendered
        GLib.idle_add(self._do_scroll_to_bottom)

    def _do_scroll_to_bottom(self):
        """Actually perform the scroll to bottom."""
        end_iter = self._buffer.get_end_iter()
        self.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)
        return False  # Don't repeat

    def _queue_announcement(self, text):
        """Queue text for screen reader announcement.

        Batches announcements to avoid overwhelming the screen reader.
        """
        from gtkmud.config import get_settings

        settings = get_settings()

        # Check if announcements are enabled
        if not settings.accessibility.announce_incoming:
            return

        self._announcement_buffer.append(text)

        # Reset timer if already running
        if self._announcement_timer:
            GLib.source_remove(self._announcement_timer)

        # Schedule announcement after configurable delay
        interval = settings.accessibility.announce_interval_ms
        self._announcement_timer = GLib.timeout_add(
            interval, self._flush_announcements
        )

    def _flush_announcements(self):
        """Flush buffered announcements to screen reader."""
        if self._announcement_buffer:
            # Combine buffered text
            combined = "".join(self._announcement_buffer)
            self._announcement_buffer.clear()

            # Use GTK 4.14+ announce() API for screen reader announcements
            # POLITE priority allows current speech to finish first
            if combined.strip():
                self.announce(combined, Gtk.AccessibleAnnouncementPriority.MEDIUM)

        self._announcement_timer = None
        return False  # Don't repeat

    def announce_text(self, text: str):
        """Immediately announce text to screen reader.

        Unlike queued announcements, this bypasses the buffer and
        announces immediately. Used for server-provided announcements
        like $buffer lines.

        Args:
            text: Text to announce to screen reader.
        """
        if text.strip():
            self.announce(text, Gtk.AccessibleAnnouncementPriority.MEDIUM)

    def clear(self):
        """Clear all content from the output view."""
        self._buffer.set_text("")

    def set_auto_scroll(self, enabled):
        """Enable or disable auto-scrolling to bottom."""
        self._auto_scroll = enabled
