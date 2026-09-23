"""Tests for GpxWriter."""

import xml.etree.ElementTree as ElementTree

import pytest

from v3xctrl_telemetry.dataclasses import GpsFix, GpsFixType
from v3xctrl_telemetry.GpxWriter import GpxWriter

_GPX_NS = "{http://www.topografix.com/GPX/1/1}"
_TPX_NS = "{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}"


def _make_fix(**overrides):
    fields = {
        "lat": 51.5,
        "lng": -0.1,
        "altitude": 123.456,
        "ground_speed": 5.0,
        "heading": 87.5,
        "fix_type": GpsFixType.FIX_3D,
        "satellites": 9,
        "horizontal_accuracy": 2.5,
        "pdop": 1.75,
        "fix_ok": True,
        "position_valid": True,
    }
    fields.update(overrides)
    return GpsFix(**fields)


def _parse(writer):
    return ElementTree.parse(writer.path).getroot()


@pytest.fixture()
def writer(tmp_path):
    return GpxWriter(tmp_path)


class TestFileCreation:
    def test_no_points_writes_nothing(self, writer, tmp_path):
        writer.close()

        assert writer.path is None
        assert list(tmp_path.iterdir()) == []

    def test_first_point_creates_named_file(self, writer, tmp_path):
        writer.add_point(_make_fix())
        writer.close()

        assert writer.path.parent == tmp_path
        assert writer.path.name.startswith("track-")
        assert writer.path.suffix == ".gpx"

    def test_missing_directory_is_created(self, tmp_path):
        target = tmp_path / "recordings"
        writer = GpxWriter(target)

        writer.add_point(_make_fix())
        writer.close()

        assert target.is_dir()


class TestDocumentStructure:
    def test_output_parses(self, writer):
        writer.add_point(_make_fix())
        writer.close()

        root = _parse(writer)

        assert root.tag == f"{_GPX_NS}gpx"
        assert root.get("version") == "1.1"

    def test_metadata_precedes_track(self, writer):
        writer.add_point(_make_fix())
        writer.close()

        children = [child.tag for child in _parse(writer)]

        assert children == [f"{_GPX_NS}metadata", f"{_GPX_NS}trk"]

    def test_trkpt_children_follow_schema_sequence(self, writer):
        writer.add_point(_make_fix())
        writer.close()

        point = _parse(writer).find(f"{_GPX_NS}trk/{_GPX_NS}trkseg/{_GPX_NS}trkpt")
        tags = [child.tag.replace(_GPX_NS, "") for child in point]

        assert tags == ["ele", "time", "fix", "sat", "pdop", "extensions"]

    def test_position_is_written_as_attributes(self, writer):
        writer.add_point(_make_fix(lat=48.858844, lng=2.294351))
        writer.close()

        point = _parse(writer).find(f"{_GPX_NS}trk/{_GPX_NS}trkseg/{_GPX_NS}trkpt")

        assert float(point.get("lat")) == pytest.approx(48.858844)
        assert float(point.get("lon")) == pytest.approx(2.294351)

    def test_values_land_in_the_right_elements(self, writer):
        writer.add_point(_make_fix())
        writer.close()

        point = _parse(writer).find(f"{_GPX_NS}trk/{_GPX_NS}trkseg/{_GPX_NS}trkpt")

        assert float(point.findtext(f"{_GPX_NS}ele")) == pytest.approx(123.46)
        assert point.findtext(f"{_GPX_NS}fix") == "3d"
        assert point.findtext(f"{_GPX_NS}sat") == "9"
        assert float(point.findtext(f"{_GPX_NS}pdop")) == pytest.approx(1.75)

    def test_speed_and_course_go_into_extensions(self, writer):
        writer.add_point(_make_fix())
        writer.close()

        point = _parse(writer).find(f"{_GPX_NS}trk/{_GPX_NS}trkseg/{_GPX_NS}trkpt")
        extension = point.find(f"{_GPX_NS}extensions/{_TPX_NS}TrackPointExtension")

        assert float(extension.findtext(f"{_TPX_NS}speed")) == pytest.approx(5.0)
        assert float(extension.findtext(f"{_TPX_NS}course")) == pytest.approx(87.5)

    def test_time_is_utc_with_a_z_suffix(self, writer):
        writer.add_point(_make_fix())
        writer.close()

        point = _parse(writer).find(f"{_GPX_NS}trk/{_GPX_NS}trkseg/{_GPX_NS}trkpt")

        assert point.findtext(f"{_GPX_NS}time").endswith("Z")

    @pytest.mark.parametrize(
        ("fix_type", "expected"),
        [
            (GpsFixType.NO_HARDWARE, "none"),
            (GpsFixType.NO_FIX, "none"),
            (GpsFixType.DEAD_RECKONING, "none"),
            (GpsFixType.FIX_2D, "2d"),
            (GpsFixType.FIX_3D, "3d"),
            (GpsFixType.GNSS_DEAD_RECKONING, "3d"),
        ],
    )
    def test_fix_type_maps_to_the_gpx_enum(self, writer, fix_type, expected):
        writer.add_point(_make_fix(fix_type=fix_type))
        writer.close()

        point = _parse(writer).find(f"{_GPX_NS}trk/{_GPX_NS}trkseg/{_GPX_NS}trkpt")

        assert point.findtext(f"{_GPX_NS}fix") == expected


class TestSegments:
    def test_break_then_point_opens_a_second_segment(self, writer):
        writer.add_point(_make_fix())
        writer.break_segment()
        writer.add_point(_make_fix())
        writer.close()

        segments = _parse(writer).findall(f"{_GPX_NS}trk/{_GPX_NS}trkseg")

        assert len(segments) == 2
        assert all(len(segment) == 1 for segment in segments)

    def test_break_before_close_leaves_no_empty_segment(self, writer):
        writer.add_point(_make_fix())
        writer.break_segment()
        writer.close()

        segments = _parse(writer).findall(f"{_GPX_NS}trk/{_GPX_NS}trkseg")

        assert len(segments) == 1

    def test_repeated_breaks_do_not_stack_closing_tags(self, writer):
        writer.add_point(_make_fix())
        writer.break_segment()
        writer.break_segment()
        writer.close()

        assert writer.path.read_text(encoding="utf-8").count("</trkseg>") == 1

    def test_break_before_any_point_is_a_noop(self, writer, tmp_path):
        writer.break_segment()

        assert writer.path is None
        assert list(tmp_path.iterdir()) == []


class TestClose:
    def test_close_twice_is_a_noop(self, writer):
        writer.add_point(_make_fix())
        writer.close()
        before = writer.path.read_bytes()

        writer.close()

        assert writer.path.read_bytes() == before

    def test_point_after_close_is_dropped(self, writer, tmp_path):
        writer.add_point(_make_fix())
        writer.close()
        before = writer.path.read_bytes()

        writer.add_point(_make_fix())

        assert writer.path.read_bytes() == before
        assert len(list(tmp_path.iterdir())) == 1

    def test_break_after_close_is_a_noop(self, writer):
        writer.add_point(_make_fix())
        writer.close()
        before = writer.path.read_bytes()

        writer.break_segment()

        assert writer.path.read_bytes() == before


class TestDurability:
    def test_points_are_readable_before_close(self, writer):
        """A killed process must leave the points it already wrote on disk."""
        writer.add_point(_make_fix())

        assert "</trkpt>" in writer.path.read_text(encoding="utf-8")

    def test_fsync_runs_on_the_configured_interval(self, writer, monkeypatch):
        synced = []
        monkeypatch.setattr("v3xctrl_telemetry.GpxWriter.os.fsync", lambda fd: synced.append(fd))
        monkeypatch.setattr("v3xctrl_telemetry.GpxWriter.FSYNC_EVERY_POINTS", 3)

        for _ in range(6):
            writer.add_point(_make_fix())

        assert len(synced) == 2
