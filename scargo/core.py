from collections import UserDict
from pathlib import Path
from typing import NamedTuple, Mapping


class MountPoint(NamedTuple):
    local: Path
    # TODO: should actually have a type
    remote: str


class WorkflowParams(UserDict):
    def __init__(self, __dict: Mapping[str, str]) -> None:
        super().__init__(__dict=__dict)

    def __setitem__(self, key: str, item: str) -> None:
        raise AttributeError("WorkflowParams is immutable.")

    def __delitem__(self, key: str) -> None:
        raise AttributeError("WorkflowParams is immutable.")


class MountPoints(UserDict):
    def __init__(self, __dict: Mapping[str, MountPoint]) -> None:
        super().__init__(__dict=__dict)

    def __setitem__(self, key: str, item: str) -> None:
        raise AttributeError("MountPoints is immutable.")

    def __delitem__(self, key: str) -> None:
        raise AttributeError("MountPoints is immutable.")
