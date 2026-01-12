# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands

```bash
# Run the application (development)
python -m gtkmud

# Run tests
pytest

# Run a single test file
pytest tests/test_ansi_parser.py

# Run tests with coverage
pytest --cov=gtkmud

# Install in development mode
pip install -e ".[dev]"
```

## Architecture Overview

GTK MUD is a GTK4/libadwaita MUD client with accessibility as a primary concern. It uses Python with PyGObject bindings.

### Data Flow

```
MUD Server
    ↓
TelnetClient (asyncio) → MCCPHandler (zlib decompress)
    ↓
ConnectionManager (asyncio↔GTK bridge via GLib.idle_add)
    ↓
TextProcessor pipeline:
  1. MSPParser extracts !!SOUND()/!!MUSIC() triggers
  2. SPHookParser extracts $sphook sound commands and $buffer announcements
  3. ScriptInterpreter checks gags (suppress matching lines)
  4. ANSIParser converts escape codes to TextSpans with styles
  5. ScriptInterpreter runs triggers for sounds/actions
    ↓
OutputView (GtkTextView with accessibility)
    ↓
AT-SPI → Screen Reader (Orca via GTK 4.14+ announce() API)
```

### Key Modules

- **`ui/main_window.py`**: Central coordinator. Owns ConnectionManager, TextProcessor, SoundManager, and ScriptInterpreter. Routes data between components.

- **`net/connection.py`**: Bridges asyncio TelnetClient with GTK's GLib main loop. All callbacks marshal to GTK thread via `GLib.idle_add()`.

- **`net/telnet.py`**: Async telnet client handling IAC negotiation, MCCP v2 compression, GMCP/MSDP protocols. Uses state machine for parsing.

- **`parsers/text_processor.py`**: Pipeline coordinating ANSI parsing, MSP extraction, SPHook parsing, and gag checking. Returns `ProcessedText` with styled spans, sound triggers, and announcements.

- **`parsers/sphook.py`**: Parser for Cosmic Rage's `$sphook` sound protocol. Handles `$sphook action:path:volume:pitch:pan:id` commands and `$buffer` screen reader announcements.

- **`sound/manager.py`**: GStreamer-based audio with three channels (sound/music/ambience). Handles both MSP triggers and MCMP (GMCP Client.Media.*).

- **`scripting/parser.py`**: Lark-based DSL parser. Grammar defined in `grammar.lark`. Transforms parse tree into Script objects (Trigger, Gag, Alias, etc.).

- **`scripting/interpreter.py`**: Executes scripts. Provides `check_gag()`, `expand_alias()`, `process_line()`. Maintains variables and evaluates conditions.

### DSL Scripting

The custom DSL supports triggers, gags, aliases, and sound control:

```
trigger /^(\w+) tells you/ {
    sound "tell.wav" priority 90
    highlight cyan
}
gag /^\[OOC\]/
alias "n" "north"
sound_trigger "thunder" "thunder.wav" volume 70
```

Grammar is in `gtkmud/scripting/grammar.lark`. Parser uses Lark's LALR mode.

**Full documentation**: See `docs/scripting.md`

### Scripts Directory

The `scripts/` directory contains example soundpack scripts:

- **`cosmic_rage.mud`**: Converted from the Mudlet Cosmic Rage soundpack. Works with the built-in `$sphook` protocol parser for server-driven sounds, plus client-side triggers for welcome/login.

### Sound Protocol Support

1. **MSP (MUD Sound Protocol)**: Standard `!!SOUND()` and `!!MUSIC()` triggers
2. **MCMP (Client.Media.*)**: GMCP-based media protocol
3. **SPHook (Cosmic Rage)**: `$sphook action:path:volume:pitch:pan:id` format with `$buffer` for screen reader announcements

**Full documentation**: See `docs/sound-protocols.md`

### Threading Model

- GTK runs on main thread
- TelnetClient runs in separate asyncio event loop thread
- ConnectionManager marshals all callbacks to GTK thread via `GLib.idle_add()`
- Sound downloads run in daemon threads

### Configuration

Uses XDG paths (`~/.config/gtkmud/`, `~/.local/share/gtkmud/`, `~/.cache/gtkmud/`). Settings and profiles stored as TOML.

## Dependencies

- **PyGObject**: GTK4/libadwaita bindings
- **Lark**: DSL parsing
- **aiohttp**: Remote sound downloads (optional)
- **tomli-w**: TOML writing for config
- **GStreamer**: Audio playback (system library)
