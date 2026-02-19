"""
Secure Desktop Vault - Main Entry Point
Requires: PyQt6, cryptography, pyudev (Linux), pywin32 (Windows)
"""

import sys
import os


from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from privexi.ui.main_window import MainWindow


def main():
    # High-DPI support
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("SecureVault")
    app.setOrganizationName("SecureVaultApp")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
