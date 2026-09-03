from __future__ import annotations

import inspect
import io
import linecache
import sys
import types
from importlib import metadata
from pathlib import Path
from typing import cast

import pytest
from rich.console import Console
from rich.text import Text

from liblaf import traceback
from liblaf.traceback import _format, _install, _variable


def _raise_with_locals() -> None:
    password = "do" + "-not-show"
    _private = "hidden"
    visible = 42
    details = password, _private
    assert details
    message = f"bad {visible}"
    raise ValueError(message)


def test_format_exception_is_text_redacts_locals_and_does_not_print(
    capsys: pytest.CaptureFixture[str],
) -> None:
    try:
        _raise_with_locals()
    except ValueError as error:
        formatted = traceback.format_exception(error)
    assert isinstance(formatted, str)
    assert "ValueError: bad 42" in formatted
    assert "<redacted>" in formatted
    assert "_private" not in formatted
    assert capsys.readouterr() == ("", "")


def test_default_formatter_renders_ordinary_locals() -> None:
    def raise_with_visible_local() -> None:
        visible = {"answer": 42}
        raise ValueError(visible)

    try:
        raise_with_visible_local()
    except ValueError as error:
        formatted = traceback.format_exception(error)

    assert "'answer': 42" in formatted


def test_nested_builtin_secrets_are_redacted() -> None:
    def raise_with_secret() -> None:
        config = {"nested": [{"api_token": "must-not-appear"}]}
        assert config
        raise ValueError("failed")

    try:
        raise_with_secret()
    except ValueError as error:
        formatted = traceback.format_exception(error)

    assert "must-not-appear" not in formatted
    assert "<redacted>" in formatted


def test_rich_renderer_handles_causes_notes_and_groups() -> None:
    def raise_group() -> None:
        def raise_key_error() -> None:
            raise KeyError("inner")

        try:
            raise_key_error()
        except KeyError as cause:
            error = ValueError("outer")
            error.add_note("diagnostic note")
            raise ExceptionGroup("many", [error, RuntimeError("second")]) from cause

    try:
        raise_group()
    except ExceptionGroup as group:
        rendered = traceback.render_exception(group)
    console = Console(file=io.StringIO(), width=100, force_terminal=False)
    with console.capture() as capture:
        console.print(rendered)
    result = capture.get()
    assert "direct cause" in result
    assert "diagnostic note" in result
    assert "Sub-exception #1" in result
    assert "RuntimeError: second" in result


def test_hidden_frame_is_dimmed_not_removed() -> None:
    def hidden() -> None:
        __tracebackhide__ = True
        raise RuntimeError("boom")

    try:
        hidden()
    except RuntimeError as error:
        formatted = traceback.format_exception(error)
    assert "hidden" in formatted
    assert "RuntimeError: boom" in formatted


def test_source_unavailable_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_missing() -> None:
        raise RuntimeError("missing")

    try:
        raise_missing()
    except RuntimeError as error:
        trace = cast("types.TracebackType", error.__traceback__)
        filename = trace.tb_frame.f_code.co_filename
        monkeypatch.delitem(linecache.cache, filename, raising=False)
        formatted = traceback.format_exception(error)
    assert "source unavailable" in formatted
    assert filename not in linecache.cache


@pytest.mark.parametrize(
    ("limit", "expected_frames"),
    [(0, 0), (1, 1), (-1, 1), (-2, 2)],
)
def test_limit_matches_stdlib_frame_semantics(limit: int, expected_frames: int) -> None:
    def outer() -> None:
        inner()

    def inner() -> None:
        raise RuntimeError("limited")

    try:
        outer()
    except RuntimeError as error:
        formatted = traceback.format_exception(error, limit=limit, capture_locals=False)

    assert formatted.count(" in ") == expected_frames


def test_custom_variable_formatter_and_hook_restore() -> None:
    def raise_custom() -> None:
        raise ValueError("custom")

    traceback.configure_variable_formatter(lambda value: f"value={value}")
    try:
        raise_custom()
    except ValueError as error:
        formatted = traceback.format_exception(error)
    assert "value=" in formatted
    traceback.configure_variable_formatter(None)

    previous = sys.excepthook
    traceback.install()
    traceback.install()
    traceback.uninstall()
    assert sys.excepthook is previous


def test_uninstall_preserves_a_replacement_exception_hook() -> None:
    previous = sys.excepthook

    def replacement(
        exc_type: type[BaseException],
        exc_value: BaseException,
        tb: object,
    ) -> None:
        del exc_type, exc_value, tb

    traceback.install()
    sys.excepthook = replacement
    traceback.uninstall()

    assert sys.excepthook is replacement
    sys.excepthook = previous


def test_install_uses_the_standard_exception_hook_signature() -> None:
    previous = sys.excepthook
    traceback.install()
    try:
        assert list(inspect.signature(sys.excepthook).parameters) == [
            "_exc_type",
            "exc_value",
            "tb",
        ]
    finally:
        traceback.uninstall()
    assert sys.excepthook is previous


def test_installed_hook_propagates_renderer_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous = sys.excepthook

    def fail(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise RuntimeError

    monkeypatch.setattr(_install, "print_exception", fail)
    traceback.install()
    try:
        with pytest.raises(RuntimeError):
            sys.excepthook(ValueError, ValueError("original"), None)
    finally:
        traceback.uninstall()
    assert sys.excepthook is previous


def test_optional_formatter_only_absorbs_missing_optional_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_optional(name: str) -> object:
        del name
        raise ModuleNotFoundError(name="liblaf.pprint")

    monkeypatch.setattr(_variable.importlib, "import_module", missing_optional)
    formatter = _variable._resolve_default_formatter()  # noqa: SLF001
    assert formatter({"answer": 42}) == "{'answer': 42}"
    assert _variable._resolve_default_frame_formatter() is None  # noqa: SLF001

    def broken_optional(name: str) -> object:
        del name
        raise ModuleNotFoundError(name="dependency-of-liblaf.pprint")

    monkeypatch.setattr(_variable.importlib, "import_module", broken_optional)
    with pytest.raises(ModuleNotFoundError) as caught:
        _variable._resolve_default_formatter()  # noqa: SLF001
    assert caught.value.name == "dependency-of-liblaf.pprint"
    with pytest.raises(ModuleNotFoundError):
        _variable._resolve_default_frame_formatter()  # noqa: SLF001


def test_optional_formatter_uses_pprint_presentations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Presentation:
        pass

    presentation = Presentation()
    module = types.SimpleNamespace(
        pretty=lambda _value: presentation,
        format_frame_variables=lambda _frames: (("value = 1",),),
    )
    monkeypatch.setattr(_variable.importlib, "import_module", lambda _name: module)

    assert _variable._resolve_default_formatter()(1) is presentation  # noqa: SLF001
    frame_formatter = _variable._resolve_default_frame_formatter()  # noqa: SLF001
    assert frame_formatter is not None
    assert frame_formatter(({"value": 1},)) == (("value = 1",),)


def test_optional_formatter_falls_back_when_capabilities_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = types.SimpleNamespace(
        pformat=lambda _value: "old interface",
        pformat_frames=lambda _frames: (("value = old interface",),),
    )
    monkeypatch.setattr(_variable.importlib, "import_module", lambda _name: module)

    formatter = _variable._resolve_default_formatter()  # noqa: SLF001
    assert formatter({"answer": 42}) == "{'answer': 42}"
    assert _variable._resolve_default_frame_formatter() is None  # noqa: SLF001


def test_frame_formatter_receives_all_frames_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def format_frames(frames: object) -> tuple[tuple[str, ...], ...]:
        calls.append(frames)
        return (("first = one",), ("second = two",))

    monkeypatch.setattr(_variable._state, "frame_formatter", format_frames)  # noqa: SLF001

    rendered = _variable.render_frame_variables(({"first": 1}, {"second": 2}))

    assert len(calls) == 1
    assert [[cast("Text", value).plain for value in frame] for frame in rendered] == [
        ["one"],
        ["two"],
    ]


def test_redaction_preserves_shared_identity_and_reuses_safe_copies() -> None:
    shared = {"answer": 42}
    secret = {"nested": {"api_token": "must-not-appear"}}
    memo: dict[int, object] = {}

    assert _format._redact_value(shared, memo=memo) is shared  # noqa: SLF001
    first = _format._redact_value(secret, memo=memo)  # noqa: SLF001
    second = _format._redact_value(secret, memo=memo)  # noqa: SLF001
    assert first is second
    assert "must-not-appear" not in repr(first)


@pytest.mark.parametrize(
    ("version", "expected"),
    [("1.2.3", 1), ("1.2.3rc1", 0), ("1.2.3.dev1", 0)],
)
def test_only_stable_distribution_frames_are_abbreviated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    version: str,
    expected: int,
) -> None:
    package_file = tmp_path / "example_package" / "module.py"

    class Distribution:
        files = (Path("example_package/module.py"),)

        def __init__(self, version_: str) -> None:
            self.version = version_

        def locate_file(self, file: Path) -> Path:
            return tmp_path / file

    monkeypatch.setattr(_format.site, "getsitepackages", lambda: [str(tmp_path)])
    monkeypatch.setattr(_format.site, "getusersitepackages", lambda: str(tmp_path))
    monkeypatch.setattr(
        _format.metadata,
        "packages_distributions",
        lambda: {"example_package": ["example-distribution"]},
    )
    monkeypatch.setattr(
        _format.metadata,
        "distribution",
        lambda _name: cast("metadata.Distribution", Distribution(version)),
    )
    _format._stable_release.cache_clear()  # noqa: SLF001

    assert _format._stable_release(  # noqa: SLF001
        str(package_file), "example_package.module"
    ) is bool(expected)
