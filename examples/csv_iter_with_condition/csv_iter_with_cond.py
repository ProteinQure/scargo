from pathlib import Path
from typing import Dict

from scargo.decorators import scargo, entrypoint
from scargo.functions import iter_csv
from scargo.args import FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint


@scargo(image="proteinqure/scargo")
def add_one(scargo_input: ScargoInput, scargo_output: ScargoOutput) -> None:
    """
    Adds one to the "value" in `scargo_in`.
    """
    result = scargo_input.parameters["init-value"] + 1
    with (scargo_output.artifacts["txt-out"].workdir_path / f"add_one_{scargo_input.parameters['init-value']}.txt").open("w+") as fi:
        fi.write(result)


@scargo(image="proteinqure/scargo")
# TODO: ideally, you should be able to use `return` to return output parameters
def add_two(scargo_input: ScargoInput, scargo_output: ScargoOutput) -> None:
    """
    Adds two to the "value" in `scargo_input`.

    """
    result = scargo_input.parameters["value"] + 2
    with (scargo_output.artifacts["txt-out"].workdir_path / f"add_two_{scargo_input.parameters['init-value']}.txt").open("w+") as fi:
        fi.write(result)


@entrypoint
def main(mount_points: Dict[str, MountPoint], workflow_parameters: Dict[str, str]) -> None:
    """
    Opening a CSV file and executing different functions based on the entries
    in the CSV.
    """

    for csv_line in iter_csv(
        Path(mount_points["root"], workflow_parameters["inputs-path"], workflow_parameters["input-csv"])
    ):
        command_type = csv_line["command_type"]
        command_arg = csv_line["command_arg"]

        # run either `add_one` or `add_two` depending on the `command_type` column
        input_items = ScargoInput(parameters={"init-value": int(command_arg)}, artifacts=None)
        output_items = ScargoOutput(
            parameters=None,
            artifacts={
                "txt-out": FileOutput(
                    workdir_path=Path("/workdir/out"),
                    root=mount_points["root"],
                    path=workflow_parameters["output-path"],
                )
            },
        )
        if command_type == "add_one":
            # TODO: make it more obvious output_items is being mutated
            add_one(input_items, output_items)

        elif command_type == "add_two":
            add_two(input_items, output_items)


workflow_parameters = WorkflowParams(
    mount_points={
        "root": MountPoint(
            local=".scratch/whatevs",
            remote="s3://pq-dataxfer-tmp/testing/scargo-prototype/",
        )
    },
    parameters={"input-csv": "add_numbers.csv", "output-path": "output"},
)

if __name__ == "__main__":
    main(workflow_parameters.mount_points, workflow_parameters.parameters)
