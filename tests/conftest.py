from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def pytest_sessionstart(session):
    _ = session
    try:
        importlib.import_module('fastapi')
    except ModuleNotFoundError:
        stub_path = Path(__file__).parent / 'stubs' / 'fastapi.py'
        spec = importlib.util.spec_from_file_location('fastapi', stub_path)
        if spec is None or spec.loader is None:
            raise RuntimeError('Failed to load fastapi test stub')
        module = importlib.util.module_from_spec(spec)
        sys.modules['fastapi'] = module
        spec.loader.exec_module(module)
