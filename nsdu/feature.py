from abc import ABC, abstractmethod


class Feature(ABC):
    """Base class for a facade class which handles a feature."""

    @abstractmethod
    def cleanup(self) -> None:
        """Perform saves and cleanup before exiting."""


class FeatureCliParser(ABC):
    """Base class for a facade class which handles a feature."""

    @abstractmethod
    def parse(self) -> None:
        """Perform saves and cleanup before exiting."""
