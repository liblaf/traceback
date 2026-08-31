"""Opt-in installation of the process exception hook."""

from __future__ import annotations

import sys
import types
from collections.abc import Callable
from typing import Any, cast

from rich.console import Console

from ._format import print_exception

type ExceptHook = Callable[
    [type[BaseException], BaseException, types.TracebackType | None], None
]


class _HookState:
    previous_hook: ExceptHook = cast("ExceptHook", sys.__excepthook__)
    installed_hook: ExceptHook | None = None
    installed = False


_state = _HookState()


def install(*, console: Console | None = None) -> None:
    """Install an idempotent `sys.excepthook` for uncaught exceptions.

    Args:
        console: Optional Rich console used by the installed hook.

    The hook is restored by [`uninstall`][liblaf.traceback.uninstall] only when
    this package still owns `sys.excepthook`.
    """
    if _state.installed:
        if sys.excepthook is _state.installed_hook:
            return
        # Another owner replaced our hook. It is now the active baseline; do
        # not retain stale ownership state or restore an unrelated hook later.
        _state.installed = False
        _state.installed_hook = None
    _state.previous_hook = cast("ExceptHook", sys.excepthook)

    def excepthook(
        _exc_type: type[BaseException],
        exc_value: BaseException,
        tb: types.TracebackType | None,
    ) -> None:
        print_exception(exc_value, console=console, traceback=tb)

    sys.excepthook = cast("Any", excepthook)
    _state.installed_hook = excepthook
    _state.installed = True


def uninstall() -> None:
    """Restore the hook active before [`install`][liblaf.traceback.install].

    A hook installed by another owner after `install()` is left untouched.
    """
    if _state.installed:
        if sys.excepthook is _state.installed_hook:
            sys.excepthook = cast("Any", _state.previous_hook)
        _state.installed_hook = None
        _state.installed = False
