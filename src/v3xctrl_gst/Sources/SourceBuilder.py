from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class SourceBuilder(ABC):
    """Base class for source builders"""

    # Override in subclasses to indicate if source needs sync
    NEEDS_SYNC: bool = False

    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        self._output_element: Optional[Gst.Element] = None

    @abstractmethod
    def build(self, pipeline: Gst.Pipeline) -> Gst.Element:
        """
        Build and return the source element.

        Implementations must set self._output_element to the element
        that should be linked to the rest of the pipeline.
        """
        pass

    def get_output_element(self) -> Gst.Element:
        if self._output_element is None:
            raise RuntimeError("build() must be called before get_output_element()")

        return self._output_element
