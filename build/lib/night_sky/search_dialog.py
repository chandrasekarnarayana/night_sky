from __future__ import annotations

from PyQt5 import QtWidgets, QtCore
from difflib import SequenceMatcher


class SearchDialog(QtWidgets.QDialog):
    """Simple search/go-to dialog."""

    object_selected = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find object")
        self.resize(400, 300)
        layout = QtWidgets.QVBoxLayout()
        self.edit = QtWidgets.QLineEdit()
        self.edit.setPlaceholderText("Search stars, planets, Moon, Messier, NGC/IC")
        self.list = QtWidgets.QListWidget()
        self.completer = QtWidgets.QCompleter()
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.edit.setCompleter(self.completer)
        btns = QtWidgets.QHBoxLayout()
        self.btn_center = QtWidgets.QPushButton("Center")
        self.btn_close = QtWidgets.QPushButton("Close")
        btns.addWidget(self.btn_center)
        btns.addWidget(self.btn_close)
        layout.addWidget(self.edit)
        layout.addWidget(self.list)
        layout.addLayout(btns)
        self.setLayout(layout)

        self._objects = []  # list of dicts with keys: name, type, data

        self.edit.textChanged.connect(self._on_search)
        self.btn_close.clicked.connect(self.reject)
        self.btn_center.clicked.connect(self._emit_selected)
        self.list.itemDoubleClicked.connect(self._emit_selected)

    def set_objects(self, objects: list[dict]):
        self._objects = objects
        try:
            model = QtCore.QStringListModel([o.get('name', '') for o in objects])
            self.completer.setModel(model)
        except Exception:
            pass
        self._on_search(self.edit.text())

    def _on_search(self, text: str):
        self.list.clear()
        q = (text or '').strip().lower()
        scored = []
        for obj in self._objects:
            name = obj.get('name', '')
            if not q:
                score = 1.0
            else:
                score = SequenceMatcher(None, q, name.lower()).ratio()
                if q in name.lower():
                    score += 0.3
            scored.append((score, obj))
        scored.sort(key=lambda t: t[0], reverse=True)
        for score, obj in scored:
            if q and score < 0.2:
                continue
            name = obj.get('name', '')
            item = QtWidgets.QListWidgetItem(f"{name} ({obj.get('type','')})")
            item.setData(QtCore.Qt.UserRole, obj)
            self.list.addItem(item)

    def _emit_selected(self):
        item = self.list.currentItem()
        if not item:
            return
        obj = item.data(QtCore.Qt.UserRole)
        self.object_selected.emit(obj)
        self.accept()
