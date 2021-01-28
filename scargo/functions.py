import csv
from pathlib import Path
from scargo.args import ScargoInput, ScargoOutput
from scargo.core import MountPoint


def iter_csv(mount_point: MountPoint, csv_file: Path):
    """
    Reads the `csv_file` and returns an iterator.

    Will have to be hand-written or generated YAML.
    """

    with open(mount_point.local / csv_file, "r") as fi:
        reader = csv.DictReader(fi)
        for line in reader:
            yield line


def run_bash_step(bash_template, scargo_inputs: ScargoInput, scargo_outputs: ScargoOutput) -> None:
    """
    Fill in the variables of a bash script, then run it
    """
    pass
