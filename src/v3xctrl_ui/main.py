import argparse
import faulthandler
import logging
import sys
from datetime import datetime

# On Windows in windowed mode, stdout/stderr are None.
# Attach to the parent console so output works when launched from a terminal.
if sys.platform == "win32" and sys.stdout is None:
    import ctypes

    if ctypes.windll.kernel32.AttachConsole(-1):
        sys.stdout = open("CONOUT$", "w")  # noqa: SIM115
        sys.stderr = open("CONOUT$", "w")  # noqa: SIM115

if sys.stderr is not None:
    faulthandler.enable()


def main() -> None:
    from v3xctrl_ui.core.AppState import AppState
    from v3xctrl_ui.core.MemoryTracker import MemoryTracker
    from v3xctrl_ui.core.Settings import Settings

    parser = argparse.ArgumentParser(description="RC Streamer")
    parser.add_argument(
        "--log", default="ERROR", help="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL). Default is ERROR."
    )
    parser.add_argument("--mem-profile", action="store_true", help="Enable periodic memory tracking using tracemalloc.")
    parser.add_argument("--log-to-file", action="store_true", help="Save logs to txt file.")
    parser.add_argument(
        "--config", default=None, help="Path to custom config file. If not specified, uses default location."
    )

    args, unknown = parser.parse_known_args()

    level_name = args.log.upper()
    level = getattr(logging, level_name, None)

    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {args.log}")

    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if args.log_to_file:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"{timestamp}.txt"
        handlers.append(logging.FileHandler(log_filename))

    logging.basicConfig(level=level, format=log_format, handlers=handlers)

    from v3xctrl_ui.utils.gstreamer import is_gstreamer_available

    if is_gstreamer_available():
        logging.info("GStreamer receiver available, will be used by default")
    else:
        logging.info("GStreamer not available, using PyAV receiver")

    mem_tracker = None
    if args.mem_profile:
        mem_tracker = MemoryTracker(interval=10, top=5)
        mem_tracker.start()

    settings = Settings(args.config)
    state = AppState(settings)

    while state.model.running:
        if not state.handle_events():
            break

        state.update()
        state.render()

        state.tick()

    state.shutdown()

    if mem_tracker:
        mem_tracker.stop()


if __name__ == "__main__":
    main()
