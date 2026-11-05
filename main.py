#!/usr/bin/env python3
"""Cheat Engine 2X -- entry point.

Run:
    python main.py
    (or double-click the packaged CheatEngine2X.exe)
"""

from __future__ import annotations

import sys
import os

from PySide6 import QtWidgets

# Ensure the src dir is on the path when run from the package root
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from CheatEngine2X.ui.main_window import main_window  # noqa: E402
from CheatEngine2X.ui.theme import style_sheet  # noqa: E402


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")  # uniform dark QSS styling
    win = main_window()
    win.setStyleSheet(style_sheet())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
