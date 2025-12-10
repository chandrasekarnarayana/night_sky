"""Theme presets for Night Sky."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Theme:
    name: str
    qss: str
    bg_color: str
    grid_color: str
    text_color: str


THEMES = {
    "night": Theme(
        name="Night",
        qss="""
        QMainWindow { background: #05070a; color: #d0d0d0; }
        QWidget { background: #0a0d12; color: #d0d0d0; }
        QPushButton, QLineEdit, QDateTimeEdit, QDoubleSpinBox, QComboBox {
            background: #101218; color: #d0d0d0; border: 1px solid #1c2028; padding: 4px;
        }
        QTabWidget::pane { border: 1px solid #1c2028; }
        QToolBar { background: #0a0d12; border: 0px; spacing: 4px; }
        """,
        bg_color="#05070a",
        grid_color="#1c2028",
        text_color="#d0d0d0",
    ),
    "astro_red": Theme(
        name="Astro Red",
        qss="""
        * { color: #ff6666; }
        QMainWindow { background: #060606; }
        QWidget { background: #0a0a0a; }
        QPushButton, QLineEdit, QDateTimeEdit, QDoubleSpinBox, QComboBox {
            background: #0f0f0f; color: #ff6666; border: 1px solid #333; padding: 4px;
        }
        """,
        bg_color="#060606",
        grid_color="#302020",
        text_color="#ff6666",
    ),
    "high_contrast": Theme(
        name="High Contrast",
        qss="""
        QMainWindow { background: #000000; color: #e0e0e0; }
        QWidget { background: #050505; color: #e0e0e0; }
        QPushButton, QLineEdit, QDateTimeEdit, QDoubleSpinBox, QComboBox {
            background: #111; color: #e0e0e0; border: 1px solid #555; padding: 4px;
        }
        """,
        bg_color="#000000",
        grid_color="#444444",
        text_color="#e0e0e0",
    ),
}


def apply_theme(app, theme_key: str):
    theme = THEMES.get(theme_key, THEMES["night"])
    app.setStyleSheet(theme.qss)
    return theme
