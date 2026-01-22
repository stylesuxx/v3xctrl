from .INA import INA
from .BatteryTelemetry import BatteryTelemetry, BatteryState
from .VideoCoreTelemetry import VideoCoreTelemetry
from .ServiceTelemetry import ServiceTelemetry
from .GstTelemetry import GstTelemetry
from .TelemetrySource import TelemetrySource
from .dataclasses import (
    GstFlags,
    ServiceFlags,
    VideoCoreFlags,
    ThrottleFlags,
    SignalInfo,
    CellInfo,
    LocationInfo,
    BatteryInfo,
    TelemetryPayload,
)

# Backwards compatibility
Battery = BatteryTelemetry

__all__ = [
  'INA',
  'BatteryTelemetry',
  'BatteryState',
  'Battery',
  'VideoCoreTelemetry',
  'VideoCoreFlags',
  'ThrottleFlags',
  'ServiceTelemetry',
  'ServiceFlags',
  'SignalInfo',
  'CellInfo',
  'LocationInfo',
  'BatteryInfo',
  'TelemetryPayload',
  'GstTelemetry',
  'GstFlags',
  'TelemetrySource',
]
