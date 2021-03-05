"""
1. Read in a file and select the nth comma-separated word.
2. Write this work to a file, but also pass it to the next step.
3. The next step appends "a" to this word N times.

Contrived example used to demonstrate full use of inputs/outputs, as well as parameters/artifacts.
"""
from scargo.decorators import scargo, entrypoint
from scargo.args import FileInput, FileOutput, ScargoInput, ScargoOutput, TmpTransput
from scargo.core import WorkflowParams, MountPoint, MountPoints
from scargo.paths import env_local_mountpoint


@scargo(image="python:alpine")
def get_nth_word(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    with scargo_in.artifacts["csv-file"].open(mode="r") as fi:
        words = fi.readline().split(",")

    word = words[int(scargo_in.parameters["word-index"])].strip()

    scargo_out.parameters["out-val"] = word

    with scargo_out.artifacts["out-file"].open("w+") as fi:
        fi.write(f"{scargo_in.parameters['pre-word']},{word},{scargo_in.parameters['post-word']}")


@scargo(image="python:alpine")
def add_multi_alpha(scargo_in: ScargoInput, scargo_out: ScargoOutput) -> None:
    """
    Appends to the character "a" to the "value" in `scargo_in`.
    """
    with scargo_in.artifacts["init-file"].open("r") as fi:
        prev_line = fi.readline()

    alphas = int(scargo_in.parameters["num-alphas"]) * "a"
    new_word = alphas + str(scargo_in.parameters["init-value"]) + alphas

    with scargo_out.artifacts["txt-out"].open(f"add_multi_{scargo_in.parameters['init-value']}.txt", "w+") as fi:
        fi.write(f"{prev_line}\n")
        fi.write(f"{workflow_parameters['pre-word']},{new_word},{workflow_parameters['post-word']}\n")


@entrypoint
def main(mount_points: MountPoints, workflow_parameters: WorkflowParams) -> None:
    nth_word_out = ScargoOutput(
        parameters={"out-val": None},
        artifacts={"out-file": TmpTransput("out-file.txt")},
    )
    get_nth_word(
        ScargoInput(
            parameters={
                "word-index": workflow_parameters["word-index"],
                "pre-word": workflow_parameters["pre-word"],
                "post-word": workflow_parameters["post-word"],
            },
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
                "init-value": nth_word_out.parameters["out-val"],
                "num-alphas": workflow_parameters["num-alphas"],
            },
            artifacts={"init-file": nth_word_out.artifacts["out-file"]},
        ),
        ScargoOutput(
            artifacts={"txt-out": FileOutput(root=mount_points["root"], path=workflow_parameters["output-path"])}
        ),
    )


workflow_parameters = WorkflowParams(
    {
        "word-index": "1",
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
            local=env_local_mountpoint(),
            remote=workflow_parameters["s3-bucket"],
        )
    }
)


if __name__ == "__main__":
    main(mount_points, workflow_parameters)
