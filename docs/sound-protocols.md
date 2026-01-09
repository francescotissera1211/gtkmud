# Sound Protocol Support

GTK MUD supports multiple sound protocols for playing audio triggered by the MUD server.

## MSP (MUD Sound Protocol)

The standard MUD Sound Protocol uses inline triggers in the text stream.

### Sound Triggers
```
!!SOUND(filename.wav)
!!SOUND(filename.wav V=80 L=3 P=50 T=combat U=http://example.com/sounds/)
```

Parameters:
- **V** (Volume): 0-100, default 100
- **L** (Loops): Number of times to play, -1 for infinite, default 1
- **P** (Priority): 0-100, higher priority sounds interrupt lower, default 50
- **T** (Type): Category tag for the sound
- **U** (URL): Base URL for downloading the sound file

### Music Triggers
```
!!MUSIC(background.wav)
!!MUSIC(background.wav V=50 L=-1 C=1 U=http://example.com/music/)
```

Parameters:
- **V** (Volume): 0-100
- **L** (Loops): -1 for infinite loop
- **C** (Continue): 1 to continue playing, 0 to restart
- **U** (URL): Base URL for downloading

### Stop Commands
```
!!SOUND(Off)
!!MUSIC(Off)
```

## MCMP (Client.Media Protocol)

GMCP-based media protocol using JSON messages.

### Client.Media.Play
```json
{
  "name": "sound.wav",
  "type": "sound",
  "url": "http://example.com/sounds/",
  "volume": 80,
  "loops": 1,
  "priority": 50
}
```

Types: `sound`, `music`, `ambience`

### Client.Media.Stop
```json
{
  "type": "sound"
}
```

### Client.Media.Load
Pre-cache a sound file:
```json
{
  "name": "sound.wav",
  "url": "http://example.com/sounds/"
}
```

## SPHook Protocol (Cosmic Rage)

A custom protocol used by Cosmic Rage MUD where the server sends sound commands as special text lines.

### Format
```
$sphook action:path:volume:pitch:pan:id
```

Fields:
- **action**: `play`, `loop`, or `stop`
- **path**: Relative path to sound file (without extension)
- **volume**: 0-100
- **pitch**: Not currently used (send `na`)
- **pan**: Not currently used (send `na`)
- **id**: Unique identifier for stopping specific sounds

### Examples
```
$sphook play:general/combat/hit:50:na:na:hit1
$sphook loop:ambiances/forest:60:na:na:amb1
$sphook stop:na:na:na:na:amb1
```

### Sound Files
SPHook sounds are downloaded from:
```
http://nathantech.net:3000/CosmicRage/CosmicRageSounds/raw/branch/main/wav/
```

Or with `.ogg` extension:
```
http://nathantech.net:3000/CosmicRage/CosmicRageSounds/raw/branch/main/ogg/
```

### Buffer Announcements
The server can also send screen reader announcements:
```
$buffer Text to announce to screen reader
```

These lines are removed from display and sent directly to the screen reader.

### Version Check
```
$soundpack mudlet last version: 2
```

This line is used for update checking and is automatically hidden.

### Registering the Soundpack
When logging into Cosmic Rage, send:
```
@sp-register mudlet
```

This tells the server to send `$sphook` commands for sound events.

## Audio Channels

GTK MUD uses three audio channels:

1. **Sound Channel**: Short sound effects, multiple can overlap
2. **Music Channel**: Background music, single track at a time
3. **Ambience Channel**: Looping ambient sounds, single track

## Caching

Downloaded sounds are cached in `~/.cache/gtkmud/sounds/` to avoid re-downloading. The cache persists across sessions.

## Volume Control

Volume is controlled at multiple levels:
1. **Master Volume**: Affects all audio
2. **Channel Volumes**: Sound, Music, Ambience each have separate controls
3. **Per-Sound Volume**: Specified in the protocol command

Final volume = Master × Channel × Sound volume

Configure volumes in Preferences (Ctrl+,) → Sound.
