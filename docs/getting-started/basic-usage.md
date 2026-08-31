# Basic usage

`format_exception()` captures a plain-text rendering; it does not print.

```python
from liblaf.traceback import format_exception

try:
    raise RuntimeError("connection failed")
except RuntimeError as error:
    text = format_exception(error, capture_locals=False)

assert "RuntimeError: connection failed" in text
```

Use `render_exception()` with a Rich console for width-aware output, or
`print_exception()` inside an `except` block to print the active exception.
