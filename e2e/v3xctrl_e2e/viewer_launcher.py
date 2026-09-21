"""Starts the viewer under test and streams its log lines back."""

import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from v3xctrl_e2e.log_expectations import LogRecord, LogSource

FLATPAK_APP_ID = "com.v3xctrl.viewer"
STOP_GRACE_SECONDS = 5.0
HELP_TIMEOUT_SECONDS = 60.0

# SDL drops joystick input while the window is unfocused unless told otherwise,
# and the viewer window never has focus during a run.
SDL_SETTINGS: dict[str, str] = {
    "SDL_AUDIODRIVER": "dummy",
    "SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS": "1",
}


class ViewerKind(StrEnum):
    SOURCE = "source"
    FLATPAK = "flatpak"


class ViewerLauncher:
    def __init__(
        self,
        kind: ViewerKind,
        python_executable: str,
        source_directory: Path,
        headless: bool,
    ) -> None:
        self.kind = kind
        self.python_executable = python_executable
        self.source_directory = source_directory
        self.headless = headless
        # Preflight clears this for a build whose usage text lacks `--title`.
        self.supports_title = True

    def command(self, config_path: Path, title: str | None = None) -> list[str]:
        viewer_arguments = ["--log", "DEBUG", "--config", str(config_path), "--connect"]
        if title is not None and self.supports_title:
            viewer_arguments.extend(["--title", title])

        if self.kind == ViewerKind.FLATPAK:
            environment_flags = [f"--env={name}={value}" for name, value in self.sdl_settings().items()]
            return [
                "flatpak",
                "run",
                f"--filesystem={config_path.parent}",
                *environment_flags,
                FLATPAK_APP_ID,
                *viewer_arguments,
            ]

        return [self.python_executable, "-m", "v3xctrl_ui.main", *viewer_arguments]

    def help_command(self) -> list[str]:
        if self.kind == ViewerKind.FLATPAK:
            return ["flatpak", "run", FLATPAK_APP_ID, "--help"]

        return [self.python_executable, "-m", "v3xctrl_ui.main", "--help"]

    def help_text(self) -> str:
        """The viewer's own usage text, to confirm it is a build the harness can drive."""
        completed = subprocess.run(
            self.help_command(),
            cwd=self.source_directory if self.kind == ViewerKind.SOURCE else None,
            env=self.environment(),
            capture_output=True,
            text=True,
            timeout=HELP_TIMEOUT_SECONDS,
        )
        return completed.stdout + completed.stderr

    def sdl_settings(self) -> dict[str, str]:
        settings = dict(SDL_SETTINGS)
        if self.headless:
            settings["SDL_VIDEODRIVER"] = "dummy"

        return settings

    def environment(self) -> dict[str, str]:
        return {**os.environ, **self.sdl_settings()}

    def start(
        self,
        config_path: Path,
        log_path: Path,
        on_record: Callable[[LogRecord], None],
        source: LogSource = LogSource.VIEWER,
        title: str | None = None,
    ) -> "ViewerProcess":
        process = subprocess.Popen(
            self.command(config_path, title),
            cwd=self.source_directory if self.kind == ViewerKind.SOURCE else None,
            env=self.environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        return ViewerProcess(process, log_path, on_record, source)


class ViewerProcess:
    def __init__(
        self,
        process: subprocess.Popen[str],
        log_path: Path,
        on_record: Callable[[LogRecord], None],
        source: LogSource = LogSource.VIEWER,
    ) -> None:
        self.process = process
        self.log_path = log_path
        self.on_record = on_record
        self.source = source
        self._reader = threading.Thread(target=self._pump, name=f"{source}-log", daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.process.stdout is not None
        with self.log_path.open("w", encoding="utf-8") as log_file:
            for line in self.process.stdout:
                text = line.rstrip("\n")
                log_file.write(text + "\n")
                log_file.flush()
                self.on_record(LogRecord(self.source, text, time.monotonic()))

    def is_running(self) -> bool:
        return self.process.poll() is None

    def stop(self) -> int:
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=STOP_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

        self._reader.join(timeout=2.0)
        return self.process.returncode if self.process.returncode is not None else -1
