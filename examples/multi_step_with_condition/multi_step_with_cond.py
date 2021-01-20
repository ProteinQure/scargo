from pathlib import Path
from typing import Dict

from scargo.decorators import scargo
from scargo.functions import write_txt
from scargo.items import ScargoInput, ScargoOutput


@scargo(image="proteinqure/scargo")
def add_alpha(scargo_in: ScargoInput) -> ScargoOutput:
    """
    Appends the character "a" to the "value" in `scargo_in`.
    """
    output = ScargoOutput(parameters={"result": str(scargo_in.parameters["value"]) + "a"}, artifacts=None)
    return output


@scargo(image="proteinqure/scargo")
def add_beta(scargo_in: ScargoInput) -> ScargoOutput:
    """
    Appends the character "b" to the "value" in `scargo_in`.
    """
    output = ScargoOutput(parameters={"result": str(scargo_in.parameters["value"]) + "b"}, artifacts=None)
    return output


def main(workflow_params: Dict):
    """
    Opening a CSV file and executing different functions based on the entries
    in the CSV.
    """

    step_input = ScargoInput(parameters={"value": workflow_params["input_val"]}, artifacts=None)

    if workflow_params["input_type"] == "alpha":
        step_output = add_alpha(step_input)
    elif workflow_params["input_type"] == "beta":
        step_output = add_beta(step_input)

    write_txt(
        step_output.parameters["result"], workflow_params["out_path"] / f"result_{workflow_params['input_name']}.txt"
    )


if __name__ == "__main__":
    params = {"input_val": 1, "input_name": "test", "input_type": "alpha", "out_path": Path.cwd()}
    main(params)
