from __future__ import annotations

from pathlib import Path
from PyQt5 import QtWidgets


class HelpViewer(QtWidgets.QDialog):
    """Simple Markdown viewer for offline help."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Night Sky Help")
        self.resize(640, 480)
        layout = QtWidgets.QVBoxLayout()
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.setLayout(layout)
        self.load_help()

    def load_help(self):
        path = Path(__file__).resolve().parent.parent / 'docs' / 'help.md'
        if not path.exists():
            self.text.setPlainText("Help file not found.")
            return
        try:
            import markdown

            html = markdown.markdown(path.read_text(encoding='utf-8'))
            self.text.setHtml(html)
        except Exception:
            self.text.setPlainText(path.read_text(encoding='utf-8'))
