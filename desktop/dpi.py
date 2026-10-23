"""Opt into Windows per-monitor DPI awareness *before* creating the first Tk window.

Without this, Windows may bitmap-scale an 830px Tk window, blurring all text,
and controls can spill below the usable desktop at 125/150/200% scaling.
"""
from __future__ import annotations

import ctypes
import sys


def enable_high_dpi() -> str:
    if sys.platform != 'win32':
        return 'not-windows'
    try:
        # Windows 10 1703+: DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (-4).
        # Do not touch Tk's scaling value; Tk derives it from Windows DPI.
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return 'per-monitor-v2'
    except (AttributeError, OSError, ValueError):
        pass
    try:
        # Windows 8.1+ fallback. E_ACCESSDENIED means the process already opted in.
        rc = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if rc == 0:
            return 'per-monitor'
    except (AttributeError, OSError, ValueError):
        pass
    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            return 'system'
    except (AttributeError, OSError, ValueError):
        pass
    return 'system-managed'
