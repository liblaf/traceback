"""The deep rendering module behind the public traceback interface."""

from __future__ import annotations

import io
import linecache
import os
import site
import sys
import sysconfig
import types
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import metadata
from pathlib import Path
from typing import Any, cast

from packaging.version import InvalidVersion, Version
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from ._config import config
from ._variable import render_frame_variables

_REDACTED = "<redacted>"
_TRUNCATED = "<truncated>"
_REDACTION_MAX_DEPTH = 4
_REDACTION_MAX_ITEMS = 100
_SECRET_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
)


@dataclass(frozen=True, slots=True)
class TracebackOptions:
    """Options governing exception rendering.

    `source` comes from the existing `linecache` entry. The renderer never
    refreshes it, so a file changed after execution may be stale and a missing
    cache entry is explicitly shown as unavailable.

    Attributes:
        limit: Number of frames to retain, using standard traceback semantics.
        hide_stable_release: Abbreviate frames from stable installed releases.
        capture_locals: Include visible local variables.
        locals_hide_sunder: Hide names beginning with one underscore.
        locals_hide_dunder: Hide names beginning with two underscores.
        suppress: Filename or module-name prefixes to abbreviate.
    """

    limit: int | None = None
    hide_stable_release: bool | None = None
    capture_locals: bool | None = None
    locals_hide_sunder: bool | None = None
    locals_hide_dunder: bool | None = None
    suppress: Sequence[str] | None = None

    def resolved(self) -> ResolvedTracebackOptions:
        """Return concrete values using the current configuration defaults."""
        return ResolvedTracebackOptions(
            limit=config.limit.get() if self.limit is None else self.limit,
            hide_stable_release=config.hide_stable_release.get()
            if self.hide_stable_release is None
            else self.hide_stable_release,
            capture_locals=config.capture_locals.get()
            if self.capture_locals is None
            else self.capture_locals,
            locals_hide_sunder=config.locals_hide_sunder.get()
            if self.locals_hide_sunder is None
            else self.locals_hide_sunder,
            locals_hide_dunder=config.locals_hide_dunder.get()
            if self.locals_hide_dunder is None
            else self.locals_hide_dunder,
            suppress=tuple(
                config.suppress.get() if self.suppress is None else self.suppress
            ),
        )


@dataclass(frozen=True, slots=True)
class ResolvedTracebackOptions:
    limit: int
    hide_stable_release: bool
    capture_locals: bool
    locals_hide_sunder: bool
    locals_hide_dunder: bool
    suppress: tuple[str, ...]


class ExceptionRenderer:
    """A Rich renderable representation of one exception and its relations.

    Attributes:
        exception: Exception to present.
        traceback: Traceback to use instead of `exception.__traceback__`.
        options: Optional rendering policy. Unspecified values use [`config`][liblaf.traceback.config].
    """

    def __init__(
        self,
        exception: BaseException,
        *,
        traceback: types.TracebackType | None = None,
        options: TracebackOptions | None = None,
    ) -> None:
        self.exception = exception
        self.traceback = exception.__traceback__ if traceback is None else traceback
        self.options = (options or TracebackOptions()).resolved()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        yield from self._render_exception(self.exception, self.traceback, set())

    def _render_exception(
        self, exception: BaseException, tb: types.TracebackType | None, seen: set[int]
    ) -> Iterator[RenderableType]:
        if id(exception) in seen:
            yield Text("<exception cycle omitted>", style="dim")
            return
        seen.add(id(exception))
        if exception.__cause__ is not None:
            yield from self._render_exception(
                exception.__cause__, exception.__cause__.__traceback__, seen
            )
            yield Text(
                "The above exception was the direct cause of the following exception:",
                style="italic",
            )
        elif exception.__context__ is not None and not exception.__suppress_context__:
            yield from self._render_exception(
                exception.__context__, exception.__context__.__traceback__, seen
            )
            yield Text(
                "During handling of the above exception, another exception occurred:",
                style="italic",
            )
        yield from self._render_stack(tb)
        yield _exception_text(exception)
        for note in getattr(exception, "__notes__", ()):
            yield Text(f"[NOTE] {note}", style="traceback.note")
        if isinstance(exception, BaseExceptionGroup):
            for index, child in enumerate(exception.exceptions, start=1):
                yield Panel(
                    Group(*self._render_exception(child, child.__traceback__, seen)),
                    title=f"Sub-exception #{index}",
                    border_style="traceback.group.border",
                )

    def _render_stack(self, tb: types.TracebackType | None) -> Iterator[RenderableType]:
        frames = list(_frames(tb, self.options.limit))
        if not frames:
            return
        hidden = [_hidden(frame, self.options) for frame, _lineno, _lasti in frames]
        redaction_memo: dict[int, Any] = {}
        local_values = [
            _visible_local_values(frame, self.options, redaction_memo)
            if self.options.capture_locals and not is_hidden
            else {}
            for (frame, _lineno, _lasti), is_hidden in zip(frames, hidden, strict=True)
        ]
        rendered_locals = (
            render_frame_variables(local_values)
            if self.options.capture_locals
            else ((),) * len(frames)
        )
        rendered: list[RenderableType] = []
        for index, ((frame, lineno, lasti), is_hidden, frame_locals) in enumerate(
            zip(frames, hidden, rendered_locals, strict=True)
        ):
            if is_hidden:
                rendered.append(_hidden_frame(frame, lineno))
            else:
                rendered.extend(
                    _visible_frame(
                        frame,
                        lineno,
                        lasti,
                        self.options,
                        dict(zip(local_values[index], frame_locals, strict=True)),
                    )
                )
        yield Panel(
            Group(*rendered),
            title=Text.assemble("Traceback ", ("(most recent call last)", "dim")),
            border_style="traceback.border",
            expand=False,
        )


def render_exception(
    exception: BaseException,
    /,
    *,
    traceback: types.TracebackType | None = None,
    **options: Any,
) -> ExceptionRenderer:
    """Build a Rich renderable for `exception`.

    Args:
        exception: Exception to render.
        traceback: Optional traceback override.
        **options: Fields accepted by [`TracebackOptions`][liblaf.traceback.TracebackOptions].

    Returns:
        A renderable accepted by `rich.console.Console.print`.
    """
    return ExceptionRenderer(
        exception, traceback=traceback, options=TracebackOptions(**options)
    )


def format_exception(
    exception: BaseException,
    /,
    *,
    traceback: types.TracebackType | None = None,
    **options: Any,
) -> str:
    """Return terminal-independent plain text for `exception`.

    Args:
        exception: Exception to render.
        traceback: Optional traceback override.
        **options: Fields accepted by [`TracebackOptions`][liblaf.traceback.TracebackOptions].

    Returns:
        Captured text without terminal colour escapes.

    Examples:
        >>> "RuntimeError: boom" in format_exception(
        ...     RuntimeError("boom"), capture_locals=False
        ... )
        True
    """
    output = io.StringIO()
    console = Console(
        file=output,
        force_terminal=False,
        width=100,
        color_system=None,
    )
    console.print(render_exception(exception, traceback=traceback, **options))
    return output.getvalue()


def print_exception(
    exception: BaseException | None = None,
    /,
    *,
    console: Console | None = None,
    **options: Any,
) -> None:
    """Print an active or explicit exception using the Rich renderer.

    Args:
        exception: Explicit exception. When omitted, uses `sys.exception()`.
        console: Rich console to receive the rendering.
        **options: Fields accepted by [`TracebackOptions`][liblaf.traceback.TracebackOptions].

    Raises:
        RuntimeError: If there is no active exception and none is supplied.
    """
    exception = sys.exception() if exception is None else exception
    if exception is None:
        message = "print_exception() requires an active or explicit exception"
        raise RuntimeError(message)
    (console or Console(stderr=True)).print(render_exception(exception, **options))


def _frames(
    tb: types.TracebackType | None, limit: int
) -> Iterable[tuple[types.FrameType, int, int]]:
    items: list[tuple[types.FrameType, int, int]] = []
    while tb is not None:
        items.append((tb.tb_frame, tb.tb_lineno, tb.tb_lasti))
        tb = tb.tb_next
    if limit == 0:
        return ()
    if limit < 0:
        return items[limit:]
    return items[-limit:]


def _hidden(frame: types.FrameType, options: ResolvedTracebackOptions) -> bool:
    if bool(frame.f_locals.get("__tracebackhide__", False)):
        return True
    filename = str(Path(frame.f_code.co_filename).resolve())
    module = str(frame.f_globals.get("__name__", ""))
    prefixes = tuple(item.rstrip(".") for item in options.suppress)
    if any(
        filename.startswith(prefix)
        or module == prefix
        or module.startswith(f"{prefix}.")
        for prefix in prefixes
    ):
        return True
    return (
        options.hide_stable_release
        and module != "__main__"
        and _stable_release(filename, module)
    )


def _hidden_frame(frame: types.FrameType, lineno: int) -> Text:
    return Text(
        f"{_display_path(frame.f_code.co_filename)}:{lineno} in {frame.f_code.co_qualname}() — hidden",
        style="dim",
    )


def _visible_frame(
    frame: types.FrameType,
    lineno: int,
    _lasti: int,
    options: ResolvedTracebackOptions,
    rendered_locals: dict[str, RenderableType],
) -> list[RenderableType]:
    result: list[RenderableType] = [
        Text.assemble(
            (_display_path(frame.f_code.co_filename), "cyan"),
            ":",
            (str(lineno), "yellow"),
            " in ",
            (frame.f_code.co_qualname + "()", "bold"),
        )
    ]
    # ``linecache.getlines`` repopulates an absent cache entry from disk. A
    # traceback cannot in general recover the source that executed after an
    # edit, so only use text Python had already cached.
    entry = cast(
        "tuple[Any, ...] | None", linecache.cache.get(frame.f_code.co_filename)
    )
    source = (
        entry[2]
        if entry is not None and len(entry) > 2 and isinstance(entry[2], list)
        else []
    )
    if source:
        code = "".join(source)
        start_line, end_line = _source_range(frame.f_code, _lasti, lineno)
        result.append(
            Syntax(
                code,
                Syntax.guess_lexer(frame.f_code.co_filename, code),
                line_numbers=True,
                line_range=(start_line, end_line),
                word_wrap=True,
            )
        )
    else:
        result.append(Text("source unavailable (no cached source)", style="dim"))
    if options.capture_locals:
        table = _locals_table(frame, options, rendered_locals)
        if table is not None:
            result.append(table)
    return result


def _locals_table(
    frame: types.FrameType,
    options: ResolvedTracebackOptions,
    rendered_locals: dict[str, RenderableType],
) -> Table | None:
    rows = []
    for name in frame.f_locals:
        if options.locals_hide_dunder and name.startswith("__"):
            continue
        if (
            options.locals_hide_sunder
            and name.startswith("_")
            and not name.startswith("__")
        ):
            continue
        rendered: RenderableType = (
            Text(_REDACTED, style="red") if _secret(name) else rendered_locals[name]
        )
        rows.append((name, rendered))
    if not rows:
        return None
    table = Table(title="locals", show_header=False, box=None, padding=(0, 1))
    table.add_column(style="cyan")
    table.add_column(overflow="fold")
    for name, rendered in rows:
        table.add_row(name, rendered)
    return table


def _visible_local_values(
    frame: types.FrameType,
    options: ResolvedTracebackOptions,
    redaction_memo: dict[int, Any],
) -> dict[str, Any]:
    return {
        name: _redact_value(value, memo=redaction_memo)
        for name, value in frame.f_locals.items()
        if not _secret(name)
        and not (options.locals_hide_dunder and name.startswith("__"))
        and not (
            options.locals_hide_sunder
            and name.startswith("_")
            and not name.startswith("__")
        )
    }


def _secret(name: str) -> bool:
    lowered = name.lower().replace("-", "_")
    return any(marker in lowered for marker in _SECRET_MARKERS)


def _redact_value(
    value: Any,
    *,
    depth: int = 0,
    memo: dict[int, Any] | None = None,
) -> Any:
    """Redact named secrets in bounded built-in containers.

    This deliberately only traverses exact built-in container types. Traversing
    arbitrary mappings or objects could execute application code while an
    exception is already being handled. Set ``capture_locals=False`` when even
    non-container values may be sensitive.
    """
    if memo is None:
        memo = {}
    if depth >= _REDACTION_MAX_DEPTH:
        return _TRUNCATED
    identifier = id(value)
    if identifier in memo:
        return memo[identifier]
    if type(value) is dict:
        redacted = _redact_dict(value, depth=depth, memo=memo)
    elif type(value) is list:
        redacted = _redact_list(value, depth=depth, memo=memo)
    elif type(value) is tuple:
        redacted = _redact_tuple(value, depth=depth, memo=memo)
    elif type(value) is set or type(value) is frozenset:
        redacted = _redact_set(value, depth=depth, memo=memo)
    else:
        redacted = value
    return redacted


def _redact_dict(
    value: dict[Any, Any], *, depth: int, memo: dict[int, Any]
) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    memo[id(value)] = result
    changed = False
    for index, (key, item) in enumerate(value.items()):
        if index >= _REDACTION_MAX_ITEMS:
            result[_TRUNCATED] = _TRUNCATED
            changed = True
            break
        if isinstance(key, str) and _secret(key):
            result[key] = _REDACTED
            changed = True
            continue
        redacted = _redact_value(item, depth=depth + 1, memo=memo)
        result[key] = redacted
        changed |= redacted is not item
    memo[id(value)] = result if changed else value
    return memo[id(value)]


def _redact_list(value: list[Any], *, depth: int, memo: dict[int, Any]) -> list[Any]:
    result: list[Any] = []
    memo[id(value)] = result
    items = value[:_REDACTION_MAX_ITEMS]
    changed = len(items) != len(value)
    for item in items:
        redacted = _redact_value(item, depth=depth + 1, memo=memo)
        result.append(redacted)
        changed |= redacted is not item
    if len(value) > _REDACTION_MAX_ITEMS:
        result.append(_TRUNCATED)
    memo[id(value)] = result if changed else value
    return memo[id(value)]


def _redact_tuple(
    value: tuple[Any, ...], *, depth: int, memo: dict[int, Any]
) -> tuple[Any, ...]:
    memo[id(value)] = _TRUNCATED
    items = value[:_REDACTION_MAX_ITEMS]
    redacted_items = tuple(
        _redact_value(item, depth=depth + 1, memo=memo) for item in items
    )
    changed = len(items) != len(value) or any(
        redacted is not item
        for item, redacted in zip(items, redacted_items, strict=True)
    )
    result = redacted_items + (
        (_TRUNCATED,) if len(value) > _REDACTION_MAX_ITEMS else ()
    )
    memo[id(value)] = result if changed else value
    return memo[id(value)]


def _redact_set(
    value: set[Any] | frozenset[Any], *, depth: int, memo: dict[int, Any]
) -> set[Any] | frozenset[Any]:
    memo[id(value)] = _TRUNCATED
    items = list(value)[:_REDACTION_MAX_ITEMS]
    redacted_items = [_redact_value(item, depth=depth + 1, memo=memo) for item in items]
    changed = len(items) != len(value) or any(
        redacted is not item
        for item, redacted in zip(items, redacted_items, strict=True)
    )
    redacted = set(redacted_items)
    if len(value) > _REDACTION_MAX_ITEMS:
        redacted.add(_TRUNCATED)
    result = type(value)(redacted)
    memo[id(value)] = result if changed else value
    return memo[id(value)]


def _display_path(filename: str) -> str:
    try:
        return os.path.relpath(filename)
    except ValueError:
        return filename


def _source_range(code: types.CodeType, lasti: int, fallback: int) -> tuple[int, int]:
    """Return the full source-statement range recorded in bytecode positions."""
    if lasti < 0:
        return fallback, fallback
    try:
        start, end, _start_col, _end_col = tuple(code.co_positions())[lasti // 2]
    except (IndexError, ValueError):
        return fallback, fallback
    return start or fallback, end or start or fallback


@cache
def _stable_release(filename: str, module: str) -> bool:
    """Return whether a frame belongs to an installed stable distribution."""
    roots = [*site.getsitepackages(), site.getusersitepackages()]
    for key in ("purelib", "platlib"):
        path = sysconfig.get_path(key)
        if path is not None:
            roots.append(path)
    resolved = Path(filename).resolve()
    if not any(
        str(resolved).startswith(str(Path(root).resolve()) + os.sep) for root in roots
    ):
        return False

    package = module.partition(".")[0]
    for distribution_name in metadata.packages_distributions().get(package, ()):
        try:
            distribution = metadata.distribution(distribution_name)
        except metadata.PackageNotFoundError:
            continue
        files = distribution.files
        if files is None or not any(
            Path(str(distribution.locate_file(file))).resolve() == resolved
            for file in files
        ):
            continue
        try:
            version = Version(distribution.version)
        except InvalidVersion:
            return False
        return not version.is_prerelease and not version.is_devrelease
    return False


def _exception_text(exception: BaseException) -> Text:
    name = type(exception).__qualname__
    if type(exception).__module__ not in {"builtins", "__main__"}:
        name = f"{type(exception).__module__}.{name}"
    message = str(exception)
    if isinstance(exception, SyntaxError) and exception.filename:
        location = f" ({exception.filename}:{exception.lineno})"
    else:
        location = ""
    return Text(
        f"{name}{location}: {message}" if message else name + location,
        style="traceback.exc_type",
    )
