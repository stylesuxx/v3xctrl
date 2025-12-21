from typing import Any, Dict, List, Type

from v3xctrl_gst.Sources import (
    SourceBuilder,
    CameraSourceBuilder,
    FileSourceBuilder,
    TestSourceBuilder,
)


class SourceRegistry:
    _builders: Dict[str, Type[SourceBuilder]] = {
        'camera': CameraSourceBuilder,
        'file': FileSourceBuilder,
        'test': TestSourceBuilder,
    }

    @classmethod
    def create(cls, name: str, settings: Dict[str, Any]) -> SourceBuilder:
        """Create a source builder by name"""
        builder_class = cls._builders.get(name)
        if not builder_class:
            available = ', '.join(cls._builders.keys())
            raise ValueError(f"Unknown source builder: '{name}'. Available: {available}")

        return builder_class(settings)

    @classmethod
    def list_sources(cls) -> List[str]:
        return list(cls._builders.keys())
