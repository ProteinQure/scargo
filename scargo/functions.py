import csv
from pathlib import Path
import subprocess

from scargo.args import ScargoInput, ScargoOutput
from scargo.core import MountPoint
from scargo.template import fill_template


def iter_csv(mount_point: MountPoint, csv_file: Path):
    """
    Reads the `csv_file` and returns an iterator.

    Will have to be hand-written or generated YAML.
    """

    with open(mount_point.local / csv_file, "r") as fi:
        reader = csv.DictReader(fi)
        for line in reader:
            yield line


def run_bash_step(bash_template: Path, scargo_input: ScargoInput, scargo_output: ScargoOutput) -> None:
    """
    Fill in the variables of a bash script, then run it.

    Parameters
    ----------
    bash_template : Path
        File path to jinja2-like template, where variables to be filled are formatted between curly braces
    scargo_input : ScargoInput
        Scargo Input Artifacts and Parameters used to fill `bash_template`
    scargo_output : ScargoOutput
        Scargo Output Artifacts and Parameters used to fill `bash_template`
    """
    with bash_template.open("r") as fi:
        filled_template = fill_template(fi.readlines(), scargo_input, scargo_output)

    # use `bash -c`, since escaping and passing the command otherwise is too difficult
    subprocess.run(["bash", "-c", "".join(filled_template)], check=True)
