"""Minimal hex/memory browser for Cheat Engine 2X.

Displays a contiguous memory range as hex + ASCII, with a simple
address/hex viewer. Built on QPlainTextEdit for editable raw bytes
in a lightweight way.

Performance note: full memory dumping is heavy; for a MVP we show a
configurable window. A full-featured viewer is a later phase.
"""

from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from ..models import MemoryRegion, Process
from ..process_manager import read_process_memory, enumerate_regions


class MemoryBrowser(QtWidgets.QTextEdit):
    """Hex/ASCII viewer of a process's memory."""

    status = QtCore.Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._proc: Process | None = None
        self._region: MemoryRegion | None = None
        self.setReadOnly(True)
        self.setMaximumHeight(320)
        self.setMinimumHeight(200)
        self.setStyleSheet("""
            QTextEdit {
                background: #1c1f24;
                color: #e6e8ec;
                border: 1px solid #33363e;
                font-family: "Cascadia Mono", "Consolas", monospace;
                font-size: 10pt;
            }
        """)
        self.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

    def set_process(self, proc: Process | None) -> None:
        self._proc = proc
        self.setPlainText("Select a process to browse memory.")

    def set_region(self, region: MemoryRegion | None) -> None:
        self._region = region
        self.refresh()

    def refresh(self) -> None:
        if self._proc is None or self._region is None:
            self.setPlainText("Select a process + region to browse memory.")
            return
        size = min(self._region.size, 2 * 1024 * 1024)  # 2MB window
        data = read_process_memory(self._proc.pid, self._region.address, size)
        if not data:
            self.setPlainText("Failed to read memory.")
            return
        lines = self._format(data)
        self.setPlainText("\n".join(lines))

    def _format(self, data: bytes) -> list[str]:
        out = []
        for off in range(0, len(data), 16):
            chunk = data[off:off + 16]
            hexpart = " ".join(f"{b:02X}" for b in chunk)
            hexpart = hexpart.ljust(47)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            out.append(f"{self._region.address + off:08X}  {hexpart}  {asc}")
        return out
