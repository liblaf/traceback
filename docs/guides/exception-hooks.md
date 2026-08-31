# Exception hooks

Install the hook explicitly in an application entry point:

```python
import liblaf.traceback

liblaf.traceback.install()
```

`install()` is idempotent. `uninstall()` restores the prior hook only while
this package still owns `sys.excepthook`; it never overwrites a later owner.

Set a custom formatter for individual local values, then pass `None` to restore
the optional default adapter:

```python
import liblaf.traceback

liblaf.traceback.configure_variable_formatter(lambda value: repr(value))
```
