"""Severity shared by the OSD status widgets."""

from enum import StrEnum


class StatusLevel(StrEnum):
    NEUTRAL = "neutral"
    GOOD = "good"
    WARNING = "warning"
    BAD = "bad"
