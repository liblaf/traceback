"""Environment-backed defaults for traceback rendering."""

from liblaf import conf


class Config(conf.BaseConfig):
    """Traceback defaults loaded from `TRACEBACK_*` environment variables.

    Per-call options passed to [`format_exception`][liblaf.traceback.format_exception]
    take precedence over this configuration.
    """

    limit: conf.Field[int] = conf.field_int(default=100)
    hide_stable_release: conf.Field[bool] = conf.field_bool(default=True)
    capture_locals: conf.Field[bool] = conf.field_bool(default=True)
    locals_hide_sunder: conf.Field[bool] = conf.field_bool(default=True)
    locals_hide_dunder: conf.Field[bool] = conf.field_bool(default=True)
    suppress: conf.Field[list[str]] = conf.field_list_str(factory=list)


config = Config()
