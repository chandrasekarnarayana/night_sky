"""
2D cylindrical projection Earth map with click-to-select location.

Displays the world in a simple cylindrical projection (longitude 0–360° on x-axis,
latitude -90° to +90° on y-axis). Clicking on the map converts screen coordinates
to lat/lon and emits a location_changed signal.
"""

from dataclasses import dataclass
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
import pyqtgraph as pg
import numpy as np


@dataclass
class GridLine:
    """A latitude or longitude grid line for reference."""
    value: float  # Latitude or longitude in degrees
    is_latitude: bool  # True for latitude, False for longitude
    color: tuple = (100, 100, 100, 100)  # RGBA


class EarthView2D(pg.GraphicsLayoutWidget):
    """
    2D cylindrical projection of Earth with click-to-select location support.
    
    Emits:
        location_changed: (lat_deg, lon_deg) when user clicks on map
    """
    
    location_changed = pyqtSignal(float, float)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Earth View (2D)")
        
        # Create plot widget for the map
        self.plot = self.addPlot(row=0, col=0)
        self.plot.setLabel('bottom', 'Longitude', units='°')
        self.plot.setLabel('left', 'Latitude', units='°')
        self.plot.setTitle('World Map (Cylindrical Projection)')
        
        # Set axis ranges: longitude 0–360, latitude -90–90
        self.plot.setXRange(0, 360, padding=0)
        self.plot.setYRange(-90, 90, padding=0)
        
        # Add grid lines at major intervals
        self._add_grid_lines()
        
        # Draw a simple Earth background (light blue)
        background = pg.PlotCurveItem(
            x=[0, 360, 360, 0, 0],
            y=[-90, -90, 90, 90, -90],
            pen=pg.mkPen(color='lightblue', width=2),
            fillLevel=-90,
            fillBrush=pg.mkBrush(color=(100, 149, 237, 80))  # Cornflower blue with transparency
        )
        self.plot.addItem(background)
        
        # Scatter plot for cities (optional; can be populated later)
        self.cities_scatter = pg.ScatterPlotItem(
            size=8,
            pen=pg.mkPen(color='red', width=1),
            brush=pg.mkBrush(color='red'),
            symbol='o'
        )
        self.plot.addItem(self.cities_scatter)
        
        # Marker for selected location
        self.location_marker = pg.ScatterPlotItem(
            size=15,
            pen=pg.mkPen(color='gold', width=2),
            brush=pg.mkBrush(color='yellow'),
            symbol='+'
        )
        self.plot.addItem(self.location_marker)
        
        # Connect mouse click event
        self.plot.scene().sigMouseClicked.connect(self._on_mouse_clicked)
    
    def _add_grid_lines(self):
        """Add latitude and longitude grid lines for reference."""
        # Longitude lines (every 30°)
        for lon in range(0, 361, 30):
            line = pg.PlotCurveItem(
                x=[lon, lon],
                y=[-90, 90],
                pen=pg.mkPen(color=(100, 100, 100, 100), width=0.5, style=Qt.DashLine)
            )
            self.plot.addItem(line)
        
        # Latitude lines (every 30°)
        for lat in range(-90, 91, 30):
            line = pg.PlotCurveItem(
                x=[0, 360],
                y=[lat, lat],
                pen=pg.mkPen(color=(100, 100, 100, 100), width=0.5, style=Qt.DashLine)
            )
            self.plot.addItem(line)
    
    def _on_mouse_clicked(self, event):
        """Handle mouse clicks on the map; convert to lat/lon."""
        if event.button() != Qt.LeftButton:
            return
        
        # Get click position in plot coordinates
        pos = event.scenePos()
        if self.plot.sceneBoundingRect().contains(pos):
            mapped_pos = self.plot.mapSceneToView(pos)
            lon = mapped_pos.x()
            lat = mapped_pos.y()
            
            # Clamp to valid ranges
            lat = max(-90, min(90, lat))
            lon = lon % 360  # Wrap to 0–360
            
            # Update marker position
            self.location_marker.setData(x=[lon], y=[lat])
            
            # Emit signal
            self.location_changed.emit(lat, lon)
    
    def add_cities(self, cities):
        """
        Add cities to the map as red dots.
        
        Args:
            cities: List of dicts with 'lat_deg' and 'lon_deg' keys
        """
        if not cities:
            return
        
        lats = [c['lat_deg'] for c in cities]
        lons = [c['lon_deg'] for c in cities]
        self.cities_scatter.setData(x=lons, y=lats)
    
    def set_marker(self, lat_deg, lon_deg):
        """
        Update the location marker without emitting signal (e.g., from UI field update).
        
        Args:
            lat_deg: Latitude in degrees
            lon_deg: Longitude in degrees (0–360)
        """
        lon_deg = lon_deg % 360
        self.location_marker.setData(x=[lon_deg], y=[lat_deg])
    
    def export_png(self, path, width=1600, height=900):
        """
        Export the map view to PNG.
        
        Args:
            path: File path to save PNG
            width: Width in pixels
            height: Height in pixels
        """
        # Resize to desired dimensions, capture, then restore
        original_size = self.size()
        self.resize(width, height)
        pixmap = self.grab()
        pixmap.save(str(path))
        self.resize(original_size)
