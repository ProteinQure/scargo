"""
Run a single bash step which processes a CSV file artifact (add_alpha.csv) and generates a single text file artifact
(command_types.txt) as output.
"""

from pathlib import Path

from scargo.decorators import entrypoint
from scargo.functions import run_bash_step
from scargo.args import FileInput, FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint, MountPoints
from scargo.paths import env_local_mountpoint


@entrypoint
def main(mount_points: MountPoints, workflow_parameters: WorkflowParams) -> None:
    run_bash_step(
        bash_template=Path(__file__).parent / "append-sh.j2",
        scargo_input=ScargoInput(
            artifacts={
                "input-csv": FileInput(
                    root=mount_points["root"],
                    path=workflow_parameters["input-path"],
                    name=workflow_parameters["input-csv"],
                )
            }
        ),
        scargo_output=ScargoOutput(
            artifacts={
                "txt-out": FileOutput(
                    root=mount_points["root"], path=workflow_parameters["output-path"], name="command_types.txt"
                )
            }
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
            remote=f"s3://{workflow_parameters['s3-bucket']}",
        )
    }
)


if __name__ == "__main__":
    main(mount_points, workflow_parameters)
