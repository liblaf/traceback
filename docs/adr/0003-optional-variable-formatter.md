# Resolve the pretty-printer through a narrow optional adapter

`liblaf.pprint` is imported only by the local variable-formatting adapter and
falls back to `pprint` when absent. When present, its frame-batch API formats
all visible locals in one pass so shared references can identify their frame
and variable anchor. This preserves a richer experience without imposing a
sibling dependency or import-order-sensitive behavior on traceback rendering.
