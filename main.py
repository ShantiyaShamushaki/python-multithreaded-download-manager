from PyQt6.QtWidgets import QApplication
from src.gui import DownloadGUI
import sys

def main():
    app = QApplication(sys.argv)
    window = DownloadGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
