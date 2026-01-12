"""Entry point for running GTK MUD as a module."""

import sys


def main():
    """Main entry point for the GTK MUD application."""
    from gtkmud.app import run

    sys.exit(run())


if __name__ == "__main__":
    main()
