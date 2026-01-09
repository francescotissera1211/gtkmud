# Cosmic Rage Soundpack for GTK MUD
# Converted from Mudlet soundpack
#
# This script works in conjunction with the built-in $sphook protocol
# parser which handles server-driven sounds. These are client-side
# triggers for events the server doesn't send sounds for.
#
# Sound files are downloaded from:
# http://nathantech.net:3000/CosmicRage/CosmicRageSounds/raw/branch/main/wav/
#
# To use .ogg files instead of .wav, change the file extension in settings.

# ============================================================================
# WELCOME AND LOGIN
# ============================================================================

# Play intro music when we see the welcome screen
trigger /^Welcome to:\s+[Cc]osmic\s+[Rr]age!$/ {
    sound "music/intromusic/defaultintro.wav" volume 30 loop infinite
}

# Stop intro music and register soundpack on successful login
trigger "New synaptic signal verified. Prepare yourself... For Cosmic Rage!" {
    # Intro music will be stopped by server sound commands
    send "@sp-register mudlet"
}

trigger "synaptic signal verified. Sleep mode disengaged. Welcome back to Cosmic Rage!" {
    send "@sp-register mudlet"
}

trigger "Your synaptic signal wavers for a moment, then returns with a snap!" {
    send "@sp-register mudlet"
}

# ============================================================================
# COMMON ALIASES
# ============================================================================

# Quick movement
alias "n" "north"
alias "s" "south"
alias "e" "east"
alias "w" "west"
alias "u" "up"
alias "d" "down"
alias "ne" "northeast"
alias "nw" "northwest"
alias "se" "southeast"
alias "sw" "southwest"

# Combat shortcuts
alias "ga" "get all"
alias "aa" "attack all"

# ============================================================================
# OPTIONAL: GAG NOISY LINES
# ============================================================================

# Uncomment these to hide repetitive messages:
# gag /^\[OOC\].*$/
# gag /^You hear.*$/

# ============================================================================
# CUSTOM SOUND TRIGGERS
# ============================================================================

# You can add your own sound triggers here. Example:
# sound_trigger "You have received a private message" "general/comms/tell.wav" volume 80

# Tell/message notification
sound_trigger /^\w+ tells you '/ "general/comms/tell.wav" volume 70 priority 90

# ============================================================================
# AMBIENCE EXAMPLES
# ============================================================================

# The server handles most ambience via $sphook, but you can override or
# add custom ambience triggers here:

# Example: Custom ambience for specific rooms
# trigger "You are inside the cargo bay" {
#     ambience "ambiances/hangar.wav" loop volume 50
# }

# trigger "You step outside onto the planet surface" {
#     ambience "ambiances/forest.wav" loop volume 60
# }

# Stop ambience when leaving specific areas
# trigger "You leave the area" {
#     ambience stop
# }
