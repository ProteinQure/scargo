from pathlib import Path
from typing import Dict

from scargo.decorators import scargo, entrypoint
from scargo.functions import iter_csv
from scargo.args import FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint


@scargo(image="proteinqure/scargo")
def add_alpha(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    """
    Appends to the character "a" to the "value" in `scargo_in`.
    """
    result = str(scargo_in.parameters["value"]) + "a"
    with (scargo_out.artifacts["txt-out"] / f"add_one_{scargo_in.parameters['init-value']}.txt").open("w+") as fi:
        fi.write(result)


@entrypoint
def main(mount_points: Dict[str, MountPoint], workflow_parameters: Dict[str, str]) -> None:
    """
    Opening a CSV file and executing a function per row.
    """

    for csv_line in iter_csv(
        Path(mount_points["root"], workflow_parameters["inputs-path"], workflow_parameters["input-csv"])
    ):
        add_alpha(
            ScargoInput(parameters={"init-value": csv_line["command_arg"]}, artifacts=None),
            ScargoOutput(
                parameters=None,
                artifacts={
                    "txt-out": FileOutput(
                        workdir_path=Path("/workdir/out"),
                        root=mount_points["root"],
                        path=workflow_parameters["output-path"],
                    )
                },
            ),
        )


workflow_parameters = WorkflowParams(
    mount_points={
        "root": MountPoint(
            local=".scratch/whatevs",
            remote="s3://pq-dataxfer-tmp/testing/scargo-prototype/",
        )
    },
    parameters={"input-csv": "add_alpha.csv", "output-path": "output"},
)


if __name__ == "__main__":
    main(workflow_parameters.mount_points, workflow_parameters.parameters)
