"""Everything that talks to the FPL API lives in this package, so an API change breaks in one place."""

from app.fpl.client import FPLClient, FPLError, FPLNotFound, FPLSchemaError, FPLUnavailable

__all__ = ["FPLClient", "FPLError", "FPLNotFound", "FPLSchemaError", "FPLUnavailable"]
