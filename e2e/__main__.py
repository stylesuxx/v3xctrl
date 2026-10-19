"""Directory launcher: `python e2e ...` runs the harness from a checkout without installing anything."""

import sys
from pathlib import Path

E2E_DIRECTORY = Path(__file__).resolve().parent
SOURCE_DIRECTORY = E2E_DIRECTORY.parent / "src"

for directory in (E2E_DIRECTORY, SOURCE_DIRECTORY):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from v3xctrl_e2e.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
