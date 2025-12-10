from __future__ import annotations

from PyQt5 import QtWidgets, QtGui, QtCore


class MoonPhaseWidget(QtWidgets.QLabel):
    """Small icon showing moon illuminated fraction and waxing/waning shading."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 40)
        self._fraction = 0.0
        self._waxing = True
        self._update_pixmap()

    def set_phase(self, fraction: float, waxing: bool = True):
        self._fraction = max(0.0, min(1.0, float(fraction)))
        self._waxing = bool(waxing)
        self._update_pixmap()

    def _update_pixmap(self):
        size = self.size()
        pm = QtGui.QPixmap(size)
        pm.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        center = QtCore.QPointF(size.width() / 2, size.height() / 2)
        radius = min(size.width(), size.height()) / 2 - 2

        # base disc (dark)
        painter.setBrush(QtGui.QColor(10, 12, 18))
        painter.setPen(QtGui.QPen(QtGui.QColor(180, 180, 200), 1))
        painter.drawEllipse(center, radius, radius)

        # illuminated portion
        frac = self._fraction
        if frac > 0:
            painter.setBrush(QtGui.QColor(230, 230, 255))
            painter.setPen(QtCore.Qt.NoPen)
            rect = QtCore.QRectF(
                center.x() - radius,
                center.y() - radius,
                2 * radius,
                2 * radius,
            )
            # Draw full disc then mask with terminator
            painter.drawEllipse(rect)

            # Terminator mask: shift ellipse to clip the dark side
            mask = QtGui.QPixmap(self.size())
            mask.fill(QtCore.Qt.transparent)
            mask_p = QtGui.QPainter(mask)
            mask_p.setRenderHint(QtGui.QPainter.Antialiasing)
            mask_p.setBrush(QtGui.QColor(255, 255, 255))
            mask_p.setPen(QtCore.Qt.NoPen)
            offset = (1 - 2 * frac) * radius
            if self._waxing:
                mask_rect = QtCore.QRectF(rect.center().x() + offset - radius, rect.top(), 2 * radius, 2 * radius)
            else:
                mask_rect = QtCore.QRectF(rect.center().x() - offset - radius, rect.top(), 2 * radius, 2 * radius)
            mask_p.drawEllipse(mask_rect)
            mask_p.end()
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
            painter.drawPixmap(0, 0, mask)

        painter.end()
        self.setPixmap(pm)
