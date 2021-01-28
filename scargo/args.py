from pathlib import Path
from scargo.core import MountPoint
from typing import Dict, NamedTuple, Optional

# TODO: ScargoInput should be immutable, both input and output artifacts should have immutable fields
class ScargoInput(NamedTuple):
    parameters: Optional[Dict] = None
    artifacts: Optional[Dict] = None


class ScargoOutput(NamedTuple):
    parameters: Optional[Dict] = None
    artifacts: Optional[Dict] = None


class FileOutput(NamedTuple):
    root: MountPoint
    path: str
