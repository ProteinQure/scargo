"""
Control flow chooses between two Python steps based on a workflow parameter.
"""

from scargo.decorators import scargo, entrypoint
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
    step_input = ScargoInput(parameters={"init-value": workflow_parameters["input-val"]})
    step_output = ScargoOutput(
        artifacts={
            "txt-out": FileOutput(
                root=mount_points["root"],
                path=workflow_parameters["output-path"],
            )
        }
    )

    if workflow_parameters["input-type"] == "alpha":
        add_alpha(step_input, step_output)
    elif workflow_parameters["input-type"] == "beta":
        add_beta(step_input, step_output)


workflow_parameters = WorkflowParams(
    {
        "input-val": "m_s_w_c",
        "input-type": "alpha",
        "s3-bucket": "pq-dataxfer-tmp",
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
