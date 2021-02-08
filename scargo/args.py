from io import TextIOWrapper
from typing import Dict, NamedTuple, Optional
from scargo.core import MountPoint


class FileInput(NamedTuple):
    """
    Wrapper around Python input file interface which is transpiled to an input artifact in Argo YAML.
    """

    root: MountPoint
    path: str
    name: str

    def open(self) -> TextIOWrapper:
        """
        Opens file for reading.

        Exists to enable Python functions with I/O to be tested locally while also being transpiled to Argo YAML.
        """
        return open(self.root.local / self.path / self.name, "r")


class FileOutput(NamedTuple):
    """
    Wrapper around Python file output interface which is transpiled to an output artifact in Argo YAML.
    """

    root: MountPoint
    path: str
    name: Optional[str] = None

    def open(self, file_name: Optional[str] = None) -> TextIOWrapper:
        """
        Opens file for writing.

        If `name` was not given at initialization, `file_name` can be given as a parameter.

        Exists to enable Python functions with I/O to be tested locally while also being transpiled to Argo YAML.
        """
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


class ScargoInput(NamedTuple):
    """
    Manages inputs (parameters and artifacts) to functions marked by the @scargo decorator.

    Enables transpilation of function inputs into Argo workflow template inputs. Should not be mutated inside a @scargo
    function.
    """

    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, FileInput]] = None


class ScargoOutput(NamedTuple):
    """
    Manages outputs (parameters and artifacts) to functions marked by the @scargo decorator.

    Enables transpilation of function outputs into Argo workflow template outputs. Only parameters should be mutated
    (assigned new values) inside a @scargo function.
    """

    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, FileOutput]] = None
