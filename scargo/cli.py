"""
The `scargo` command line interface.

Examples:
    Transpile the `python_step.py` script:
    $ scargo transpile examples/python_step/python_step.py

    Transpile & submit `python_step.py` as an Argo workflow:
    $ scargo submit examples/python_step/python_step.py

    Transpile & submit `python_step.py` as an Argo workflow and watch the progress in the shell:
    $ scargo submit examples/python_step/python_step.py --watch
"""

from pathlib import Path
import typer

from scargo.transpile import transpiler


app = typer.Typer()


@app.command()
def transpile(python_script: str):
    """
    Transpiles the `python_script` to Argo YAML by creating a workflow YAML
    file and a parameter YAML file in the user's current working directory.
    """
    typer.echo(f"This subcommand should transpile {python_script} to Argo YAML.")
    transpiler.transpile(Path.cwd() / python_script)


@app.command()
def submit(python_script: str, watch: bool = False):
    """
    Transpiles `python_script` by calling `transpile()` and then immediately
    submits it through the `argo` CLI without storing the transpiled Argo YAML
    files.
    """
    if watch:
        typer.echo((f"This subcommand should transpile & submit {python_script}" "by adding the --watch flag."))
    else:
        typer.echo(f"This subcommand should transpile & submit {python_script}")


def run():
    """
    Entrypoint for the CLI.
    """
    app()
