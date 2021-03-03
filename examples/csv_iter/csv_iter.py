"""
Open a CSV file and execute a function per row.
"""

from pathlib import Path

from scargo.decorators import scargo, entrypoint
from scargo.functions import iter_csv
from scargo.args import FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint, MountPoints
from scargo.paths import env_local_mountpoint


@scargo(image="proteinqure/scargo")
def add_alpha(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    """
    Appends to the character "a" to the "value" in `scargo_in`.
    """
    result = str(scargo_in.parameters["init-value"]) + "a"
    with scargo_out.artifacts["txt-out"].open(f"add_alpha_{scargo_in.parameters['init-value']}.txt") as fi:
        fi.write(result)


@entrypoint
def main(mount_points: MountPoints, workflow_parameters: WorkflowParams) -> None:
    for csv_line in iter_csv(
        mount_points["root"], Path(workflow_parameters["input-path"], workflow_parameters["input-csv"])
    ):
        add_alpha(
            ScargoInput(parameters={"init-value": csv_line["command_arg"]}),
            ScargoOutput(
                artifacts={
                    "txt-out": FileOutput(
                        root=mount_points["root"],
                        path=workflow_parameters["output-path"],
                    )
                },
            ),
        )


workflow_parameters = WorkflowParams(
    {
        "s3-bucket": "pq-dataxfer-tmp",
        "input-path": "testing/scargo-examples",
        "input-csv": "add_alpha.csv",
        "output-path": "testing/scargo-examples/output",
    }
)
mount_points = MountPoints(
    {
        "root": MountPoint(
            local=env_local_mountpoint(),
            remote=workflow_parameters["s3-bucket"],
        )
    }
)


if __name__ == "__main__":
    main(mount_points, workflow_parameters)
