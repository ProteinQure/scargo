from dataclasses import dataclass
from datetime import date
from io import TextIOWrapper
from pathlib import Path
import tempfile
from typing import Any, Dict, Literal, NamedTuple, Optional

from scargo.core import MountPoint


class FileInput(NamedTuple):
    """
    Wrapper around Python input file interface which is transpiled to an input artifact in Argo YAML.
    """

    root: MountPoint
    path: str
    name: str

    def open(self, mode="r") -> TextIOWrapper:
        """
        Opens file for reading.

        Exists to enable Python functions with I/O to be tested locally while also being transpiled to Argo YAML.
        """
        if mode != "r":
            raise ValueError("Can only read from FileInput. Did you think this was a FileOutput or TmpTransput?")

        return open(self.root.local / self.path / self.name, "r")

    def bash_str(self) -> str:
        """
        String representation for filling bash templates.
        """
        return str(self.root.local / self.path / self.name)


@dataclass(frozen=True)
class TmpTransput:
    """
    Wrapper around Python file interface used for temporary file I/O.

    In Argo, this is transpiled to an output destined for the default AWS S3 bucket. In PQ Argo configuration, the
    default S3 bucket is pq-dataxfer-tmp. This periodically cleared bucket is used as a kind of temporary storage for
    data-transfer between Argo steps. Thus,  TmpTransput represents this temporary storage for Python and enables
    transpilation to Argo YAML.
    """

    name: str
    tmp_dir: Path = Path(tempfile.gettempdir()) / date.today().isoformat()

    def __post_init__(self):
        self.tmp_dir.mkdir(exist_ok=True)

    def open(self, mode: Literal["w+", "r"]) -> TextIOWrapper:
        file_path = self.tmp_dir / self.name
        if mode == "w+":
            return open(file_path, mode)
        elif mode == "r":
            if not file_path.exists():
                raise IOError("No file found. Are you trying to read from the TmpTransput before it's been written to?")
            else:
                return open(file_path, mode)
        else:
            raise ValueError("Unsupported file I/O mode.")

    def bash_str(self) -> str:
        """
        String representation for filling bash templates.
        """
        return str(self.tmp_dir / self.name)


class FileOutput(NamedTuple):
    """
    Wrapper around Python file output interface which is transpiled to an output artifact in Argo YAML.
    """

    root: MountPoint
    path: str
    name: Optional[str] = None

    def open(self, file_name: Optional[str] = None, mode="w+") -> TextIOWrapper:
        """
        Opens file for writing.

        If `name` was not given at initialization, `file_name` can be given as a parameter.

        Exists to enable Python functions with I/O to be tested locally while also being transpiled to Argo YAML.
        """
        if mode != "w+":
            raise ValueError("Can only write from FileOutput. Did you think this was a FileInput or TmpTransput?")

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

    def bash_str(self) -> str:
        """
        String representation for filling bash templates.
        """
        if self.name is None:
            raise ValueError("name must be set to provide value to fill bash template")
        else:
            return str(self.root.local / self.path / self.name)


class ScargoInput(NamedTuple):
    """
    Manages inputs (parameters and artifacts) to functions marked by the @scargo decorator.

    Enables transpilation of function inputs into Argo workflow template inputs. Should not be mutated inside a @scargo
    function.
    """

    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, Any]] = None


class ScargoOutput(NamedTuple):
    """
    Manages outputs (parameters and artifacts) to functions marked by the @scargo decorator.

    Enables transpilation of function outputs into Argo workflow template outputs. Only parameters should be mutated
    (assigned new values) inside a @scargo function.
    """

    parameters: Optional[Dict] = None
    artifacts: Optional[Dict[str, Any]] = None
