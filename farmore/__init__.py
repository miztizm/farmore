"""
Farmore - Mirror every repo you own — in one command.

"In a world of ephemeral clouds, be the one with local backups." — schema.cx
"""

__version__ = "0.1.0"
__author__ = "miztizm"
__license__ = "MIT"

from .models import Config, Repository, TargetType, Visibility

__all__ = [
    "Config",
    "Repository",
    "TargetType",
    "Visibility",
    "__version__",
]
