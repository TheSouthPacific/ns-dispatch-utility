from abc import ABC, abstractmethod
from typing import Any, Mapping

RenderContext = Mapping[str, Any]


class Feature(ABC):
    """Base class for a facade class which handles a feature."""

    @abstractmethod
    def cleanup(self) -> None:
        """Perform saves and cleanup before exiting."""
