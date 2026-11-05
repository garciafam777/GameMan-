#!/usr/bin/env python3
"""Cheat Engine 2X -- entry point.

Run:
    python main.py

Requires only Python 3.10+ and PySide6 (see requirements.txt).
"""

from __future__ import annotations

import sys
import os

# Ensure the src dir is on the path when run from the package root
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from CheatEngine2X.ui.main_window import main_window  # noqa: E402


def main() -> int:
    from CheatEngine2X.ui.theme import style_sheet  # noqa: E402

    app = QApplicationWrapper()
    win = main_window()
    win.setStyleSheet(style_sheet())
    app.setMainWindow(win)
    app.setStyle("Fusion")  # ensure the dark QSS stylesheet is applied uniformly
    app.show()
    return app.exec_and_exit()


if __name__ == "__main__":
    sys.exit(main())
