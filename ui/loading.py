from pathlib import Path

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QMovie
from qgis.PyQt.QtWidgets import QLabel


class LoadingSpinner:
    def __init__(self, parent=None):
        self.parent = parent

        self.label = QLabel(parent)
        self.label.setAlignment(Qt.AlignCenter)

        self.label.setFixedSize(80, 80)

        plugin_dir = Path(__file__).resolve().parent.parent
        spinner_path = plugin_dir / "assets" / "icons" / "spinner.gif"

        self.movie = QMovie(str(spinner_path))
        self.movie.setScaledSize(QSize(80, 80))

        self.label.setMovie(self.movie)
        self.label.setVisible(False)

    def show(self):
        if self.parent:
            x = (self.parent.width() - self.label.width()) // 2
            y = (self.parent.height() - self.label.height()) // 2
            self.label.move(x, y)

        self.label.raise_()
        self.movie.start()
        self.label.setVisible(True)

    def hide(self):
        self.movie.stop()
        self.label.setVisible(False)

    def is_visible(self):
        return self.label.isVisible()