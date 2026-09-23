"""Tests for GpsTrackLogger."""

import math
import xml.etree.ElementTree as ElementTree

import pytest

import v3xctrl_telemetry.GpsTrackLogger as track_logger_module
from v3xctrl_helper.helper import EARTH_RADIUS_METERS
from v3xctrl_telemetry.dataclasses import GpsFix, GpsFixType, GpsTrackMode
from v3xctrl_telemetry.GpsTrackLogger import GpsTrackLogger

_GPX_NS = "{http://www.topografix.com/GPX/1/1}"
_METERS_PER_DEGREE = EARTH_RADIUS_METERS * math.pi / 180


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now


class _Drive:
    """Feeds fixes at a fixed rate, moving north unless told otherwise."""

    STEP_SECONDS = 0.25  # exact in binary, so interval maths never lands a hair short

    def __init__(self, track_logger, clock):
        self.track_logger = track_logger
        self.clock = clock
        self.lat = 52.52

    def feed(self, count, meters_per_fix=5.0, **overrides):
        for _ in range(count):
            self.lat += meters_per_fix / _METERS_PER_DEGREE
            fields = {
                "lat": self.lat,
                "lng": 13.405,
                "fix_type": GpsFixType.FIX_3D,
                "satellites": 9,
                "fix_ok": True,
                "position_valid": True,
            }
            fields.update(overrides)
            self.clock.now += self.STEP_SECONDS
            self.track_logger.add_fix(GpsFix(**fields))

    def bad(self, count):
        self.feed(count, meters_per_fix=0.0, fix_type=GpsFixType.NO_FIX)


def _tracks(directory):
    return sorted(directory.glob("*.gpx"))


def _segment_sizes(path):
    root = ElementTree.parse(path).getroot()
    return [len(segment) for segment in root.findall(f"{_GPX_NS}trk/{_GPX_NS}trkseg")]


@pytest.fixture()
def clock(monkeypatch):
    fake = _Clock()
    monkeypatch.setattr(track_logger_module, "time", fake)
    return fake


def _make(tmp_path, clock, mode=GpsTrackMode.ALWAYS):
    track_logger = GpsTrackLogger(tmp_path, mode, min_satellites=6, interval=1.0, min_distance=1.0)
    return track_logger, _Drive(track_logger, clock)


class TestGate:
    @pytest.mark.parametrize(
        "overrides",
        [
            {"fix_type": GpsFixType.NO_FIX},
            {"fix_type": GpsFixType.FIX_2D},
            {"fix_ok": False},
            {"position_valid": False},
            {"satellites": 5},
        ],
    )
    def test_bad_fix_never_produces_a_point(self, tmp_path, clock, overrides):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(20, **overrides)
        track_logger.close()

        assert _tracks(tmp_path) == []

    def test_min_satellites_is_inclusive(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5, satellites=6)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]


class TestHysteresis:
    def test_arms_on_the_fifth_consecutive_good_fix(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]

    def test_a_bad_fix_resets_the_arming_count(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(4)
        drive.bad(1)
        drive.feed(4)
        track_logger.close()

        assert _tracks(tmp_path) == []

    def test_short_dropout_does_not_break_the_segment(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.bad(2)
        drive.feed(8)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [3]

    def test_sustained_dropout_starts_a_new_segment(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.bad(3)
        drive.feed(5)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1, 1]

    def test_new_segment_starts_with_a_point_even_when_parked(self, tmp_path, clock):
        """Without this the new segment would wait for the vehicle to move or a heartbeat."""
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.bad(3)
        drive.feed(5, meters_per_fix=0.0)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1, 1]

    def test_rearming_needs_the_full_count_again(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.bad(3)
        drive.feed(4)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]


class TestDecimation:
    def test_points_are_limited_to_the_interval(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.feed(20)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [6]

    def test_stationary_vehicle_writes_no_wander(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.feed(40, meters_per_fix=0.0)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]

    def test_stationary_vehicle_still_gets_heartbeat_points(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        drive.feed(124, meters_per_fix=0.0)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [3]


class TestModes:
    def test_off_writes_nothing(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.OFF)

        drive.feed(20)
        track_logger.close()

        assert _tracks(tmp_path) == []

    def test_always_ignores_the_recording_flag(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        track_logger.set_recording(True)
        track_logger.set_recording(False)
        drive.feed(4)
        track_logger.close()

        assert len(_tracks(tmp_path)) == 1
        assert _segment_sizes(_tracks(tmp_path)[0]) == [2]

    def test_with_recording_waits_for_the_flag(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.WITH_RECORDING)

        drive.feed(20)
        track_logger.close()

        assert _tracks(tmp_path) == []

    def test_with_recording_is_armed_before_the_flag_arrives(self, tmp_path, clock):
        """A settled fix should not cost another second of track once recording starts."""
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.WITH_RECORDING)

        drive.feed(10)
        track_logger.set_recording(True)
        drive.feed(1)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]

    def test_with_recording_dropout_while_idle_needs_rearming(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.WITH_RECORDING)

        drive.feed(5)
        drive.bad(3)
        track_logger.set_recording(True)
        drive.feed(4)
        track_logger.close()

        assert _tracks(tmp_path) == []

    def test_with_recording_closes_the_file_when_recording_stops(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.WITH_RECORDING)

        track_logger.set_recording(True)
        drive.feed(5)
        track_logger.set_recording(False)

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]

    def test_with_recording_gives_one_file_per_recording(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.WITH_RECORDING)

        track_logger.set_recording(True)
        drive.feed(5)
        track_logger.set_recording(False)
        track_logger.set_recording(True)
        drive.feed(1)
        track_logger.close()

        tracks = _tracks(tmp_path)
        assert len(tracks) == 2
        assert [_segment_sizes(track) for track in tracks] == [[1], [1]]

    def test_repeated_recording_flag_is_a_noop(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock, GpsTrackMode.WITH_RECORDING)

        track_logger.set_recording(True)
        drive.feed(5)
        track_logger.set_recording(True)
        drive.feed(4)
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [2]


class TestClose:
    def test_fix_after_close_creates_no_second_file(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        track_logger.close()
        drive.feed(10)

        assert len(_tracks(tmp_path)) == 1
        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]

    def test_close_twice_is_safe(self, tmp_path, clock):
        track_logger, drive = _make(tmp_path, clock)

        drive.feed(5)
        track_logger.close()
        track_logger.close()

        assert _segment_sizes(_tracks(tmp_path)[0]) == [1]

    def test_close_without_any_fix_leaves_no_file(self, tmp_path, clock):
        track_logger, _ = _make(tmp_path, clock)

        track_logger.close()

        assert _tracks(tmp_path) == []
