from pathlib import Path
from typing import Dict

from scargo.decorators import scargo
from scargo.functions import iter_csv, write_txt
from scargo.items import ScargoInput, ScargoOutput


@scargo(image="proteinqure/scargo")
def add_alpha(scargo_in: ScargoInput) -> ScargoOutput:
    """
    Appends to the character "a" to the "value" in `scargo_in`.
    """
    output = ScargoOutput(parameters={"result": str(scargo_in.parameters["value"]) + "a"}, artifacts=None)
    return output


def main(workflow_params: Dict):
    """
    Opening a CSV file and executing a function per row.
    """

    for csv_line in iter_csv(workflow_params["csv_input"]):
        step_output = add_alpha(ScargoInput(parameters={"value": int(csv_line["command_arg"])}, artifacts=None))
        write_txt(
            step_output.parameters["result"],
            workflow_params["out_path"] / f"result_{csv_line['command_arg']}.txt",
        )


if __name__ == "__main__":
    params = {"csv_input": Path("add_alpha.csv"), "out_path": Path.cwd()}
    main(params)
