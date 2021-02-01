from scargo.core import MountPoint
from typing import Dict, NamedTuple, Optional


class FileInput(NamedTuple):
    root: MountPoint
    path: str
    name: str

    def open(self):
        pass

class FileOutput(NamedTuple):
    root: MountPoint
    path: str
    name: Optional[str] = None

    def open(self, file_name: Optional[str]):
        if self.name is None:
            if file_name is None:
                raise ValueError("Either init with file_name or provide one")
            else:
                self.name = file_name
        elif file_name is not None:
                raise ValueError("Trying to overwrite name")

        pass


# TODO: ScargoInput should be immutable, both input and output artifacts should have immutable fields
class ScargoInput(NamedTuple):
    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, FileInput]] = None


class ScargoOutput(NamedTuple):
    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, FileOutput]] = None
