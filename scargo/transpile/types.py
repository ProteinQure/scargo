from typing import Dict, NamedTuple, Optional


class FilePut(NamedTuple):
    root: str
    path: str


class Transput(NamedTuple):
    """
    Transput is the hypernym of inputs & outputs. Provides
    access to the WorkflowStep input/output parameters and artifacts.
    """

    parameters: Optional[Dict[str, str]] = None
    artifacts: Optional[Dict[str, FilePut]] = None

    @property
    def exist(self) -> bool:
        """
        True if at least one of the two class attributes is not None or an
        empty dict.
        """
        return (self.parameters is None or not self.parameters) or (self.artifacts is None or not self.artifacts)
