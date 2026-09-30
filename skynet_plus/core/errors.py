from __future__ import annotations


class SkynetError(Exception):
    """Base class for everything Skynet+ raises on purpose."""


class ConfigError(SkynetError):
    """The configuration file or profile cannot be used."""


class ResolutionError(SkynetError):
    """A configured provider is missing, incompatible, or lacks a required capability.

    Raised *before* any provider is initialised, so the message is the diagnosis.
    """

    def __init__(self, problems) -> None:
        self.problems = list(problems)
        lines = [f"  - {p}" for p in self.problems]
        super().__init__("cannot resolve providers:\n" + "\n".join(lines))


class ProviderError(SkynetError):
    """A provider failed to initialise or reported itself unhealthy."""
