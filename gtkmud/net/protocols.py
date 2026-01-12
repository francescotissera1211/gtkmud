"""Telnet and MUD protocol constants."""

# Telnet protocol bytes
IAC = 255   # Interpret As Command
DONT = 254  # Refuse to perform option
DO = 253    # Request to perform option
WONT = 252  # Refusal to perform option
WILL = 251  # Agreement to perform option
SB = 250    # Subnegotiation Begin
GA = 249    # Go Ahead
EL = 248    # Erase Line
EC = 247    # Erase Character
AYT = 246   # Are You There
AO = 245    # Abort Output
IP = 244    # Interrupt Process
BREAK = 243 # Break
DM = 242    # Data Mark
NOP = 241   # No Operation
SE = 240    # Subnegotiation End

# Telnet options
OPT_BINARY = 0       # Binary Transmission
OPT_ECHO = 1         # Echo
OPT_RCP = 2          # Reconnection
OPT_SGA = 3          # Suppress Go Ahead
OPT_NAMS = 4         # Approx Message Size Negotiation
OPT_STATUS = 5       # Status
OPT_TM = 6           # Timing Mark
OPT_RCTE = 7         # Remote Controlled Trans and Echo
OPT_NAOL = 8         # Output Line Width
OPT_NAOP = 9         # Output Page Size
OPT_NAOCRD = 10      # Output Carriage-Return Disposition
OPT_NAOHTS = 11      # Output Horizontal Tab Stops
OPT_NAOHTD = 12      # Output Horizontal Tab Disposition
OPT_NAOFFD = 13      # Output Formfeed Disposition
OPT_NAOVTS = 14      # Output Vertical Tabstops
OPT_NAOVTD = 15      # Output Vertical Tab Disposition
OPT_NAOLFD = 16      # Output Linefeed Disposition
OPT_XASCII = 17      # Extended ASCII
OPT_LOGOUT = 18      # Logout
OPT_BM = 19          # Byte Macro
OPT_DET = 20         # Data Entry Terminal
OPT_SUPDUP = 21      # SUPDUP
OPT_SUPDUPOUTPUT = 22  # SUPDUP Output
OPT_SNDLOC = 23      # Send Location
OPT_TTYPE = 24       # Terminal Type
OPT_EOR = 25         # End of Record
OPT_TUID = 26        # TACACS User Identification
OPT_OUTMRK = 27      # Output Marking
OPT_TTYLOC = 28      # Terminal Location Number
OPT_3270REGIME = 29  # 3270 Regime
OPT_X3PAD = 30       # X.3 PAD
OPT_NAWS = 31        # Window Size
OPT_TSPEED = 32      # Terminal Speed
OPT_LFLOW = 33       # Remote Flow Control
OPT_LINEMODE = 34    # Linemode
OPT_XDISPLOC = 35    # X Display Location
OPT_OLD_ENVIRON = 36 # Environment Option (old)
OPT_AUTHENTICATION = 37  # Authentication
OPT_ENCRYPT = 38     # Encryption
OPT_NEW_ENVIRON = 39 # New Environment Option
OPT_TN3270E = 40     # TN3270E
OPT_CHARSET = 42     # Character Set
OPT_MSDP = 69        # MUD Server Data Protocol
OPT_COMPRESS = 85    # MCCP v1 (deprecated)
OPT_COMPRESS2 = 86   # MCCP v2
OPT_MSP = 90         # MUD Sound Protocol
OPT_MXP = 91         # MUD eXtension Protocol
OPT_ZMP = 93         # Zenith MUD Protocol
OPT_ATCP = 200       # Achaea Telnet Client Protocol
OPT_GMCP = 201       # Generic MUD Communication Protocol

# Option names for debugging
OPTION_NAMES = {
    OPT_BINARY: "BINARY",
    OPT_ECHO: "ECHO",
    OPT_SGA: "SGA",
    OPT_TTYPE: "TTYPE",
    OPT_EOR: "EOR",
    OPT_NAWS: "NAWS",
    OPT_LINEMODE: "LINEMODE",
    OPT_NEW_ENVIRON: "NEW-ENVIRON",
    OPT_MSDP: "MSDP",
    OPT_COMPRESS: "COMPRESS",
    OPT_COMPRESS2: "COMPRESS2",
    OPT_MSP: "MSP",
    OPT_MXP: "MXP",
    OPT_ZMP: "ZMP",
    OPT_ATCP: "ATCP",
    OPT_GMCP: "GMCP",
}


def get_option_name(option):
    """Get human-readable name for a telnet option."""
    return OPTION_NAMES.get(option, f"UNKNOWN({option})")


# Terminal type to send
TERMINAL_TYPE = b"GTKMUD"

# GMCP package names
GMCP_CORE_HELLO = "Core.Hello"
GMCP_CORE_SUPPORTS_SET = "Core.Supports.Set"
GMCP_CORE_SUPPORTS_ADD = "Core.Supports.Add"
GMCP_CORE_SUPPORTS_REMOVE = "Core.Supports.Remove"
GMCP_CLIENT_MEDIA_PLAY = "Client.Media.Play"
GMCP_CLIENT_MEDIA_STOP = "Client.Media.Stop"
GMCP_CLIENT_MEDIA_LOAD = "Client.Media.Load"

# MSDP commands
MSDP_VAR = 1
MSDP_VAL = 2
MSDP_TABLE_OPEN = 3
MSDP_TABLE_CLOSE = 4
MSDP_ARRAY_OPEN = 5
MSDP_ARRAY_CLOSE = 6
