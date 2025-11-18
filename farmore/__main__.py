"""
Entry point for running Farmore as a module.

Usage: python -m farmore

"The main entry point. Where it all begins. Or ends." — schema.cx
"""

from .cli import app

if __name__ == "__main__":
    app()
