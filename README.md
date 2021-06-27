# Scargo

Scargo is Argo for Scientific Workflows.

## Table of content

- [Description](#description)
- [Features](#features)
- [Core](#core)
- [Support](#support)
- [Non-goals](#non-goals)
- [Installation](#installation)
- [Testing](#testing)

## Description

A Scientific Workflow is a single-use workflow which takes statically defined inputs and outputs results. This is simpler than the CI/CD and event-driven workflows which Argo implements.

This reduced scope allows Scargo to be implemented as a subset of Python which is compiled to Argo YAML. Using Python instead of YAML also provides additional benefits, such as as:

- Access to Python tooling, such as linting, auto-formatting and auto-completion
- Less nesting and more brevity than YAML
- Easier testing
- Improved modularity

Using Scargo, scientists should be able to prototype and modify simple sequential Argo workflows without engineering intervention. 

## Features

Almost all of these features have not been implemented yet. See `examples/` for practical demonstrations of features.

### Core

- Run Python functions locally and allow for unit testing before bundling in Argo
- Run Bash scripts defined outside of the main script
- Define global parameters such they can separated out in the compiled Argo workflow
- Import common Argo functionality (iterating through a CSV, iterating through all files in an S3 folder)
- Manage artifacts and parameters for individual steps with minimal boilerplate
- Provide a YAML escape hatch
    - Allows for quickly implementing weird corner cases, such as adding volume mounts (MOE licenses), retry strategies and environment variables (MongoDB)

### Support

- Adding Python-only dependencies to a Docker Image. All other dependencies that are not pip-installable will require research-engineer intervention.
- Running a workflow locally in the same environment as it would run in the cloud.
- A user wants to specify resource requirements for each workflow step/Python function
- Automate switching between local root and S3 root

## Non-Goals

Complete implementation of the Argo API, including:

- Recursion
- Artifacts from anywhere other than S3 and Minio

## Installation

We rely on [`invoke`](http://www.pyinvoke.org/) to install our project code with Poetry.

You can install the `scargo` project in development mode by running:
```bash
inv install
```

## Testing

Running the full test suite is as easy as running:
```bash
inv test
```

If you're interested in the code coverage of this repo you may run:
```bash
inv test --coverage --html-report
```
and inspect the resulting interactive HTML report by opening the `index.html` in the `htmlcov/` folder in your favourite browser.
