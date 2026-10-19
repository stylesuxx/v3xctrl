import sys
from pathlib import Path

AGENT_DIRECTORY = Path(__file__).resolve().parents[1] / "agent"

if str(AGENT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(AGENT_DIRECTORY))
