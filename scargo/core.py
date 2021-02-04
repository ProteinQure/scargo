from collections import UserDict
from pathlib import Path
from typing import Mapping, NamedTuple


class MountPoint(NamedTuple):
    """
    Maps location of data between local (filesystem used when running workflow with Python) and remote (S3 data used
    when running transpiled Argo workflow).
    """

    local: Path
    remote: str


class WorkflowParams(UserDict):
    """
    Immutable parameters for use across all steps in a workflow.
    """

    def __init__(self, __dict: Mapping[str, str]) -> None:
        super().__init__()
        for key, value in __dict.items():
            super().__setitem__(key, value)

    def __setitem__(self, key: str, item: str) -> None:
        raise AttributeError("WorkflowParams is immutable.")

    def __delitem__(self, key: str) -> None:
        raise AttributeError("WorkflowParams is immutable.")


class MountPoints(UserDict):
    """
    MountPoint collection defining all local <-> remote filesystem mappings for a given workflow.
    """

    def __init__(self, __dict: Mapping[str, MountPoint]) -> None:
        super().__init__()
        for key, value in __dict.items():
            super().__setitem__(key, value)

    def __setitem__(self, key: str, item: str) -> None:
        raise AttributeError("MountPoints is immutable.")

    def __delitem__(self, key: str) -> None:
        raise AttributeError("MountPoints is immutable.")
