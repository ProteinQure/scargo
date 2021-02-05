# Scargo by Example

This folder contains examples of Scargo workflows. This document, which assumes surface level familiarity with Argo Workflows, is a Scargo workflow tutorial based on these examples.

## Running the examples

Let's start by looking at `python_step/`, since it's the simplest example.

- The workflow can be run locally with `env SCARGO_LOCAL_MOUNT=$(pwd) python python_step.py`
- The transpiled result can be run with `argo submit python_step.yaml -f params.yaml`

# Structure of examples

All examples follow the same structure/flow to accomplish their specific task noted in the docstring at the top of the Python file.

## Setup MountPoints and WorkflowParameters

Every Scargo workflow needs both `MountPoints` and `WorkflowParameters`.

As mentioned in their docstring, `WorkflowParameters` are immutable parameters which can used across all steps of a workflow. In `python_step/` and other examples, they are used to define input values which are intended to be overwritten by users using `-f params.yaml` for the transpiled workflow.

`MountPoints` are maps between local filesystems and remote storage. This enables switching back and forth between running a workflow locally with Python and running a transpiled workflow on the cluster. Multiple `MountPoint` are possible, for example if a different mount-point is needed for input and output, but this feature is not demonstrated in the examples.

Currently, files in a `MountPoint` still need to be synced manually with `aws s3 sync`. Ideally, a tool should exist to sync files between local filesystem and remote storage.

The `WorkflowParameter` and `MountPoints` instances can be assigned to any variable, as long as they are used as described in the next section.

## Execute @entrypoint

The Scargo transpiler starts with the function marked by the `@entrypoint` decorator.

For Python, using this starting point is enabled by the lines:
```python
if __name__ == "__main__":
    main(mount_points, workflow_parameters)
```

However, this `if __name__ == "__main__"` block is ignored by the Scargo Transpiler.

Argo-level flow control is written inside this `@entrypoint`. Specifically,

- Assembling inputs (`ScargoInput`) and outputs (`ScargoOutput`) to be used by and passed between `@scargo` decorated functions called from the `@entrypoint` function.
- Conditionals and iterators (`iter_csv` in the `csv_iter` examples)

## Run @scargo functions

A function marked by `@scargo` are run as normal Python function, both locally and in the Argo workflow. For a function to be transpilable, it can only take the arguments:

1. `ScargoInput`
2. `ScargoOutput`

The parameters can be named anything, but they must be of this type.

Furthermore, all file I/O must be managed through `ScargoInput` and `ScargoOutput`, to keep the function compatible with Argo.
