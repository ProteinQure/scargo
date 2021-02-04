from scargo.paths import env_local_mountpoint

from scargo.decorators import scargo, entrypoint
from scargo.args import FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint, MountPoints


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
    """
    Run a single Python step with an artifact output.
    """

    add_alpha(
        ScargoInput(parameters={"init-value": workflow_parameters["input-val"]}),
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
        "input-val": "1",
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
