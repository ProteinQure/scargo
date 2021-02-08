"""
Open a CSV file and execute different functions based on the csv row content.
"""

from pathlib import Path

from scargo.decorators import scargo, entrypoint
from scargo.functions import iter_csv
from scargo.args import FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint, MountPoints
from scargo.paths import env_local_mountpoint


@scargo(image="proteinqure/scargo")
def add_one(scargo_input: ScargoInput, scargo_output: ScargoOutput) -> None:
    """
    Adds one to the "value" in `scargo_in`.
    """
    result = scargo_input.parameters["init-value"] + 1
    with scargo_output.artifacts["txt-out"].open(f"add_one_{scargo_input.parameters['init-value']}.txt") as fi:
        fi.write(result)


@scargo(image="proteinqure/scargo")
def add_two(scargo_input: ScargoInput, scargo_output: ScargoOutput) -> None:
    """
    Adds two to the "value" in `scargo_input`.

    """
    result = scargo_input.parameters["init-value"] + 2
    with scargo_output.artifacts["txt-out"].open(f"add_two_{scargo_input.parameters['init-value']}.txt") as fi:
        fi.write(result)


@entrypoint
def main(mount_points: MountPoints, workflow_parameters: WorkflowParams) -> None:
    for csv_line in iter_csv(
        mount_points["root"], Path(workflow_parameters["input-path"], workflow_parameters["input-csv"])
    ):
        command_type = csv_line["command_type"]
        command_arg = csv_line["command_arg"]

        input_items = ScargoInput(parameters={"init-value": int(command_arg)})
        output_items = ScargoOutput(
            artifacts={
                "txt-out": FileOutput(
                    root=mount_points["root"],
                    path=workflow_parameters["output-path"],
                )
            },
        )
        if command_type == "add_one":
            add_one(input_items, output_items)

        elif command_type == "add_two":
            add_two(input_items, output_items)


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
            remote=f"s3://{workflow_parameters['s3-bucket']}",
        )
    }
)


if __name__ == "__main__":
    main(mount_points, workflow_parameters)