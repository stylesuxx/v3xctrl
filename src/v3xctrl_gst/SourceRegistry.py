from typing import Any, ClassVar

from v3xctrl_gst.Sources import (
    CameraSourceBuilder,
    FileSourceBuilder,
    SourceBuilder,
    TestSourceBuilder,
)


class SourceRegistry:
    _builders: ClassVar[dict[str, type[SourceBuilder]]] = {
        "camera": CameraSourceBuilder,
        "file": FileSourceBuilder,
        "test": TestSourceBuilder,
    }

    @classmethod
    def create(cls, name: str, settings: dict[str, Any]) -> SourceBuilder:
        """Create a source builder by name"""
        builder_class = cls._builders.get(name)
        if not builder_class:
            available = ", ".join(cls._builders.keys())
            raise ValueError(f"Unknown source builder: '{name}'. Available: {available}")

        return builder_class(settings)

    @classmethod
    def list_sources(cls) -> list[str]:
        return list(cls._builders.keys())
