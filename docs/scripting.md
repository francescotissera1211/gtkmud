# GTK MUD Scripting Guide

GTK MUD includes a custom scripting language for automating responses to game text. Scripts can play sounds, gag (hide) text, create command aliases, and more.

## Script Files

Script files use the `.mud` extension and are plain text files. Load a script via:
- The Connect dialog's "Script File" field
- A profile's saved script path

Scripts are located in `~/.local/share/gtkmud/scripts/` by convention.

## Basic Syntax

Comments start with `#`:
```
# This is a comment
```

Strings use double quotes:
```
"Hello world"
```

Regular expressions use forward slashes:
```
/^Player tells you/
```

Add `i` after the closing slash for case-insensitive matching:
```
/hello/i
```

## Triggers

Triggers execute actions when text from the server matches a pattern.

### Literal Triggers
```
trigger "You have been slain" {
    sound "death.wav"
}
```

### Regex Triggers
```
trigger /^(\w+) tells you '(.+)'$/ {
    sound "tell.wav" volume 80
}
```

Capture groups can be accessed with `match(N)`:
```
trigger /^(\w+) says: (.+)$/ {
    send "reply " + match(1) + " I heard you say: " + match(2)
}
```

### Trigger Actions

#### sound
Play a sound file:
```
sound "filename.wav"
sound "path/to/sound.wav" volume 80
sound "alert.wav" volume 100 priority 90
sound "loop.wav" loop 3           # Play 3 times
sound "ambient.wav" loop infinite  # Loop forever
sound "charging.wav" id "charge1" loop infinite  # With explicit ID
```

Stop sounds:
```
sound stop              # Stop all sounds
sound stop "charge1"    # Stop specific sound by ID
```

The `id` option allows you to later stop a specific sound. Without an explicit ID, sounds are assigned auto-generated IDs.

#### music
Play background music (single track channel — replaces any current music):
```
music "theme.ogg"
music "battle.ogg" volume 80
music "boss.ogg" volume 90 loop 3     # Play 3 times
music "explore.ogg" loop infinite      # Loop forever
music "calm.ogg" continue              # Don't restart if already playing
music stop                             # Stop current music
```

Music plays on a dedicated channel separate from sound effects. Only one
music track plays at a time — starting a new track replaces the previous one.
The `continue` option prevents restarting a track that's already playing.

#### ambience
Control background ambient sounds:
```
ambience "forest.wav" loop volume 60
ambience "rain.wav" loop fadein 2000  # 2 second fade in
ambience stop  # Stop current ambience
```

#### send
Send a command to the server:
```
send "north"
send "say Hello " + $name
```

#### gag
Hide the matched line from display:
```
trigger /^\[SPAM\]/ {
    gag
}
```

#### highlight
Highlight the matched line (not fully implemented):
```
trigger "ALERT" {
    highlight red
}
```

#### Variables
Set variables for later use:
```
trigger "You are in (\w+)" {
    $location = match(1)
}
```

#### Conditionals
```
trigger "combat starts" {
    if $music == "off" {
        sound "battle.wav"
    } else {
        ambience "combat_ambient.wav" loop
    }
}
```

## Gags

Gags hide matching lines from the output:

```
# Hide OOC channel
gag /^\[OOC\]/

# Hide spam
gag "You are too tired to do that."
```

## Aliases

Aliases expand short commands into longer ones:

```
alias "n" "north"
alias "s" "south"
alias "ga" "get all"
alias "aa" "attack all"
```

Aliases also pass through extra arguments:
```
alias "t" "tell"
# Typing "t bob hello" sends "tell bob hello"
```

## Sound Triggers (Shorthand)

A shorthand for simple sound-on-match triggers:

```
sound_trigger "thunder rumbles" "thunder.wav" volume 70
sound_trigger /^You hit/ "hit.wav" volume 50 priority 80
```

## Connection Hooks

Run actions when connecting or disconnecting from the server. These fire on
the TCP connection itself, before any game text is received.

### on_connect
```
on_connect {
    music "intro/theme.ogg"
}
```

### on_disconnect
```
on_disconnect {
    music stop
    ambience stop
}
```

Connection hooks support all the same actions as triggers: `sound`, `music`,
`ambience`, `send`, and variable assignments. They do not have pattern matching
since they fire on connection events, not text.

## Variables

Variables store state between triggers:

```
# Set at top level
$combat = "false"

trigger "Combat begins" {
    $combat = "true"
    ambience "battle.wav" loop
}

trigger "Combat ends" {
    $combat = "false"
    ambience stop
}
```

## Conditions

Conditions compare variables or match groups:

```
if $variable == "value" {
    # actions
}

if match(1) != "" {
    # capture group was not empty
}

# Numeric comparisons
if $health < "50" {
    sound "lowhealth.wav"
}
```

Operators: `==`, `!=`, `<`, `>`, `<=`, `>=`

## Complete Example

```
# Cosmic Rage Soundpack
# Load this script when connecting to Cosmic Rage

# Play theme music on connection (before login)
on_connect {
    music "music/intro.ogg"
}

# Stop all audio on disconnect
on_disconnect {
    music stop
    ambience stop
}

# Movement aliases
alias "n" "north"
alias "s" "south"
alias "e" "east"
alias "w" "west"

# Register soundpack on login
trigger "Welcome back to Cosmic Rage!" {
    send "@sp-register mudlet"
}

# Tell notification
sound_trigger /^\w+ tells you/ "comms/tell.ogg" volume 70

# Combat music and ambience
trigger "Combat begins" {
    $combat = "true"
    music "music/battle.ogg" loop infinite volume 60
    ambience "combat/battle_ambient.ogg" loop volume 50
}

trigger "Combat ends" {
    $combat = "false"
    music stop
    ambience stop
}

# Vehicle charging with sound stop
trigger "Your vehicle begins charging" {
    sound "vehicle/charging.ogg" id "vehicle_charge" loop infinite volume 40
}

trigger "Your vehicle is fully charged" {
    sound stop "vehicle_charge"
    sound "vehicle/charged.ogg"
}

# Gag spammy messages
gag /^\[AutoSave\]/
gag "You feel a bit better."
```

## Sound File Locations

Local sounds are searched in:
1. `~/.local/share/gtkmud/sounds/`
2. Relative to script file location

Remote sounds (from MSP/SPHook) are cached in:
- `~/.cache/gtkmud/sounds/`

### Sound File Resolution

GTK MUD uses a three-level fallback when looking for sound files:

1. **Exact match** — Looks for the file at the exact path specified.
2. **Case-insensitive match** — If exact match fails, searches the directory
   case-insensitively. This handles soundpacks authored on case-insensitive
   filesystems (Windows/macOS) being used on Linux.
3. **Numbered variant selection** — If neither exact nor case-insensitive match
   is found, looks for files matching the pattern `name` + digits + extension
   (e.g. `theme1.ogg`, `theme2.ogg`) and picks one at random. This supports
   the common MUD soundpack pattern of providing multiple variants of a sound
   for random variation.

For example, if a script plays `"miriani/music/theme.ogg"` and no exact file
exists, GTK MUD will find `theme1.ogg`, `theme2.ogg`, etc. and randomly select
one each time the sound is triggered.

The numbered variant search is also case-insensitive, so `"misc/command.ogg"`
will match `Command1.ogg`, `Command2.ogg`, etc.
