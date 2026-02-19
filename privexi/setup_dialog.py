from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QHBoxLayout, QMessageBox
)
from PyQt6.QtCore import Qt

from privexi.usb_key_manager import create_usb_key, KEY_FILE_NAME

SETUP_STYLE = """
QDialog { background: #1a1a2e; }
QLabel { color: #c0c0e0; font-size: 13px; }
QLabel#title { color: #e0e0ff; font-size: 18px; font-weight: bold; }
QLineEdit { background: #16213e; color: #e0e0ff; border: 1px solid #3030a0; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
QLineEdit:focus { border-color: #7070ff; }
QPushButton { background: #3030a0; color: #ffffff; border: none; border-radius: 6px; padding: 9px 18px; font-size: 13px; }
QPushButton:hover { background: #4040c0; }
QPushButton#browse_btn { background: #252560; padding: 9px 12px; }
"""


class SetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Initialize USB Key")
        self.setMinimumWidth(440)
        self.setStyleSheet(SETUP_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)

        title = QLabel("🔑 Initialize USB Security Key")
        title.setObjectName("title")

        instructions = QLabel(
            "This will create an encrypted key file on your USB drive.\n"
            "You will need this USB drive AND your password or recovery code to access the vault."
        )
        instructions.setWordWrap(True)

        usb_label = QLabel("USB Drive Path:")
        path_row = QHBoxLayout()
        self.usb_path_input = QLineEdit()
        self.usb_path_input.setPlaceholderText("/media/username/MyUSB or D:\\")
        browse_btn = QPushButton("Browse")
        browse_btn.setObjectName("browse_btn")
        browse_btn.clicked.connect(self._browse_usb)
        path_row.addWidget(self.usb_path_input)
        path_row.addWidget(browse_btn)

        pw_label = QLabel("Set Vault Password:")
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw_input.setPlaceholderText("Choose a strong password…")

        pw2_label = QLabel("Confirm Password:")
        self.pw2_input = QLineEdit()
        self.pw2_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw2_input.setPlaceholderText("Repeat password…")

        self.error_lbl = QLabel("")
        self.error_lbl.setStyleSheet("color: #ff5252;")
        self.error_lbl.hide()

        init_btn = QPushButton("Initialize USB Key")
        init_btn.clicked.connect(self._on_init)

        layout.addWidget(title)
        layout.addWidget(instructions)
        layout.addSpacing(6)
        layout.addWidget(usb_label)
        layout.addLayout(path_row)
        layout.addWidget(pw_label)
        layout.addWidget(self.pw_input)
        layout.addWidget(pw2_label)
        layout.addWidget(self.pw2_input)
        layout.addWidget(self.error_lbl)
        layout.addWidget(init_btn)

    def _browse_usb(self):
        path = QFileDialog.getExistingDirectory(self, "Select USB Drive Root")
        if path:
            self.usb_path_input.setText(path)

    def _on_init(self):
        usb_path = self.usb_path_input.text().strip()
        password = self.pw_input.text()
        password2 = self.pw2_input.text()

        if not usb_path or not Path(usb_path).exists():
            self._show_error("Please select a valid USB drive path.")
            return
        if not password:
            self._show_error("Password cannot be empty.")
            return
        if password != password2:
            self._show_error("Passwords do not match.")
            return
        if len(password) < 8:
            self._show_error("Password must be at least 8 characters.")
            return

        key_file = Path(usb_path) / KEY_FILE_NAME
        if key_file.exists():
            reply = QMessageBox.question(
                self,
                "Overwrite USB Key?",
                f"A vault key already exists at:\n{key_file}\n\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                key_file.unlink()
            except Exception:
                self._show_error("Could not delete old key file.")
                return

        recovery_code = create_usb_key(Path(usb_path), password)

        if recovery_code:
            QMessageBox.warning(
                self,
                "⚠️ SAVE YOUR RECOVERY CODE",
                f"This recovery code will be shown ONCE:\n\n{recovery_code}"
            )
            QMessageBox.information(
                self,
                "USB Key Initialized",
                f"USB key initialized successfully at {key_file}.\nKeep this USB drive safe."
            )
            self.accept()
        else:
            self._show_error("Failed to write key file. Check permissions.")

    def _show_error(self, msg: str):
        self.error_lbl.setText(f"⚠ {msg}")
        self.error_lbl.show()
