"""Result view for scan results."""

from __future__ import annotations
from PySide6 import QtWidgets, QtCore

from ..models import ScanResult


class ResultView(QtWidgets.QListView):
    """Shows a list of ScanResult entries.

    Wired to a model by the caller (e.g. MainWindow) via set_model().
    """

    def __init__(self) -> None:
        super().__init__()
        self._model = None
        self.setAlternatingRowColors(True)

    def set_model(self, model: QtWidgets.QAbstractItemModel | None) -> None:
        self._model = model
        self.setModel(model)

    def refresh(self) -> None:
        if self._model is not None:
            self.repaint()
