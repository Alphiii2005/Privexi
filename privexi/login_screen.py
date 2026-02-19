"""
ui/login_screen.py
Login screen: USB status indicator + password or recovery code.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal


STYLE_LOCKED = """
QWidget#LoginScreen {
    background: #1a1a2e;
}
QLabel#title {
    color: #e0e0ff;
    font-size: 26px;
    font-weight: bold;
}
QLabel#subtitle {
    color: #7070a0;
    font-size: 13px;
}
QLabel#usb_status {
    font-size: 14px;
    padding: 8px 16px;
    border-radius: 8px;
}
QLineEdit#password_input {
    background: #16213e;
    color: #e0e0ff;
    border: 1px solid #3030a0;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 15px;
}
QPushButton#unlock_btn {
    background: #3030a0;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 11px;
    font-size: 15px;
    font-weight: bold;
}
QPushButton#unlock_btn:hover {
    background: #4040c0;
}
QPushButton#unlock_btn:disabled {
    background: #222240;
    color: #555580;
}
QLabel#error_label {
    color: #ff5252;
    font-size: 13px;
}
QPushButton#setup_btn {
    background: transparent;
    color: #5555aa;
    border: none;
    font-size: 12px;
    text-decoration: underline;
}
QPushButton#setup_btn:hover {
    color: #8888cc;
}
"""


class LoginScreen(QWidget):
    """Emits unlock_requested(secret: str, is_recovery: bool)."""

    unlock_requested = pyqtSignal(str, bool)
    setup_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("LoginScreen")
        self._usb_connected = False
        self._build_ui()
        self.setStyleSheet(STYLE_LOCKED)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(20)

        title_lbl = QLabel("🔐 Privexi")
        title_lbl.setObjectName("title")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Your personal encrypted vault")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.usb_label = QLabel("⬤  Checking USB...")
        self.usb_label.setObjectName("usb_status")
        self.usb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pw_input = QLineEdit()
        self.pw_input.setObjectName("password_input")
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Enter vault password…")
        self.pw_input.returnPressed.connect(self._on_unlock_password)

        self.error_label = QLabel("")
        self.error_label.setObjectName("error_label")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.hide()

        self.unlock_btn = QPushButton("Unlock Vault")
        self.unlock_btn.setObjectName("unlock_btn")
        self.unlock_btn.setEnabled(False)
        self.unlock_btn.clicked.connect(self._on_unlock_password)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a50;")

        self.setup_btn = QPushButton("First time? Initialize USB key →")
        self.setup_btn.setObjectName("setup_btn")
        self.setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setup_btn.clicked.connect(self.setup_requested.emit)

        self.forgot_btn = QPushButton("Forgot password? Use recovery code →")
        self.forgot_btn.setObjectName("setup_btn")
        self.forgot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forgot_btn.clicked.connect(self._on_recovery_unlock)

        layout.addStretch()
        layout.addWidget(title_lbl)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.usb_label)
        layout.addWidget(self.pw_input)
        layout.addWidget(self.error_label)
        layout.addWidget(self.unlock_btn)
        layout.addSpacing(10)
        layout.addWidget(sep)
        layout.addWidget(self.setup_btn)
        layout.addWidget(self.forgot_btn)
        layout.addStretch()

    def set_usb_status(self, connected: bool):
        self._usb_connected = connected
        if connected:
            self.usb_label.setText("✅  USB Security Key: Connected")
            self.usb_label.setStyleSheet(
                "color: #00e676; background: #003320; border: 1px solid #00e676;"
                "border-radius: 8px; padding: 8px 16px; font-size: 14px;"
            )
            self.unlock_btn.setEnabled(True)
            self.pw_input.setEnabled(True)
        else:
            self.usb_label.setText("❌  Insert your USB Security Key")
            self.usb_label.setStyleSheet(
                "color: #ff5252; background: #330000; border: 1px solid #ff5252;"
                "border-radius: 8px; padding: 8px 16px; font-size: 14px;"
            )
            self.unlock_btn.setEnabled(False)
            self.pw_input.setEnabled(False)

    def show_error(self, msg: str):
        self.error_label.setText(f"⚠ {msg}")
        self.error_label.show()

    def clear_error(self):
        self.error_label.hide()
        self.error_label.setText("")

    def clear_password(self):
        self.pw_input.clear()

    def _on_unlock_password(self):
        if not self._usb_connected:
            self.show_error("USB key not connected.")
            return
        password = self.pw_input.text()
        if not password:
            self.show_error("Please enter your password.")
            return
        self.clear_error()
        self.unlock_requested.emit(password, False)

    def _on_recovery_unlock(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox

        if not self._usb_connected:
            QMessageBox.warning(self, "USB Required", "Insert your USB key first.")
            return

        code, ok = QInputDialog.getText(
            self,
            "Recovery Code",
            "Enter your recovery code:",
            QLineEdit.EchoMode.Normal,
        )

        if ok and code:
            self.clear_error()
            self.unlock_requested.emit(code.strip(), True)
