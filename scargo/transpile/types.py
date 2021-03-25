from typing import Any, Dict, NamedTuple, Optional, Union

from scargo.core import WorkflowParams


class FilePut(NamedTuple):
    """
    Artifact permanently stored on S3.
    """

    root: str
    path: str


class Origin(NamedTuple):
    """
    For parameters and artifacts passed between steps, the step where they are first used as outputs (and thus assigned
    a value in Argo) need to be tracked.
    """

    step: str
    name: str


class FileTmp(NamedTuple):
    """
    Temporary artifact passed between steps, but with no expectation of being stored permanently.
    """

    path: str
    origin: Optional[Origin] = None


FileAny = Union[FilePut, FileTmp]
Artifacts = Dict[str, FileAny]


class Parameter(NamedTuple):
    value: Optional[Any] = None
    origin: Optional[Origin] = None


class Transput(NamedTuple):
    """
    Transput is the hypernym of inputs & outputs. Provides
    access to the WorkflowStep input/output parameters and artifacts.
    """

    parameters: Optional[Dict[str, Parameter]] = None
    artifacts: Optional[Artifacts] = None

    @property
    def exist(self) -> bool:
        """
        True if at least one of the two class attributes is not None or an
        empty dict.
        """
        return not self.parameters or not self.artifacts


class Context(NamedTuple):
    locals: Dict[str, Any]
    inputs: Dict[str, Transput]
    outputs: Dict[str, Transput]
    workflow_params: WorkflowParams
    mount_points: Dict[str, str]
