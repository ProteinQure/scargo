import ast

import pytest

from scargo.transpile.transformer import SourceToArgoTransformer
from scargo.transpile.types import FilePut, FileTmp


@pytest.mark.parametrize("path_value, ext", [("add_alpha_", ".txt"), ("add_beta_", ".csv")])
def test_resolve_string(path_value, ext):
    """
    Testing if a JoinedStr node representing an f-string is correctly resolved
    by the SourceToArgoTransformer.
    """
    node = ast.JoinedStr(
        values=[
            ast.Constant(value=path_value, kind=None),
            ast.FormattedValue(
                value=ast.Constant(value="{{inputs.parameters.init-value}}", kind=None),
                conversion=-1,
                format_spec=None,
            ),
            ast.Constant(value=ext, kind=None),
        ],
    )

    assert SourceToArgoTransformer._resolve_string(node) == "%s{{inputs.parameters.init-value}}%s" % (path_value, ext)


def test_resolve_subscript():
    """
    Testing if a Subscript node is correctly resolved
    by the SourceToArgoTransformer.
    """
    node = ast.Subscript(
        value=ast.Attribute(
            value=ast.Name(id="scargo_in"),
            attr="parameters",
        ),
        slice=ast.Index(
            value=ast.Constant(value="init-value", kind=None),
        ),
    )

    assert (
        SourceToArgoTransformer._resolve_subscript(node, input_arg="scargo_in", output_arg="scargo_out")
        == r"{{inputs.parameters.init-value}}"
    )


@pytest.mark.parametrize(
    "call_val, args, keywords, inputs, outputs, exp_path, exp_mode",
    [
        # input with arg mode
        (
            "{{inputs.artifacts.csv-file.path}}",
            [ast.Constant(value="r", kind=None)],
            [],
            {"csv-file": FilePut(root="{{workflow.parameters.s3-bucket}}", path="{{workflow.parameters.input-path}}")},
            None,
            "{{inputs.artifacts.csv-file.path}}",
            "r",
        ),
        # input with keyword mode
        (
            "{{inputs.artifacts.csv-file.path}}",
            [],
            [
                ast.keyword(
                    arg="mode",
                    value=ast.Constant(value="r", kind=None),
                ),
            ],
            {"csv-file": FilePut(root="{{workflow.parameters.s3-bucket}}", path="{{workflow.parameters.input-path}}")},
            None,
            "{{inputs.artifacts.csv-file.path}}",
            "r",
        ),
        # tmp output with arg mode
        (
            "{{outputs.artifacts.out-file.path}}",
            [ast.Constant(value="w+", kind=None)],
            [],
            None,
            {"out-file": FileTmp(path="out-file.txt")},
            "{{outputs.artifacts.out-file.path}}",
            "w+",
        ),
        # tmp output with keyword mode
        (
            "{{outputs.artifacts.out-file.path}}",
            [],
            [
                ast.keyword(
                    arg="mode",
                    value=ast.Constant(value="w+", kind=None),
                ),
            ],
            None,
            {"out-file": FileTmp(path="out-file.txt")},
            "{{outputs.artifacts.out-file.path}}",
            "w+",
        ),
        # output with arg path and mode
        (
            "{{outputs.artifacts.txt-out.path}}",
            [
                ast.JoinedStr(
                    values=[
                        ast.Constant(value="add_multi_", kind=None),
                        ast.FormattedValue(
                            value=ast.Constant(value="{{inputs.parameters.init-value}}", kind=None),
                            conversion=-1,
                            format_spec=None,
                        ),
                        ast.Constant(value=".txt", kind=None),
                    ],
                ),
                ast.Constant(value="w+", kind=None),
            ],
            [],
            None,
            {"txt-out": FilePut(root="{{workflow.parameters.s3-bucket}}", path="{{workflow.parameters.output-path}}")},
            "{{outputs.artifacts.txt-out.path}}/add_multi_{{inputs.parameters.init-value}}.txt",
            "w+",
        ),
        # output with arg path and keyword mode
        (
            "{{outputs.artifacts.txt-out.path}}",
            [
                ast.JoinedStr(
                    values=[
                        ast.Constant(value="add_multi_", kind=None),
                        ast.FormattedValue(
                            value=ast.Constant(value="{{inputs.parameters.init-value}}", kind=None),
                            conversion=-1,
                            format_spec=None,
                        ),
                        ast.Constant(value=".txt", kind=None),
                    ],
                ),
            ],
            [
                ast.keyword(
                    arg="mode",
                    value=ast.Constant(value="w+", kind=None),
                )
            ],
            None,
            {"txt-out": FilePut(root="{{workflow.parameters.s3-bucket}}", path="{{workflow.parameters.output-path}}")},
            "{{outputs.artifacts.txt-out.path}}/add_multi_{{inputs.parameters.init-value}}.txt",
            "w+",
        ),
        # output with keyword path and modes
        (
            "{{outputs.artifacts.txt-out.path}}",
            [],
            [
                ast.keyword(
                    arg="file_name",
                    value=ast.JoinedStr(
                        values=[
                            ast.Constant(value="add_multi_", kind=None),
                            ast.FormattedValue(
                                value=ast.Constant(value="{{inputs.parameters.init-value}}", kind=None),
                                conversion=-1,
                                format_spec=None,
                            ),
                            ast.Constant(value=".txt", kind=None),
                        ],
                    ),
                ),
                ast.keyword(
                    arg="mode",
                    value=ast.Constant(value="w+", kind=None),
                ),
            ],
            None,
            {"txt-out": FilePut(root="{{workflow.parameters.s3-bucket}}", path="{{workflow.parameters.output-path}}")},
            "{{outputs.artifacts.txt-out.path}}/add_multi_{{inputs.parameters.init-value}}.txt",
            "w+",
        ),
    ],
)
def test_resolve_open_with_args(call_val, args, keywords, inputs, outputs, exp_path, exp_mode):
    """
    Given TmpTransput can act as both an input and an output.
    """

    node = ast.Call(
        func=ast.Attribute(
            value=ast.Constant(value=call_val, kind=None),
            attr="open",
        ),
        args=args,
        keywords=keywords,
    )
    res = SourceToArgoTransformer._resolve_open(node, inputs=inputs, outputs=outputs)
    assert len(res.args) == 2

    full_path = res.args[0]
    assert isinstance(full_path, ast.Constant)
    assert full_path.value == exp_path

    mode = res.args[1]
    assert isinstance(mode, ast.Constant)
    assert mode.value == exp_mode
