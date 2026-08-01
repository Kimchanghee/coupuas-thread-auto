"""Pytest collection guard for interactive/manual smoke scripts.

These files intentionally launch GUI or network flows at import time and are
kept as manual diagnostics.  Importing them during normal collection can close
Qt-owned standard streams before the real unit suite starts.
"""

collect_ignore = [
    "test_aggro.py",
    "test_gui_flow.py",
    "test_main.py",
    "test_register_flow.py",
]
