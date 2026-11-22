"""Read-only Pattern Investigator core (not connected to a live service)."""
from .engine import InvalidInput, investigate, watchdog
__all__ = ["InvalidInput", "investigate", "watchdog"]
