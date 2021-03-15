The Transpiler accomplishes the following steps:

## 1. Acquire MountPoints and WorkflowParameters

Parse the top-level functions and assignments to acquire the Mount Points and the Workflow Parameters. This process starts in `transpiler.transpile()`.

## 2. Parse the Entrypoint function

Find the function marked with `@entrypoint` and parse it's data structures. This is accomplished by `entrypoint.EntrypointTranspiler()`. All AST manipulation and transformation uses `ast` subclasses. In this case, `entrypoint.EntrypointTranspiler` is a subclass of `ast.NodeVisitor`.

## 2.1 Create WorkflowStep for @scargo functions

When a call to a function is encountered by `EntrypointTranspiler`, make sure it's marked with `@scargo` and transform it's source code to be Argo Compatible. This is accomplished by `EntrypointTranspiler` creating `WorkflowStep` instances using `make_workflow_step`.

## 2.2 Transform @scargo function source code

To transform the source code, an `ast.NodeTransformer` which transforms any access of Scargo Inputs and Outputs to use actual Argo inputs and outputs.

For example, writing to an output parameter in Scargo Python:
```python
scargo_out.parameters["out-val"] = word
```

Will be transpiled to:
```python
with open("{{outputs.parameters.out-val.path}}", "w+") as fi:
    fi.write(word)
```

## 3. Transpile data-structures to YAML

Given the data structures created from the previous steps, transpile them into Argo YAML.
