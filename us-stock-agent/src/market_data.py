"""Backward-compatible module proxy for src.us.market_data.core."""

from importlib import import_module as _import_module
import sys as _sys
import types as _types

_module_name = __name__
try:
    _impl = _import_module(".us.market_data.core", __package__)
except (ImportError, TypeError):  # direct script execution
    _impl = _import_module("us.market_data.core")

for _key, _value in _impl.__dict__.items():
    if _key not in {"__name__", "__package__", "__loader__", "__spec__"}:
        globals()[_key] = _value

class _ProxyModule(_types.ModuleType):
    def __getattr__(self, name):
        return getattr(_impl, name)

    def __setattr__(self, name, value):
        setattr(_impl, name, value)
        super().__setattr__(name, value)

    def __delattr__(self, name):
        if hasattr(_impl, name):
            delattr(_impl, name)
        super().__delattr__(name)

_sys.modules[_module_name].__class__ = _ProxyModule
