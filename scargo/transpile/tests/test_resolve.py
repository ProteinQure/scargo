import ast
from pathlib import Path

import pytest

from scargo.core import MountPoint, MountPoints, WorkflowParams
from scargo.transpile import resolve
from scargo.transpile.types import Context, FilePut, FileTmp, Origin, Parameter, Transput


@pytest.mark.parametrize(
    "node, locals_context, expected",
    [
        (
            ast.Subscript(
                value=ast.Name(id="workflow_parameters", ctx=ast.Load()),
                slice=ast.Constant(value="word-index"),
                ctx=ast.Load(),
            ),
            {"workflow_parameters": WorkflowParams({"word-index": "1"})},
            "{{workflow.parameters.word-index}}",
        )
    ],
)
def test_resolve_workflow_param(node, locals_context, expected):
    assert resolve.resolve_workflow_param(node, locals_context) == expected


@pytest.mark.parametrize(
    "raw_params, context, expected",
    [
        # single temporary file output
        (
            ast.Dict(
                keys=[ast.Constant(value="out-file")],
                values=[
                    ast.Call(func=ast.Name(id="TmpTransput"), args=[ast.Constant(value="out-file.txt")], keywords=[])
                ],
            ),
            Context(locals={}, inputs={}, outputs={}, workflow_params=WorkflowParams({}), mount_points={}),
            {"out-file": FileTmp(path="out-file.txt", origin=None)},
        ),
        # single file output
        (
            ast.Dict(
                keys=[ast.Constant(value="csv-file")],
                values=[
                    ast.Call(
                        func=ast.Name(id="FileInput"),
                        args=[],
                        keywords=[
                            ast.keyword(
                                arg="root",
                                value=ast.Subscript(
                                    value=ast.Name(id="mount_points"),
                                    slice=ast.Constant(value="root"),
                                ),
                            ),
                            ast.keyword(
                                arg="path",
                                value=ast.Subscript(
                                    value=ast.Name(id="workflow_parameters"),
                                    slice=ast.Constant(value="input-path"),
                                ),
                            ),
                            ast.keyword(
                                arg="name",
                                value=ast.Subscript(
                                    value=ast.Name(id="workflow_parameters"),
                                    slice=ast.Constant(value="input-csv"),
                                ),
                            ),
                        ],
                    )
                ],
            ),
            Context(
                locals={
                    "workflow_parameters": WorkflowParams(
                        {"input-path": "testing/scargo-examples", "input-csv": "add_alpha.csv"}
                    ),
                    "mount_points": MountPoints(
                        {"root": MountPoint(local=Path("/some/path"), remote="pq-dataxfer-tmp")}
                    ),
                },
                inputs={},
                outputs={},
                workflow_params=WorkflowParams({"input-path": "testing/scargo-examples", "input-csv": "add_alpha.csv"}),
                mount_points={"root": "pq-dataxfer-tmp"},
            ),
            {
                "csv-file": FilePut(
                    root="pq-dataxfer-tmp", path="{{workflow.parameters.input-path}}/{{workflow.parameters.input-csv}}"
                )
            },
        ),
        # temporary file created in a previous step
        (
            ast.Dict(
                keys=[ast.Constant(value="init-file")],
                values=[
                    ast.Subscript(
                        value=ast.Attribute(
                            value=ast.Name(id="nth_word_out"),
                            attr="artifacts",
                        ),
                        slice=ast.Constant(value="out-file"),
                    )
                ],
            ),
            Context(
                locals={},
                inputs={},
                outputs={
                    "nth_word_out": Transput(
                        parameters=None,
                        artifacts={
                            "out-file": FileTmp(
                                path="out-file.txt", origin=Origin(step="get-nth-word", name="out-file")
                            )
                        },
                    )
                },
                workflow_params=WorkflowParams({}),
                mount_points={},
            ),
            {"init-file": FileTmp(path="out-file.txt", origin=Origin(step="get-nth-word", name="out-file"))},
        ),
    ],
)
def test_resolve_transput_artifacts(raw_params, context, expected):
    assert resolve.resolve_transput_artifacts(raw_params, context) == expected


@pytest.mark.parametrize(
    "raw_params, context, expected",
    [
        # single parameter without a value
        (
            ast.Dict(keys=[ast.Constant(value="out-val")], values=[ast.Constant(value=None)]),
            Context(locals={}, inputs={}, outputs={}, workflow_params=WorkflowParams({}), mount_points={}),
            {"out-val": Parameter(value=None, origin=None)},
        ),
        # multiple subscripts
        (
            ast.Dict(
                keys=[
                    ast.Constant(value="word-index"),
                    ast.Constant(value="pre-word"),
                    ast.Constant(value="post-word"),
                ],
                values=[
                    ast.Subscript(value=ast.Name(id="workflow_parameters"), slice=ast.Constant(value="word-index")),
                    ast.Subscript(value=ast.Name(id="workflow_parameters"), slice=ast.Constant(value="pre-word")),
                    ast.Subscript(value=ast.Name(id="workflow_parameters"), slice=ast.Constant(value="post-word")),
                ],
            ),
            Context(
                locals={
                    "workflow_parameters": WorkflowParams({"word-index": "1", "pre-word": "pre", "post-word": "post"})
                },
                inputs={},
                outputs={},
                workflow_params=WorkflowParams({"word-index": "1", "pre-word": "pre", "post-word": "post"}),
                mount_points={},
            ),
            {
                "word-index": Parameter(value="{{workflow.parameters.word-index}}", origin=None),
                "pre-word": Parameter(value="{{workflow.parameters.pre-word}}", origin=None),
                "post-word": Parameter(value="{{workflow.parameters.post-word}}", origin=None),
            },
        ),
        # resolve subscript assigned in a previous step
        (
            ast.Dict(
                keys=[ast.Constant(value="init-value")],
                values=[
                    ast.Subscript(
                        value=ast.Attribute(value=ast.Name(id="nth_word_out"), attr="parameters"),
                        slice=ast.Constant(value="out-val"),
                    )
                ],
            ),
            Context(
                locals={},
                inputs={},
                outputs={
                    "nth_word_out": Transput(
                        parameters={
                            "out-val": Parameter(value=None, origin=Origin(step="get-nth-word", name="out-val"))
                        },
                        artifacts=None,
                    )
                },
                workflow_params=WorkflowParams({}),
                mount_points={},
            ),
            {"init-value": Parameter(value=None, origin=Origin(step="get-nth-word", name="out-val"))},
        ),
    ],
)
def test_resolve_transput_parameters(raw_params, context, expected):
    assert resolve.resolve_transput_parameters(raw_params, context) == expected
