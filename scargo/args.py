from typing import Dict, NamedTuple, Optional
from scargo.core import MountPoint


class FileInput(NamedTuple):
    root: MountPoint
    path: str
    name: str

    def open(self):
        return open(self.root.local / self.path / self.name, "r")


class FileOutput(NamedTuple):
    root: MountPoint
    path: str
    name: Optional[str] = None

    def open(self, file_name: Optional[str]):
        output_dir = self.root.local / self.path

        if self.name is None:
            if file_name is None:
                raise ValueError("Either init with file_name or provide one")
            else:
                output_file = file_name
        elif file_name is not None:
            raise ValueError("Trying to overwrite name")
        else:
            output_file = self.name

        output_dir.mkdir(parents=True, exist_ok=True)
        return open(output_dir / output_file, "w+")


# TODO: ScargoInput should be immutable, both input and output artifacts should have immutable fields
class ScargoInput(NamedTuple):
    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, FileInput]] = None


class ScargoOutput(NamedTuple):
    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, FileOutput]] = None
