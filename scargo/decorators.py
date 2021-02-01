"""
Decorators that reduce the amount of boilerplate code required from the user
when writing Scargo scripts.
"""


def scargo(image):
    """
    A decorator factory taking a Docker `image` name as argument. Every Python
    function that should be compiled to Argo YAML needs to be decorated with
    the @scargo decorator.
    """

    def decorator(function):
        """
        This decorator wraps the decorated `function` with
        `run_python_function`.
        """

        def wrapped_function(scargo_inputs, scargo_outputs):
            function(scargo_inputs, scargo_outputs)

        return wrapped_function

    return decorator


def entrypoint(func):
    def decorator():
        return func()

    return decorator
