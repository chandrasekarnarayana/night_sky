from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QLineEdit, QListWidget, QLabel, QHBoxLayout, QVBoxLayout, QWidget, QPushButton
from PyQt5.QtCore import pyqtSignal
from typing import List, Dict

from .data_manager import load_cities


class LocationSelector(QWidget):
    """Widget to select an observing location.

    - Manual latitude/longitude entry
    - City search (loads `data/cities.csv`) with incremental substring matching

    Emits `location_changed(lat: float, lon: float)` when the chosen location changes.
    """

    location_changed = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cities: List[Dict] = []
        try:
            self.cities = load_cities()
        except FileNotFoundError:
            # No cities available yet; widget still functional for manual entry
            self.cities = []

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('Search city...')
        self.search_results = QListWidget()
        self.search_results.setMaximumHeight(120)

        self.lat_edit = QLineEdit()
        self.lat_edit.setPlaceholderText('Latitude (deg)')
        self.lon_edit = QLineEdit()
        self.lon_edit.setPlaceholderText('Longitude (deg)')

        # Quick apply button
        self.apply_btn = QPushButton('Apply')

        # Layout
        top = QHBoxLayout()
        top.addWidget(QLabel('Location:'))
        top.addWidget(self.search_edit)

        coords = QHBoxLayout()
        coords.addWidget(QLabel('Lat:'))
        coords.addWidget(self.lat_edit)
        coords.addWidget(QLabel('Lon:'))
        coords.addWidget(self.lon_edit)
        coords.addWidget(self.apply_btn)

        main = QVBoxLayout()
        main.addLayout(top)
        main.addWidget(self.search_results)
        main.addLayout(coords)
        self.setLayout(main)

        # Connections
        self.search_edit.textChanged.connect(self._on_search)
        self.search_results.itemClicked.connect(self._on_result_clicked)
        self.apply_btn.clicked.connect(self._on_apply)
        self.lat_edit.returnPressed.connect(self._on_apply)
        self.lon_edit.returnPressed.connect(self._on_apply)

    def _format_city_label(self, c: Dict) -> str:
        return f"{c['name']}, {c.get('country','')} ({c['lat_deg']:.4f}, {c['lon_deg']:.4f})"

    def _on_search(self, text: str) -> None:
        self.search_results.clear()
        q = (text or '').strip().lower()
        if not q or not self.cities:
            return
        matches = []
        for c in self.cities:
            if q in c['name'].lower() or q in c.get('country','').lower():
                matches.append(c)
        # Show first 50 matches to avoid huge lists
        for c in matches[:50]:
            self.search_results.addItem(self._format_city_label(c))

    def _on_result_clicked(self, item) -> None:
        text = item.text()
        # find matching city by formatted label
        for c in self.cities:
            if text.startswith(c['name']):
                self.lat_edit.setText(f"{c['lat_deg']}")
                self.lon_edit.setText(f"{c['lon_deg']}")
                self.location_changed.emit(float(c['lat_deg']), float(c['lon_deg']))
                break

    def _on_apply(self) -> None:
        try:
            lat = float(self.lat_edit.text())
            lon = float(self.lon_edit.text())
        except Exception:
            QtWidgets.QMessageBox.warning(self, 'Invalid input', 'Latitude and Longitude must be numbers')
            return
        self.location_changed.emit(lat, lon)
    
    def _update_lat_lon_fields(self, lat: float, lon: float) -> None:
        """
        Update lat/lon fields without emitting signal.
        Used when location is set externally (e.g., from Earth view).
        """
        self.lat_edit.blockSignals(True)
        self.lon_edit.blockSignals(True)
        self.lat_edit.setText(f"{lat:.4f}")
        self.lon_edit.setText(f"{lon:.4f}")
        self.lat_edit.blockSignals(False)
        self.lon_edit.blockSignals(False)
