# Rendering policy

`TracebackOptions` uses `TRACEBACK_*` values for omitted fields; per-call
arguments win. Positive `limit` values keep the most recent frames and negative
ones retain the oldest portion, matching standard traceback semantics.

## Locals

Sunder and dunder names are hidden by default. Obvious secret names such as
`password`, `token`, and `api_key` are redacted in exact built-in containers.
Only those containers are traversed, so formatting does not execute arbitrary
application objects. Disable locals entirely for sensitive contexts:

```python
text = format_exception(error, capture_locals=False)
```

## Source

Source comes only from Python's existing `linecache` entry. The renderer does
not reload files, because newer on-disk text cannot reliably describe the
statement that raised. A missing cache entry is shown as unavailable.
