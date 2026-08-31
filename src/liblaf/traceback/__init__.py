"""Render Python exceptions as text or Rich presentations.

Use [`format_exception`][liblaf.traceback.format_exception] for text suitable
for logs and files, and [`render_exception`][liblaf.traceback.render_exception]
with `Console.print` for terminal output.

Examples:
    >>> "ValueError: invalid" in format_exception(
    ...     ValueError("invalid"), capture_locals=False
    ... )
    True
"""

from ._config import Config, config
from ._format import (
    ExceptionRenderer,
    TracebackOptions,
    format_exception,
    print_exception,
    render_exception,
)
from ._install import install, uninstall
from ._variable import VariableFormatter, configure_variable_formatter
from ._version import __commit_id__, __version__, __version_tuple__

__all__ = [
    "Config",
    "ExceptionRenderer",
    "TracebackOptions",
    "VariableFormatter",
    "__commit_id__",
    "__version__",
    "__version_tuple__",
    "config",
    "configure_variable_formatter",
    "format_exception",
    "install",
    "print_exception",
    "render_exception",
    "uninstall",
]
