<div align="center" markdown>

![liblaf-traceback](https://socialify.git.ci/liblaf/traceback/image?description=1&forks=1&issues=1&language=1&name=1&owner=1&pattern=Transparent&pulls=1&stargazers=1&theme=Auto)

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/liblaf-traceback?logo=Python)](https://pypi.org/project/liblaf-traceback/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[Source](https://github.com/liblaf/traceback) · [Issues](https://github.com/liblaf/traceback/issues)

![Rule](https://cdn.jsdelivr.net/gh/andreasbm/readme/assets/lines/rainbow.png)

</div>

# liblaf.traceback

Rich exception rendering for applications that need terminal output and a
plain-text path for logs, files, and snapshots.

```python
import liblaf.traceback

try:
    raise ValueError("invalid input")
except ValueError as error:
    text = liblaf.traceback.format_exception(error)
    liblaf.traceback.print_exception(error)
```

`format_exception()` returns plain text. `render_exception()` returns a Rich renderable for `Console.print()`. Captured local values hide sunder and dunder names by default and recursively redact obvious secret keys in built-in containers. Traversal is deliberately bounded and does not inspect arbitrary objects; set `capture_locals=False` where locals may be sensitive. `TRACEBACK_*` environment variables configure defaults through `liblaf-conf`.

When `liblaf-pprint` is installed, visible locals from the complete stack are
formatted in one batch. Repeated values can therefore point back to a frame and
variable path such as `$frames[0].payload`; without it, each value uses the
standard-library `pprint` adapter independently.

Source is rendered only from Python's existing line cache. The library never reloads a file and marks absent cached source as unavailable; it does not claim to reconstruct the exact source that executed.

## Guides

The documentation covers [basic usage](https://liblaf.github.io/traceback/getting-started/basic-usage/),
[rendering policy](https://liblaf.github.io/traceback/concepts/rendering-policy/),
and [exception hooks](https://liblaf.github.io/traceback/guides/exception-hooks/).

### License

Copyright © 2026 [liblaf](https://github.com/liblaf). This project is [MIT](https://github.com/liblaf/traceback/blob/main/LICENSE) licensed.
