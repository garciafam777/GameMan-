"""Guided scan wizard widget.

Replaces the old "what scan type do you want?" dialog with a step-based
workflow:
  1. What changed?   (Increased / Decreased / Changed)
  2. Scan type?      (Value / AOB / Pointer chain)
  3. Target          (value, pattern, or start address)
  4. Region          (auto module or custom range)
  5. Scan

Scanning is delegated to CheatEngine2X.memory_scanner which does the
comparisons in numpy and batches reads, and to the corrected
CheatEngine2X.process_manager (self-contained, with explicit ctypes
signatures so handle/pointer returns are never truncated).
"""

from __future__ import annotations

from PySide6 import QtWidgets, QtCore
import numpy as np

from CheatEngine2X.models import Process as ModelProcess, ScanResult, MemoryRegion
from CheatEngine2X.memory_scanner import (
    MemoryScanner,
    aob_scan,
    ScanFilter as MemScanFilter,
    ValueType,
)
from CheatEngine2X.process_manager import (
    Process as CProcess,
    enumerate_regions,
    read_process_memory,
)

_FLOW = [
    "What changed?",
    "Scan type",
    "Target",
    "Region",
    "Scan",
]


class GuidedScanner(QtWidgets.QWidget):
    """The scanner panel with a step-based guided wizard."""

    status = QtCore.Signal(str)
    finished = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(560)
        self.setMinimumHeight(400)
        self._procs: list[ModelProcess] = []
        self._regions: list[MemoryRegion] = []
        self._handle: int | None = None
        self._cur_proc_model: ModelProcess | None = None
        self._build_ui()

    # -- build -----------------------------------------------------------
    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # title + stepper
        header = QtWidgets.QHBoxLayout()
        self.step_label = QtWidgets.QLabel("Step 1 of 5")
        self.step_label.setStyleSheet("color: #58a6ff; font-weight: bold;")
        header.addWidget(self.step_label)
        header.addStretch()
        self.step_label.setVisible(False)
        root.addLayout(header)

        # stepper dots
        self.dots = QtWidgets.QStackedWidget()
        self._build_steps(self.dots)
        root.addWidget(self.dots)

        # content area (steps are hidden, stepper shows them)
        self.content = QtWidgets.QStackedWidget()
        self.content.addWidget(self._step_what_changed())
        self.content.addWidget(self._step_scan_type())
        self.content.addWidget(self._step_target())
        self.content.addWidget(self._step_region())
        self.content.addWidget(self._step_scan())
        root.addWidget(self.content)

        # guidance text
        self.guide = QtWidgets.QLabel(
            "Step-by-step: tell us what changed, and we'll pick the scan for you.")
        self.guide.setStyleSheet("color: #6b707c; font-size: 9pt;")
        root.addWidget(self.guide)

        # buttons
        btn = QtWidgets.QHBoxLayout()
        self.btn_back = QtWidgets.QPushButton("← Back")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self._prev_step)
        self.btn_next = QtWidgets.QPushButton("Next →")
        self.btn_next.clicked.connect(self._next_step)
        btn.addWidget(self.btn_back)
        btn.addWidget(self.btn_next)
        root.addLayout(btn)

        # native controls (advanced scan)
        self.native_group = QtWidgets.QGroupBox("Advanced scan")
        nat = QtWidgets.QVBoxLayout(self.native_group)
        self.vlabel = QtWidgets.QLineEdit()
        self.vlabel.setPlaceholderText("Value to find (decimal)")
        self.mask_spin = QtWidgets.QSpinBox()
        self.mask_spin.setSuffix(" (mask)")
        self.min_spin = QtWidgets.QSpinBox()
        self.max_spin = QtWidgets.QSpinBox()
        self.filter_combo = QtWidgets.QComboBox()
        self.filter_combo.addItems([f.value for f in MemScanFilter])
        nat.addWidget(QtWidgets.QLabel("Value:"))
        nat.addWidget(self.vlabel)
        nat.addWidget(QtWidgets.QLabel("Mask:"))
        nat.addWidget(self.mask_spin)
        nat.addWidget(QtWidgets.QLabel("Min:"))
        nat.addWidget(self.min_spin)
        nat.addWidget(QtWidgets.QLabel("Max:"))
        nat.addWidget(self.max_spin)
        nat.addWidget(QtWidgets.QLabel("Filter:"))
        nat.addWidget(self.filter_combo)
        btn2 = QtWidgets.QHBoxLayout()
        self.btn_native = QtWidgets.QPushButton("Run native scan")
        self.btn_native.clicked.connect(self._run_native)
        btn2.addWidget(self.btn_native)
        root.addLayout(btn2)

    def _build_steps(self, stacked: QtWidgets.QStackedWidget) -> None:
        for i, name in enumerate(_FLOW, 1):
            lbl = QtWidgets.QLabel(f"Step {i}")
            lbl.setAlignment(QtCore.Qt.AlignCenter)
            color = "#58a6ff" if i == 1 else "#6b707c"
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            stacked.addWidget(lbl)

    def _step_what_changed(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        info = QtWidgets.QLabel(
            "Tell us what changed in-game. This chooses the scan direction.")
        lay.addWidget(info)

        grp = QtWidgets.QGroupBox("What changed?")
        rlay = QtWidgets.QVBoxLayout(grp)
        self.rb_inc = QtWidgets.QRadioButton("Increased")
        self.rb_dec = QtWidgets.QRadioButton("Decreased")
        self.rb_changed = QtWidgets.QRadioButton("Changed since last scan")
        self.rb_inc.setChecked(True)
        rlay.addWidget(self.rb_inc)
        rlay.addWidget(self.rb_dec)
        rlay.addWidget(self.rb_changed)
        lay.addWidget(grp)

        self.hint = QtWidgets.QLabel(
            "Hint: take a screenshot first, then make the change.")
        lay.addWidget(self.hint)
        return w

    def _step_scan_type(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        info = QtWidgets.QLabel(
            "Choose what you're searching for in memory.")
        lay.addWidget(info)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems([
            "Value scan", "Array-of-bytes (AOB) scan", "Pointer chain"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        lay.addWidget(self.type_combo)

        self.type_note = QtWidgets.QLabel("")
        self.type_note.setStyleSheet("color: #6b707c; font-size: 9pt;")
        lay.addWidget(self.type_note)
        return w

    def _step_target(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        self.target_label = QtWidgets.QLabel("Target value / pattern")
        self.target_input = QtWidgets.QLineEdit()
        self.target_input.setPlaceholderText("e.g. 12345678 or FF 00 AA 99")
        lay.addWidget(self.target_label)
        lay.addWidget(self.target_input)

        self.value_desc = QtWidgets.QLabel("")
        self.value_desc.setStyleSheet("color: #6b707c; font-size: 9pt;")
        lay.addWidget(self.value_desc)
        return w

    def _step_region(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        info = QtWidgets.QLabel("Memory region to scan.")
        lay.addWidget(info)

        self.region_combo = QtWidgets.QComboBox()
        self.region_combo.addItem("<auto-select module>", "auto")
        self.region_combo.setMinimumWidth(220)
        lay.addWidget(self.region_combo)

        self.custom_check = QtWidgets.QCheckBox("Custom range")
        self.custom_check.toggled.connect(self._on_custom_changed)
        lay.addWidget(self.custom_check)

        self.custom_layout = QtWidgets.QHBoxLayout()
        self.custom_base = QtWidgets.QLineEdit()
        self.custom_base.setPlaceholderText("base address")
        self.custom_size = QtWidgets.QLineEdit()
        self.custom_size.setPlaceholderText("size")
        self.custom_layout.addWidget(self.custom_base)
        self.custom_layout.addWidget(self.custom_size)
        lay.addLayout(self.custom_layout)
        return w

    def _step_scan(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        lay.addWidget(self.progress)

        self.result_count = QtWidgets.QLabel("0 results")
        self.result_count.setStyleSheet("color: #6b707c; font-size: 9pt;")
        lay.addWidget(self.result_count)

        btn = QtWidgets.QHBoxLayout()
        self.btn_run = QtWidgets.QPushButton("▶  Scan")
        self.btn_run.setAutoDefault(True)
        self.btn_run.clicked.connect(self._run_guided)
        btn.addWidget(self.btn_run)
        lay.addLayout(btn)
        return w

    # -- stepping --------------------------------------------------------
    def _next_step(self) -> None:
        idx = self.content.currentIndex()
        if idx >= self.content.count() - 1:
            self._run_guided()
            return
        self.content.setCurrentIndex(idx + 1)
        self.btn_back.setEnabled(idx > 0)
        self.step_label.setText(f"Step {idx + 2} of 5")
        self._on_type_changed(self.type_combo.currentText())

    def _prev_step(self) -> None:
        idx = self.content.currentIndex()
        self.content.setCurrentIndex(idx - 1)
        self.btn_back.setEnabled(idx > 1)
        self.step_label.setText(f"Step {idx} of 5")

    def _on_type_changed(self, text: str) -> None:
        self.type_note.setText({
            "Value scan": "Enter the in-game value you want to find below.",
            "Array-of-bytes (AOB)": "Enter the byte pattern (hex, space-separated).",
            "Pointer chain": "We'll find a chain of pointers leading to the target.",
        }.get(text, ""))

    def _on_custom_changed(self, checked: bool) -> None:
        self.custom_layout.setVisible(checked)

    # -- scanning --------------------------------------------------------
    def start_scan(self, process: ModelProcess | None) -> None:
        """Open the process, load its modules + readable regions, and store the
        handle so all subsequent scanner reads use one cached handle."""
        self._procs = []
        self._regions = []
        self._handle = None
        self._cur_proc_model = process
        if process is not None:
            with CProcess.open(process.pid) as proc:
                self._regions = proc.regions()
                self._procs = proc.modules()
                self._handle = proc.handle
        self.region_combo.clear()
        self.region_combo.addItem("<auto-select module>", "auto")
        for mod in self._procs:
            self.region_combo.addItem(f"{mod.name} ({hex(mod.base)})", hex(mod.base))

    @QtCore.Slot()
    def _run_guided(self) -> None:
        self.stop = False
        typ = self.type_combo.currentText()
        self.status.emit("Running guided scan...")
        self.progress.setRange(0, 0)
        self.result_count.setText("Scanning...")

        handle = self._handle
        if handle is None:
            self.status.emit("Please select a process first.")
            return

        if typ == "Value scan":
            val = int(self.target_input.text(), 0)
            f = MemScanFilter.EQUAL
            scanner = MemoryScanner(
                lambda a, s: read_process_memory(handle, a, s),
                self._regions, value_type=ValueType.INT32, aligned=False)
            scanner.set_progress_cb(lambda done, total: self.progress.setValue(
                int(done / total * 100)) if total else None)
            summary = scanner.first_scan(f, value=val)
            results = [
                ScanResult(index=i, value=int(v), address=int(a), module="<auto>")
                for i, (a, v) in enumerate(zip(summary.addresses, scanner.values))]
            self._emit(results)

        elif typ == "Array-of-bytes (AOB) scan":
            pat = self.target_input.text().strip()
            results = [
                ScanResult(index=i, value=0, address=int(a), module="AOB")
                for i, a in enumerate(aob_scan(
                    lambda a, s: read_process_memory(handle, a, s),
                    self._regions, pat))]
            self._emit(results)

        elif typ == "Pointer chain":
            # Pointer-chain resolution is a full feature (injection lifecycle)
            # and is intentionally stubbed out in this build.
            self.status.emit("Pointer-chain scan coming next.")
            self.finished.emit()

        else:
            self.status.emit("Unknown scan type")
            self.finished.emit()

    def _emit(self, results: list[ScanResult]) -> None:
        self.result_count.setText(f"{len(results)} result(s)")
        self.finished.emit(list(results))
        self.status.emit(f"Found {len(results)} result(s)")

    @QtCore.Slot()
    def _run_native(self) -> None:
        if self._handle is None:
            self.status.emit("Select a process first.")
            return
        val = self.vlabel.text().strip()
        if not val:
            self.status.emit("Enter a value.")
            return
        try:
            v = int(val, 0)
        except ValueError:
            self.status.emit("Invalid value")
            return
        try:
            f = MemScanFilter(self.filter_combo.currentData())
        except ValueError:
            self.status.emit("Invalid filter")
            return

        scanner = MemoryScanner(
            lambda a, s: read_process_memory(self._handle, a, s),
            self._regions, value_type=ValueType.INT32, aligned=False)
        scanner.set_progress_cb(lambda done, total: None)
        self.status.emit(f"Scanning value {v} ({f.name}) ...")
        self.progress.setRange(0, 0)
        self.result_count.setText("Scanning...")
        summary = scanner.first_scan(f, value=v)
        idx = np.nonzero(summary.addresses)[0]
        results = [
            ScanResult(index=i, value=int(scanner.values[j]),
                       address=int(scanner.addresses[j]), module="native")
            for i, j in enumerate(idx)]
        self._emit(results)
        self.status.emit(f"Native scan: {len(results)} result(s)")

    def _debug(self) -> None:
        from CheatEngine2X.disassembler import disassemble
        data = b"\x50\x58\xc3"  # PUSH, POP, RET
        lines = disassemble(data, 0x1000)
        self.status.emit("\n".join(lines))

    def selected_process(self) -> ModelProcess | None:
        # Fallback kept for API compatibility; the main window's
        # process selector is wired to start_scan() directly.
        return None
