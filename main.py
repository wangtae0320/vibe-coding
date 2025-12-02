# -*- coding: utf-8 -*-
"""PDF 문서 비교 GUI 프로그램 - 진입점"""

import sys
from PySide6.QtWidgets import QApplication
from views.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

