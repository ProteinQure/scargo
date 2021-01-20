"""
Definition of all invoke CLI commands for this project.
"""
from invoke import task


project_name = "scargo"


@task
def install(c):
    """
    Install all requirements and setup poetry environment.
    """
    c.run("poetry install")


@task
def check(c):
    """
    Runs all static checks, such as black, flake8 and pylint.
    """
    print("Black")
    c.run(f"black --line-length 120 {project_name}/")
    print("Style checks")
    c.run(f"flake8 {project_name}/")
    c.run(f"pylint {project_name}/ --rcfile=setup.cfg --output-format=colorized")

