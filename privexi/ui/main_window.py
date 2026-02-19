"""
ui/main_window.py
Main window: orchestrates login screen, vault screen, USB monitoring,
authentication, auto-lock, and brute-force protection.
"""

from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QSystemTrayIcon, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QCloseEvent, QIcon, QAction

from privexi.login_screen import LoginScreen
from privexi.vault_screen import VaultScreen
from privexi.setup_dialog import SetupDialog
from privexi.usb_monitor import USBMonitor
from privexi.encryption import VaultCrypto
from privexi.vault_manager import VaultManager
from privexi.security_log import log_event, log_warning, log_failure

# ─── Config ────────────────────────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
AUTO_LOCK_SECONDS = 300
LOCKOUT_SECONDS = 30

PAGE_LOGIN = 0
PAGE_VAULT = 1


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Privexi Secure Desktop Vault")
        self.setMinimumSize(720, 520)

        # State
        self._usb_path: Path | None = None
        self._vault_manager: VaultManager | None = None
        self._failed_attempts = 0
        self._locked_out = False

        # Auto-lock timer
        self._auto_lock_timer = QTimer(self)
        self._auto_lock_timer.setSingleShot(True)
        self._auto_lock_timer.timeout.connect(self._auto_lock)
        if AUTO_LOCK_SECONDS > 0:
            self._auto_lock_timer.setInterval(AUTO_LOCK_SECONDS * 1000)

        # UI
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        self._login_screen = LoginScreen()
        self._vault_screen = VaultScreen()

        self._stack.addWidget(self._login_screen)
        self._stack.addWidget(self._vault_screen)

        self._login_screen.unlock_requested.connect(self._on_unlock_requested)
        self._login_screen.setup_requested.connect(self._on_setup_requested)

        self._vault_screen.lock_requested.connect(self._lock_vault)
        self._vault_screen.add_file_requested.connect(self._on_add_file)
        self._vault_screen.extract_file_requested.connect(self._on_extract_file)
        self._vault_screen.delete_file_requested.connect(self._on_delete_file)

        # USB monitor
        self._usb_monitor = USBMonitor(
            on_connected=self._on_usb_connected,
            on_disconnected=self._on_usb_disconnected,
        )

        self._usb_check_timer = QTimer(self)
        self._usb_check_timer.setInterval(1000)
        self._usb_check_timer.timeout.connect(self._poll_usb)
        self._usb_check_timer.start()

        self._usb_monitor.start()

        self._stack.setCurrentIndex(PAGE_LOGIN)
        self._login_screen.set_usb_status(False)

        self._setup_tray()
        self.setStyleSheet("QMainWindow { background: #1a1a2e; }")

    # ─── Tray ────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(QIcon(), self)
        menu = QMenu(self)

        show_action = QAction("Show", self)
        quit_action = QAction("Quit", self)

        show_action.triggered.connect(self.showNormal)
        quit_action.triggered.connect(self.close)

        menu.addAction(show_action)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.setToolTip("Privexi Vault")
        self._tray.show()

    # ─── USB ────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _poll_usb(self):
        usb = self._usb_monitor.usb_path
        was_connected = self._usb_path is not None

        if usb and usb != self._usb_path:
            self._usb_path = usb
            self._on_usb_connected(usb)
        elif not usb and was_connected:
            self._usb_path = None
            self._on_usb_disconnected()

    def _on_usb_connected(self, path: Path):
        self._usb_path = path
        log_event("USB_CONNECTED", f"path={path}")
        self._login_screen.set_usb_status(True)
        if self._stack.currentIndex() == PAGE_VAULT:
            self._vault_screen.set_usb_status(True)

    def _on_usb_disconnected(self):
        log_warning("USB_REMOVED", "Auto-locking vault")
        self._usb_path = None
        self._login_screen.set_usb_status(False)
        if self._stack.currentIndex() == PAGE_VAULT:
            self._vault_screen.set_usb_status(False)
            self._lock_vault()

    # ─── Auth ────────────────────────────────────────────────────────────────

    @pyqtSlot(str, bool)
    def _on_unlock_requested(self, secret: str, is_recovery: bool):
        if self._locked_out:
            self._login_screen.show_error(f"Too many failures. Try again in {LOCKOUT_SECONDS}s.")
            return

        if not self._usb_path:
            self._login_screen.show_error("USB key not connected.")
            return

        from privexi.usb_key_manager import load_usb_key
        master_key = load_usb_key(self._usb_path, secret.strip(), is_recovery)

        if not master_key:
            self._failed_attempts += 1
            remaining = MAX_FAILED_ATTEMPTS - self._failed_attempts
            log_failure("AUTH_FAILURE", f"attempt={self._failed_attempts}")

            if self._failed_attempts >= MAX_FAILED_ATTEMPTS:
                self._trigger_lockout()
                return

            self._login_screen.show_error(f"Wrong password or recovery code. {remaining} left.")
            self._login_screen.clear_password()
            return

        self._failed_attempts = 0
        self._locked_out = False
        self._login_screen.clear_error()
        log_event("AUTH_SUCCESS")

        crypto = VaultCrypto(master_key)
        for i in range(len(master_key)):
            master_key[i] = 0

        self._vault_manager = VaultManager(crypto)
        self._login_screen.clear_password()
        self._switch_to_vault()

    def _trigger_lockout(self):
        self._locked_out = True
        log_failure("AUTH_LOCKOUT", f"duration={LOCKOUT_SECONDS}s")
        self._login_screen.show_error(f"Locked for {LOCKOUT_SECONDS}s.")
        QTimer.singleShot(LOCKOUT_SECONDS * 1000, self._end_lockout)

    def _end_lockout(self):
        self._locked_out = False
        self._failed_attempts = 0
        self._login_screen.clear_error()
        log_event("AUTH_LOCKOUT_EXPIRED")

    # ─── Vault ────────────────────────────────────────────────────────────────

    def _switch_to_vault(self):
        self._refresh_file_list()
        self._vault_screen.set_usb_status(True)
        self._stack.setCurrentIndex(PAGE_VAULT)
        self._auto_lock_timer.start()

    def _refresh_file_list(self):
        if self._vault_manager:
            self._vault_screen.populate_files(self._vault_manager.list_files())

    def _reset_auto_lock_timer(self):
        if self._stack.currentIndex() == PAGE_VAULT:
            self._auto_lock_timer.start()

    @pyqtSlot()
    def _lock_vault(self):
        self._auto_lock_timer.stop()
        if self._vault_manager:
            self._vault_manager.lock()
            self._vault_manager = None
        log_event("VAULT_LOCKED")
        self._stack.setCurrentIndex(PAGE_LOGIN)
        self._login_screen.set_usb_status(self._usb_path is not None)

    @pyqtSlot()
    def _auto_lock(self):
        log_event("AUTO_LOCK")
        self._lock_vault()

    # ─── File Ops ──────────────────────────────────────────────────────────────

    @pyqtSlot(Path)
    def _on_add_file(self, path: Path):
        self._reset_auto_lock_timer()
        if self._vault_manager and self._vault_manager.add_file(path, True):
            self._refresh_file_list()

    @pyqtSlot(str, Path)
    def _on_extract_file(self, vault_id: str, dest: Path):
        self._reset_auto_lock_timer()
        if self._vault_manager:
            self._vault_manager.extract_file(vault_id, dest)

    @pyqtSlot(str)
    def _on_delete_file(self, vault_id: str):
        self._reset_auto_lock_timer()
        if self._vault_manager and self._vault_manager.delete_file(vault_id):
            self._refresh_file_list()

    # ─── Setup ────────────────────────────────────────────────────────────────

    @pyqtSlot()
    def _on_setup_requested(self):
        SetupDialog(self).exec()

    # ─── Window Events ────────────────────────────────────────────────────────

    def closeEvent(self, event: QCloseEvent):
        self._usb_check_timer.stop()
        self._usb_monitor.stop()
        if self._vault_manager:
            self._vault_manager.lock()
        log_event("APP_CLOSED")
        event.accept()
