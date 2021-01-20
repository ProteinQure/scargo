from typing import Dict, Optional

from scargo.decorators import scargo
from scargo.functions import iter_csv, workdir_file
from scargo.items import ScargoInput, ScargoOutput


@scargo(image="proteinqure/scargo")
def add_one(parameters: Optional[Dict]) -> ScargoOutput:
    """
    Adds one to the "value" in `scargo_in`.
    """
    output = ScargoOutput(parameters={"result": parameters["value"] + 1}, artifacts=None)
    return output


@scargo(image="proteinqure/scargo")
def add_two(parameters: Optional[Dict]) -> ScargoOutput:
    """
    Adds two to the "value" in `scargo_in`.

    """
    result = parameters["value"] + 2
    with workdir_file("some_file_name") as fi:
        fi.write()
    output = ScargoOutput(parameters={"result": }, artifacts=None)
    return output


# TODO: should probably mark the argo entrypoint with a decorator
def main(workflow_params: Dict):
    """
    Opening a CSV file and executing different functions based on the entries
    in the CSV.
    """

    for csv_line in iter_csv(workflow_params["csv_input"]):
        command_type = csv_line["command_type"]
        command_arg = csv_line["command_arg"]

        # run either `add_one` or `add_two` depending on the `command_type` column
        input_items = ScargoInput(parameters={"value": int(command_arg)}, artifacts=None)
        if command_type == "add_one":
            step_output = add_one(input_items)

        elif command_type == "add_two":
            step_output = add_two(input_items)

        # write the output to file
        write_txt(
            step_output.parameters["result"], workflow_params["out_path"] / f"result_{command_type}_{command_arg}.txt"
        )


if __name__ == "__main__":
    # Assuming there's some way to sync these input and output files from S3
    LOCAL_ROOT = PKG_ROOT_DIR / "task_files"
    ROOT_S3_PATH = "s3://pq-dataxfer-tmp/testing/scargo-prototype/"
    params = {"csv_input": LOCAL_ROOT / "add_numbers.csv", "out_path": LOCAL_ROOT}
    main(params)
