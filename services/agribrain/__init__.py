import sys
from pathlib import Path

_agribrain_dir = str(Path(__file__).resolve().parent)
if _agribrain_dir not in sys.path:
    sys.path.insert(0, _agribrain_dir)
