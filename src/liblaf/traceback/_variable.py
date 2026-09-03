"""One-time optional adapter for rendering captured local variables."""

from __future__ import annotations

import importlib
import pprint
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from rich.console import RenderableType
from rich.text import Text

type VariableFormatter = Callable[[Any], RenderableType | str]
type FrameFormatter = Callable[
    [Sequence[Mapping[str, Any]]], tuple[tuple[str, ...], ...]
]


def _resolve_default_formatter() -> VariableFormatter:
    """Resolve the optional pretty-printer once at module import time."""
    try:
        module = importlib.import_module("liblaf.pprint")
    except ModuleNotFoundError as error:
        if error.name != "liblaf.pprint":
            raise
        return pprint.pformat
    return module.pretty


def _resolve_default_frame_formatter() -> FrameFormatter | None:
    """Resolve the optional sibling's shared frame-formatting pass."""
    try:
        module = importlib.import_module("liblaf.pprint")
    except ModuleNotFoundError as error:
        if error.name != "liblaf.pprint":
            raise
        return None
    return module.format_frame_variables


_default_formatter = _resolve_default_formatter()
_default_frame_formatter = _resolve_default_frame_formatter()


class _FormatterState:
    def __init__(
        self,
        formatter: VariableFormatter,
        frame_formatter: FrameFormatter | None,
    ) -> None:
        # A function stored on the class becomes a bound method when retrieved
        # through the state instance. Keep it on the instance so ``value`` is
        # passed to the formatter's first argument, not its ``indent`` slot.
        self.formatter = formatter
        self.frame_formatter = frame_formatter


_state = _FormatterState(_default_formatter, _default_frame_formatter)


def configure_variable_formatter(formatter: VariableFormatter | None) -> None:
    """Set the formatter used for individual local values.

    Args:
        formatter: Callable accepting a local value, or `None` to restore the
            optional default formatter and frame-batch support.
    """
    if formatter is None:
        _state.formatter = _default_formatter
        _state.frame_formatter = _default_frame_formatter
    else:
        _state.formatter = formatter
        _state.frame_formatter = None


def render_variable(value: Any) -> RenderableType:
    """Format one local with the configured formatter."""
    rendered = _state.formatter(value)
    return Text(rendered) if isinstance(rendered, str) else rendered


def render_frame_variables(
    frames: Sequence[Mapping[str, Any]],
) -> tuple[tuple[RenderableType, ...], ...]:
    """Render frame locals together when the active adapter supports it."""
    if _state.frame_formatter is None:
        return tuple(
            tuple(render_variable(value) for value in variables.values())
            for variables in frames
        )

    lines = _state.frame_formatter(frames)
    if len(lines) != len(frames):
        message = "frame formatter returned the wrong number of frames"
        raise ValueError(message)
    rendered_frames: list[tuple[RenderableType, ...]] = []
    for variables, frame_lines in zip(frames, lines, strict=True):
        if len(frame_lines) != len(variables):
            message = "frame formatter returned the wrong number of variables"
            raise ValueError(message)
        rendered: list[RenderableType] = []
        for name, line in zip(variables, frame_lines, strict=True):
            prefix = f"{name} = "
            if not line.startswith(prefix):
                message = f"frame formatter omitted the {name!r} variable prefix"
                raise ValueError(message)
            rendered.append(Text(line.removeprefix(prefix)))
        rendered_frames.append(tuple(rendered))
    return tuple(rendered_frames)
