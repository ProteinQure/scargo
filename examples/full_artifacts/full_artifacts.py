"""
Write a function with:
 - input artifacts
 - input parameters
 - output artifacts
 - output parameters
 - input parameter from workflow

 # TODO: make this example less contrived
 # TODO: use the return parameter for the length instead
"""
from pathlib import Path

from scargo.decorators import scargo, entrypoint
from scargo.args import FileInput, FileOutput, ScargoInput, ScargoOutput
from scargo.core import WorkflowParams, MountPoint, MountPoints


@scargo(image="proteinqure/scargo")
def get_nth_word(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    with scargo_in.artifacts["csv-file"].open() as fi:
        words = fi.readline().split(",")

    word = words[int(scargo_in.parameters["word-index"])]

    scargo_out.parameters["out-val"] = word

    with scargo_out.artifacts["out-file"].open("out-file.txt") as fi:
        fi.write(f"{scargo_in.parameters['pre-word']},{word},{scargo_in.parameters['post-word']}")


@scargo(image="proteinqure/scargo")
def add_multi_alpha(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    """
    Appends to the character "a" to the "value" in `scargo_in`.
    """
    result = str(scargo_in.parameters["value"]) + "a"
    with scargo_out.artifacts["txt-out"].open(f"add_multi_{scargo_in.parameters['init-value']}.txt") as fi:
        fi.write(result)


@entrypoint
def main(mount_points: MountPoints, workflow_parameters: WorkflowParams) -> None:
    """
    Read in a file and select the nth comma-separated word.
    Write this work to a file, but also pass it to the next function.
    The next function appends "a" to this word N times.
    """
    nth_word_out = ScargoOutput(
        parameters={"out-value": None},
        artifacts={"out-file": FileOutput(root=mount_points["root"], path=workflow_parameters["output-path"], name="out-file.txt")},
    )
    get_nth_word(
        ScargoInput(
            parameters={"word-index": workflow_parameters},
            artifacts={
                "csv-file": FileInput(
                    root=mount_points["root"],
                    path=workflow_parameters["input-path"],
                    name=workflow_parameters["input-csv"],
                )
            },
        ),
        nth_word_out,
    )
    add_multi_alpha(
        ScargoInput(
            parameters={
                "init-value": nth_word_out.parameters["out-value"],
                "num-alphas": workflow_parameters["num-alphas"],
            },
            artifacts={
                "init-file": FileInput(
                    root=mount_points["root"],
                    path=nth_word_out.artifacts["out-file"].path,
                    name=nth_word_out.artifacts["out-file"].name,
                )
            },
        ),
        ScargoOutput(
            artifacts={"txt-out": FileOutput(root=mount_points["root"], path=workflow_parameters["output-path"])}
        ),
    )


workflow_parameters = WorkflowParams(
    {
        "input-val": "1",
        "pre-word": "pre",
        "post-word": "post",
        "num-alphas": "3",
        "s3-bucket": "pq-dataxfer-tmp",
        "input-path": "testing/scargo-examples",
        "input-csv": "add_alpha.csv",
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