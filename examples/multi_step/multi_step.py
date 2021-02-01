from pathlib import Path

from scargo.decorators import scargo, entrypoint
from scargo.args import FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint, MountPoints


@scargo(image="proteinqure/scargo")
def add_alpha(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    """
    Appends to the character "a" to the "value" in `scargo_in`.
    """
    scargo_out.parameters["out-value"] = str(scargo_in.parameters["init-value"]) + "a"


@scargo(image="proteinqure/scargo")
def add_beta(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    """
    Appends the character "b" to the "value" in `scargo_in`.
    """
    result = str(scargo_in.parameters["init-value"]) + "b"
    with scargo_out.artifacts["txt-out"].open(f"add_beta_{scargo_in.parameters['init-value']}.txt") as fi:
        fi.write(result)


@entrypoint
def main(mount_points: MountPoints, workflow_parameters: WorkflowParams) -> None:
    """
    Run two Python steps with the result of the previous step being passed by a parameter.
    """

    alpha_out = ScargoOutput(parameters={"out-value": None})
    add_alpha(ScargoInput(parameters={"init-value": workflow_parameters["input_val"]}), alpha_out)
    add_beta(
        ScargoInput(parameters={"value": alpha_out.parameters["out-value"]}),
        ScargoOutput(
            artifacts={
                "txt-out": FileOutput(
                    root=mount_points["root"],
                    path=workflow_parameters["output-path"],
                )
            }
        ),
    )


workflow_parameters = WorkflowParams(
    {
        "input-val": "1",
        "s3-bucket": "pq-dataxfer-tmp",
        "output-path": "testing/scargo-examples/output",
    }
)
mount_points = MountPoints(
    {
        "root": MountPoint(
            local=Path("~/s3-data/scargo-examples"),
            remote=f"s3://{workflow_parameters['s3-bucket']}",
        )
    }
)

if __name__ == "__main__":
    main(mount_points, workflow_parameters)
