# Keep text formatting and Rich rendering separate

`format_exception()` returns plain text so it remains useful to stdlib-shaped consumers such as loggers and files; `render_exception()` returns the Rich renderable. This avoids making a terminal-rendering dependency part of every caller's output contract.
