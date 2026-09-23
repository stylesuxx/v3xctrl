"""Tests for GPX repair and the repair_gpx app.

Broken files are made the way a crash makes them: write a real track with GpxWriter, then
cut its bytes short.
"""

import xml.etree.ElementTree as ElementTree

import pytest

from v3xctrl_telemetry.apps import repair_gpx
from v3xctrl_telemetry.dataclasses import GpsFix, GpsFixType
from v3xctrl_telemetry.GpxWriter import GpxWriter, RepairResult, repair_track

_GPX_NS = "{http://www.topografix.com/GPX/1/1}"


def _write_track(directory, points=3, break_after=None):
    writer = GpxWriter(directory)
    for index in range(points):
        writer.add_point(GpsFix(lat=52.52 + index * 0.0001, lng=13.405, fix_type=GpsFixType.FIX_3D))
        if index == break_after:
            writer.break_segment()
    writer.close()
    return writer.path


def _cut(path, marker, offset=0, last=True):
    """Truncate at a marker, as if the power went right there."""
    data = path.read_bytes()
    position = data.rfind(marker) if last else data.find(marker)
    assert position != -1, marker
    path.write_bytes(data[: position + offset])


def _point_counts(path):
    root = ElementTree.parse(path).getroot()
    return [len(segment) for segment in root.findall(f"{_GPX_NS}trk/{_GPX_NS}trkseg")]


class TestRepair:
    def test_open_track_is_closed_with_every_point_kept(self, tmp_path):
        path = _write_track(tmp_path, points=3)
        _cut(path, b"    </trkseg>")

        assert repair_track(path) is RepairResult.REPAIRED
        assert _point_counts(path) == [3]

    def test_half_written_point_is_dropped(self, tmp_path):
        path = _write_track(tmp_path, points=3)
        _cut(path, b"<sat>")

        assert repair_track(path) is RepairResult.REPAIRED
        assert _point_counts(path) == [2]

    def test_cut_right_after_a_segment_break_is_not_closed_twice(self, tmp_path):
        path = _write_track(tmp_path, points=2, break_after=1)
        _cut(path, b"  </trk>")

        assert repair_track(path) is RepairResult.REPAIRED
        text = path.read_text(encoding="utf-8")
        assert text.count("<trkseg>") == text.count("</trkseg>")
        assert _point_counts(path) == [2]

    def test_crash_inside_a_later_segment_keeps_the_earlier_ones(self, tmp_path):
        path = _write_track(tmp_path, points=4, break_after=1)
        _cut(path, b"<ele>")

        assert repair_track(path) is RepairResult.REPAIRED
        assert _point_counts(path) == [2, 1]

    def test_header_only_file_closes_with_an_empty_segment(self, tmp_path):
        path = _write_track(tmp_path, points=1)
        _cut(path, b"      <trkpt", last=False)

        assert repair_track(path) is RepairResult.REPAIRED
        assert _point_counts(path) == [0]

    def test_repair_is_idempotent(self, tmp_path):
        path = _write_track(tmp_path)
        _cut(path, b"<sat>")
        repair_track(path)
        repaired = path.read_bytes()

        assert repair_track(path) is RepairResult.ALREADY_CLOSED
        assert path.read_bytes() == repaired


class TestLeftUntouched:
    def test_closed_track(self, tmp_path):
        path = _write_track(tmp_path)
        before = path.read_bytes()

        assert repair_track(path) is RepairResult.ALREADY_CLOSED
        assert path.read_bytes() == before

    def test_not_a_gpx_file(self, tmp_path):
        path = tmp_path / "notes.gpx"
        path.write_text("<html>not a track</html>", encoding="utf-8")

        assert repair_track(path) is RepairResult.NOT_GPX
        assert path.read_text(encoding="utf-8") == "<html>not a track</html>"

    def test_empty_file(self, tmp_path):
        path = tmp_path / "track-empty.gpx"
        path.write_bytes(b"")

        assert repair_track(path) is RepairResult.UNREPAIRABLE
        assert path.read_bytes() == b""

    def test_cut_inside_the_header(self, tmp_path):
        path = _write_track(tmp_path)
        _cut(path, b"<metadata>", last=False)
        before = path.read_bytes()

        assert repair_track(path) is RepairResult.UNREPAIRABLE
        assert path.read_bytes() == before

    def test_dry_run(self, tmp_path):
        path = _write_track(tmp_path)
        _cut(path, b"<sat>")
        before = path.read_bytes()

        assert repair_track(path, dry_run=True) is RepairResult.REPAIRED
        assert path.read_bytes() == before


class TestApp:
    def test_repairs_every_broken_track(self, tmp_path, caplog):
        first = _write_track(tmp_path)
        second = tmp_path / "track-second.gpx"
        second.write_bytes(first.read_bytes())
        _cut(first, b"<sat>")
        _cut(second, b"    </trkseg>")

        with caplog.at_level("INFO", logger="repair_gpx"):
            exit_code = repair_gpx.main(["--path", str(tmp_path)])

        assert exit_code == 0
        assert _point_counts(first) == [2]
        assert _point_counts(second) == [3]
        assert caplog.text.count("repaired") == 2

    def test_dry_run_changes_nothing(self, tmp_path, caplog):
        path = _write_track(tmp_path)
        _cut(path, b"<sat>")
        before = path.read_bytes()

        with caplog.at_level("INFO", logger="repair_gpx"):
            exit_code = repair_gpx.main(["--path", str(tmp_path), "--dry-run"])

        assert exit_code == 0
        assert path.read_bytes() == before
        assert "would repair" in caplog.text

    def test_empty_directory(self, tmp_path, caplog):
        with caplog.at_level("INFO", logger="repair_gpx"):
            exit_code = repair_gpx.main(["--path", str(tmp_path)])

        assert exit_code == 0
        assert "No GPX files" in caplog.text

    def test_missing_directory_fails(self, tmp_path):
        assert repair_gpx.main(["--path", str(tmp_path / "missing")]) == 1

    def test_unrepairable_file_fails_the_run(self, tmp_path):
        (tmp_path / "track-empty.gpx").write_bytes(b"")

        assert repair_gpx.main(["--path", str(tmp_path)]) == 1

    def test_unreadable_file_is_reported_and_the_rest_still_repaired(self, tmp_path, monkeypatch, caplog):
        good = _write_track(tmp_path)
        _cut(good, b"<sat>")
        blocked = tmp_path / "track-blocked.gpx"
        blocked.write_bytes(b"")

        def fake_repair(path, dry_run=False):
            if path == blocked:
                raise PermissionError("permission denied")
            return repair_track(path, dry_run)

        monkeypatch.setattr(repair_gpx, "repair_track", fake_repair)

        with caplog.at_level("INFO", logger="repair_gpx"):
            exit_code = repair_gpx.main(["--path", str(tmp_path)])

        assert exit_code == 1
        assert "permission denied" in caplog.text
        assert _point_counts(good) == [2]


@pytest.mark.parametrize("points", [1, 5])
def test_repaired_file_matches_a_cleanly_closed_one(tmp_path, points):
    """Repair should produce exactly what a clean close would have."""
    clean = _write_track(tmp_path, points=points)
    expected = clean.read_bytes()
    _cut(clean, b"    </trkseg>")

    repair_track(clean)

    assert clean.read_bytes() == expected
