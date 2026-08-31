# Traceback Rendering

This context turns a raised Python exception into a useful human-facing diagnosis without changing exception semantics.

## Language

**Captured source**:
The source text already held by Python's `linecache` when an exception is
rendered. It may be stale and is not necessarily the exact code that executed.
_Avoid_: executed source, current source

**Hidden frame**:
A traceback frame deliberately abbreviated to a dim location summary while retaining the fact that it occurred.
_Avoid_: removed frame, omitted frame

**Variable formatter**:
The callable that turns one captured local value into a human-readable
presentation.
_Avoid_: pretty-printer dependency

**Variable batch**:
The ordered visible locals from every rendered frame, formatted through one
shared identity pass when the active adapter supports it.
_Avoid_: Locals table, stack dump
