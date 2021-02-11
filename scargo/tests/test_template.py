from pathlib import Path

import pytest

from scargo.args import FileInput, FileOutput, ScargoInput, ScargoOutput, MountPoint
from scargo.template import BashVar, extract_vars_from_str, get_bash_vars, get_missing_vars, get_vars, replace_vars


def test_get_vars_single_line():
    expected = [
        (
            0,
            [
                BashVar(var_type="inputs", io_type="artifacts", name="input-csv", location=slice(4, 34)),
                BashVar(var_type="outputs", io_type="artifacts", name="output-csv", location=slice(55, 87)),
            ],
        )
    ]
    result = get_vars(["cat {{inputs.artifacts.input-csv}} | cut -d ',' -f 1 > {{outputs.artifacts.output-csv}}"])
    assert result == expected


def test_get_vars_multi_line():
    expected = [
        (4, [BashVar(var_type="outputs", io_type="artifacts", name="extracted-pdb", location=slice(14, 49))]),
        (7, [BashVar(var_type="inputs", io_type="artifacts", name="sequence-file", location=slice(8, 42))]),
        (8, [BashVar(var_type="inputs", io_type="artifacts", name="pdb-file", location=slice(8, 37))]),
        (17, [BashVar(var_type="inputs", io_type="artifacts", name="sequence-file", location=slice(30, 64))]),
        (20, [BashVar(var_type="inputs", io_type="artifacts", name="pdb-file", location=slice(16, 45))]),
        (22, [BashVar(var_type="inputs", io_type="parameters", name="nstruct", location=slice(13, 42))]),
        (23, [BashVar(var_type="inputs", io_type="parameters", name="unique-id", location=slice(12, 43))]),
        (25, [BashVar(var_type="outputs", io_type="artifacts", name="silent-file", location=slice(17, 50))]),
        (
            28,
            [
                BashVar(var_type="outputs", io_type="artifacts", name="silent-file", location=slice(11, 44)),
                BashVar(var_type="outputs", io_type="artifacts", name="score-file", location=slice(47, 79)),
            ],
        ),
        (31, [BashVar(var_type="outputs", io_type="artifacts", name="extracted-pdb", location=slice(3, 38))]),
        (33, [BashVar(var_type="outputs", io_type="artifacts", name="silent-file", location=slice(16, 49))]),
        (34, [BashVar(var_type="inputs", io_type="parameters", name="pdb-file-name", location=slice(12, 47))]),
    ]
    lines = [
        "#!/bin/bash\n",
        "\n",
        "set -xe\n",
        "\n",
        "sudo mkdir -p {{outputs.artifacts.extracted-pdb}}\n",
        "sudo chmod -R a+rwX /workdir\n",
        "\n",
        "ls -alF {{inputs.artifacts.sequence-file}}\n",
        "ls -alF {{inputs.artifacts.pdb-file}}\n",
        "\n",
        "ROSETTA_BIN=/home/user/setup/rosetta/main/source/bin\n",
        "\n",
        "# Run cycpep_predict\n",
        "# Outputs one *.silent file per run\n",
        "# Each silent file contains coordinates and score for up to 1000 generated structures\n",
        "\n",
        "$ROSETTA_BIN/simple_cycpep_predict.default.linuxgccrelease \\\n",
        "-cyclic_peptide:sequence_file {{inputs.artifacts.sequence-file}} \\\n",
        "-cyclic_peptide:genkic_closure_attempts 5000 \\\n",
        "-cyclic_peptide:min_genkic_hbonds 2 \\\n",
        "-in:file:native {{inputs.artifacts.pdb-file}} \\\n",
        "-cyclic_peptide:cyclization_type n_to_c_amide_bond \\\n",
        "-out:nstruct {{inputs.parameters.nstruct}} \\\n",
        "-out:suffix {{inputs.parameters.unique-id}} \\\n",
        "-score:symmetric_gly_tables \\\n",
        "-out:file:silent {{outputs.artifacts.silent-file}}\n",
        "\n",
        "# Extract scores (RMSDs of each generated model to reference structure)\n",
        "grep SCORE {{outputs.artifacts.silent-file}} > {{outputs.artifacts.score-file}}\n",
        "\n",
        "# Extract individual PDBs (optional)\n",
        "cd {{outputs.artifacts.extracted-pdb}}\n",
        "$ROSETTA_BIN/extract_pdbs.default.linuxgccrelease \\\n",
        "-in:file:silent {{outputs.artifacts.silent-file}} \\\n",
        "-out:prefix {{inputs.parameters.pdb-file-name}}-",
    ]
    result = get_vars(lines)
    assert result == expected


@pytest.mark.parametrize(
    "line, expected_vars, expected_line",
    [
        (
            "{{var-a }} filler text {{ var-b }} even more {{ var-c}}",
            ["var-a", "var-b", "var-c"],
            " filler text  even more ",
        ),
        (
            "start {{ var-a}} filler text {{var-b}} even more {{var-c }} last one {{var-d}} end",
            ["var-a", "var-b", "var-c", "var-d"],
            "start  filler text  even more  last one  end",
        ),
    ],
)
def test_extract_vars_from_str(line, expected_vars, expected_line):
    """
    Test extracting variables from strings by verifying extracted variables and deleting their given spans.
    """
    all_vars, total_vars = extract_vars_from_str([line])
    assert total_vars == len(expected_vars)
    assert len(all_vars) == 1
    vars = all_vars[0]
    matches = vars[1]

    matched_vars = [match.group(0).strip() for match in matches]
    assert matched_vars == expected_vars

    trimmed_line = []
    last_stop = 0
    for match in matches:
        span = slice(match.span()[0] - 2, match.span()[1] + 2)
        trimmed_line.append(line[last_stop : span.start])
        last_stop = span.stop

    trimmed_line.append(line[last_stop:])

    assert "".join(trimmed_line) == expected_line


def test_extract_vars_from_str_no_vars():
    all_vars, total_vars = extract_vars_from_str(["No {vars} in this str"])
    assert all_vars == []
    assert total_vars == 0


@pytest.mark.parametrize("bad_str", ["This {{bad-format}} str", "{{also.bad}} str", "str {{so.bad.its.worse}}"])
def test_get_bash_vars_invalid_format(bad_str):
    all_vars, _ = extract_vars_from_str([bad_str])
    with pytest.raises(ValueError) as err:
        get_bash_vars(all_vars)

    assert "Invalid variable format" in str(err.value)


@pytest.mark.parametrize(
    "bad_str", ["This {{input.artifacts.bad}} str", "{{output.artifacts.output-csv}} str", "str {{nope.okay.what}}"]
)
def test_get_bash_vars_invalid_type(bad_str):
    all_vars, _ = extract_vars_from_str([bad_str])
    with pytest.raises(ValueError) as err:
        get_bash_vars(all_vars)

    assert "Invalid variable type" in str(err.value)


@pytest.mark.parametrize(
    "bad_str", ["This {{inputs.artifact.bad}} str", "{{outputs.parameter.output-csv}} str", "str {{inputs.okay.what}}"]
)
def test_get_bash_vars_invalid_io_type(bad_str):
    all_vars, _ = extract_vars_from_str([bad_str])
    with pytest.raises(ValueError) as err:
        get_bash_vars(all_vars)

    assert "Invalid IO type" in str(err.value)


@pytest.mark.parametrize(
    "bad_str",
    [
        "This {{inputs.artifacts.bad name}} str",
        "{{outputs.parameters.not'good}} str",
        "str {{inputs.parameters.why*bad&name}}",
    ],
)
def test_get_bash_vars_multi_invalid(bad_str):
    all_vars, _ = extract_vars_from_str([bad_str])
    with pytest.raises(ValueError) as err:
        get_bash_vars(all_vars)

    assert "Invalid variable name" in str(err.value)


def test_missing_vars():
    mount_point = MountPoint(
        local=Path("~/s3-data"),
        remote="s3://pq-dataxfer-tmp",
    )
    result = get_missing_vars(
        [
            # Should be determined to be missing due to no io_type="artifacts" given in ScargoInput
            (0, [BashVar(var_type="inputs", io_type="parameters", name="input-val", location=slice(4, 34))]),
            (
                1,
                [
                    # Should be determined to be missing due to no variable named "output-txt"
                    BashVar(var_type="outputs", io_type="artifacts", name="output-txt", location=slice(20, 30)),
                    # Should be found
                    BashVar(var_type="outputs", io_type="artifacts", name="txt-out", location=slice(53, 87)),
                ],
            ),
        ],
        ScargoInput(
            artifacts={
                "input-csv": FileInput(
                    root=mount_point,
                    path="testing/scargo-examples",
                    name="input.csv",
                )
            }
        ),
        ScargoOutput(
            artifacts={
                "txt-out": FileOutput(root=mount_point, path="testing/scargo-examples/output", name="output.txt")
            }
        ),
    )

    assert result == [
        (0, BashVar(var_type="inputs", io_type="parameters", name="input-val", location=slice(4, 34))),
        (1, BashVar(var_type="outputs", io_type="artifacts", name="output-txt", location=slice(20, 30))),
    ]


def test_replace_vars():
    mount_point = MountPoint(
        local=Path("~/s3-data"),
        remote="s3://pq-dataxfer-tmp",
    )
    result = replace_vars(
        "cat {{inputs.artifacts.input-csv}} | cut -d ',' -f 1 > {{outputs.artifacts.txt-out}}",
        [
            BashVar(var_type="inputs", io_type="artifacts", name="input-csv", location=slice(4, 34)),
            BashVar(var_type="outputs", io_type="artifacts", name="txt-out", location=slice(53, 87)),
        ],
        ScargoInput(
            artifacts={
                "input-csv": FileInput(
                    root=mount_point,
                    path="testing/scargo-examples",
                    name="input.csv",
                )
            }
        ),
        ScargoOutput(
            artifacts={
                "txt-out": FileOutput(root=mount_point, path="testing/scargo-examples/output", name="output.txt")
            }
        ),
    )
    expected = (
        "cat ~/s3-data/testing/scargo-examples/input.csv | "
        "cut -d ',' -f 1 ~/s3-data/testing/scargo-examples/output/output.txt"
    )
    assert "".join(result) == expected
