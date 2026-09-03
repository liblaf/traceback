# Keep text formatting and Rich rendering separate

`format_exception()` returns plain text for logs, files, and snapshots;
`render_exception()` returns the Rich renderable. This avoids making a
terminal-rendering dependency part of every caller's output contract.
