"""Per-run and per-test output on disk, plus the console summary."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from v3xctrl_e2e.log_expectations import LogRecord

DEFAULT_RUNS_DIRECTORY = Path(__file__).resolve().parents[1] / "runs"


@dataclass
class TestResult:
    name: str
    passed: bool
    duration_seconds: float
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class RunDirectory:
    def __init__(self, root: Path = DEFAULT_RUNS_DIRECTORY, timestamp: datetime | None = None) -> None:
        stamp = (timestamp or datetime.now()).strftime("%Y-%m-%d_%H-%M-%S")
        self.path = root / stamp
        self.path.mkdir(parents=True, exist_ok=True)

    def test_directory(self, test_name: str) -> Path:
        directory = self.path / test_name
        directory.mkdir(parents=True, exist_ok=True)

        return directory

    def write_json(self, relative_path: str, payload: Any) -> Path:
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")

        return target

    def write_text(self, relative_path: str, text: str) -> Path:
        target = self.path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

        return target


def render_journal(records: list[LogRecord]) -> str:
    return "".join(f"{record.captured_at:12.3f} {record.source:<24} {record.text}\n" for record in records)


def write_test_artifacts(
    run_directory: RunDirectory,
    result: TestResult,
    records: list[LogRecord],
    streamer_config: dict[str, Any] | None,
    viewer_settings: str,
) -> None:
    prefix = result.name
    run_directory.write_text(f"{prefix}/timeline.log", render_journal(records))
    run_directory.write_text(f"{prefix}/viewer-settings.toml", viewer_settings)
    if streamer_config is not None:
        run_directory.write_json(f"{prefix}/streamer-config.json", streamer_config)

    run_directory.write_json(f"{prefix}/result.json", asdict(result))


def write_summary(run_directory: RunDirectory, results: list[TestResult], metadata: dict[str, Any]) -> None:
    run_directory.write_json("summary.json", {"metadata": metadata, "results": [asdict(result) for result in results]})


def format_summary_table(results: list[TestResult]) -> str:
    name_width = max((len(result.name) for result in results), default=4)
    lines = [f"{'test':<{name_width}}  result  seconds", f"{'-' * name_width}  ------  -------"]
    for result in results:
        verdict = "PASS" if result.passed else "FAIL"
        lines.append(f"{result.name:<{name_width}}  {verdict:<6}  {result.duration_seconds:7.1f}")
        for failure in result.failures:
            lines.append(f"{'':<{name_width}}          - {failure}")

    passed = sum(1 for result in results if result.passed)
    lines.append(f"\n{passed}/{len(results)} passed")
    return "\n".join(lines)
