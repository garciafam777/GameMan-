"""Modern dark main window for Cheat Engine 2X.

Layout:
  - QToolBar (top): process selector, engine filter, scan-type selector
  - QSplitter (center): left = scanner panel, right = results + memory browser
  - QStatusBar (bottom): scan status / progress
"""

from __future__ import annotations
import sys
from PySide6 import QtWidgets, QtCore

from ..config import C
from .theme import style_sheet
from ..scan.guided_scanner import GuidedScanner
from ..scan.result_view import ResultView
from ..scan.memory_browser import MemoryBrowser
from ..models import Process


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Cheat Engine 2X")
        self.setMinimumSize(1100, 700)
        self._setup_ui()
        # populate the process selector from the corrected process layer
        from CheatEngine2X.process_manager import list_processes
        self.populate_processes(list_processes())

    # -- UI setup -------------------------------------------------------
    def _setup_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- toolbar (replacing the old CE flat menu) ---
        self._build_toolbar(root)
        # status bar
        self._build_statusbar(root)
        # --- center splitter ---
        self._build_center(root)

    def _build_toolbar(self, root: QtWidgets.QVBoxLayout) -> None:
        toolbar = QtWidgets.QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setIconSize(QtCore.QSize(18, 18))
        self.addToolBar(toolbar)

        # process selector
        self.proc_combo = QtWidgets.QComboBox()
        self.proc_combo.setMinimumWidth(220)
        self.proc_combo.setPlaceholderText("Select process...")
        toolbar.addWidget(self.proc_combo)

        toolbar.addSeparator()

        self.engine_combo = QtWidgets.QComboBox()
        self.engine_combo.addItems(list(__import__("CheatEngine2X.config", fromlist=["ENGINE_TEMPLATES"]).ENGINE_TEMPLATES))
        self.engine_combo.setToolTip("Game engine filter for guided scan")
        toolbar.addWidget(self.engine_combo)

        toolbar.addSeparator()

        self.scan_type_radio = QtWidgets.QButtonGroup(self)
        self.scan_type_radio.setExclusive(True)
        self.radio_value = QtWidgets.QRadioButton("Address scan")
        self.radio_aob = QtWidgets.QRadioButton("AOB scan")
        self.radio_ptr = QtWidgets.QRadioButton("Pointer scan")
        self.radio_value = QtWidgets.QRadioButton("Address scan")
        self.scan_type_radio.addButton(self.radio_value)
        self.scan_type_radio.addButton(self.radio_aob)
        self.scan_type_radio.addButton(self.radio_ptr)
        self.radio_value.setChecked(True)
        toolbar.addWidget(self.radio_value)
        toolbar.addWidget(self.radio_aob)
        toolbar.addWidget(self.radio_ptr)

        toolbar.addSeparator()

        self.btn_scan = QtWidgets.QPushButton("▶  Scan")
        self.btn_scan.setAutoDefault(True)
        self.btn_scan.clicked.connect(self._on_scan)
        self.btn_stop = QtWidgets.QPushButton("■  Stop")
        self.btn_stop.setAutoDefault(False)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_stop.setEnabled(False)
        toolbar.addWidget(self.btn_scan)
        toolbar.addWidget(self.btn_stop)

        # spacer to push controls right
        root.addWidget(toolbar)
        root.addStretch(1)

    def _build_statusbar(self, root: QtWidgets.QVBoxLayout) -> None:
        self.statusbar = QtWidgets.QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setStyleSheet("color: #6b707c;")
        self.statusbar.addWidget(self.status_label)

    def _build_center(self, root: QtWidgets.QVBoxLayout) -> None:
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C['border']};
                width: 8px;
            }}
        """)

        # left: scanner
        self.scanner = GuidedScanner()
        splitter.addWidget(self.scanner)

        # right: results + memory browser
        self.results = ResultView()
        self.memory_browser = MemoryBrowser()
        self.memory_browser.setVisible(False)

        right = QtWidgets.QWidget()
        rlayout = QtWidgets.QVBoxLayout(right)
        rlayout.setContentsMargins(0, 0, 0, 0)
        rlayout.addWidget(self.results)
        rlayout.addWidget(self.memory_browser)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([600, 600])
        root.addWidget(splitter)

    # -- wiring ----------------------------------------------------------
    def populate_processes(self, procs: list[Process]) -> None:
        self.proc_combo.clear()
        self.proc_combo.addItem("<choose a process>", None)
        for p in procs:
            self.proc_combo.addItem(p.name, p.pid)
        if procs:
            self.proc_combo.setCurrentIndex(1)

    def selected_process(self) -> Process | None:
        idx = self.proc_combo.currentIndex()
        if idx <= 0:
            return None
        pid = self.proc_combo.currentData()
        name = self.proc_combo.currentText().split(" (")[0]
        return Process(pid=pid, name=name)

    def _on_scan(self) -> None:
        self.btn_scan.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText("Scanning...")
        self.scanner.start_scan(self.selected_process())
        # hook stop
        self._stop_requested = False

    def _on_stop(self) -> None:
        self._stop_requested = True
        self.scanner.stop = True
        self.btn_scan.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("Stopped")
