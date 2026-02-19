"""
ui/vault_screen.py
Main vault UI: file list, add/extract/delete, lock button.
"""

import time
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor


VAULT_STYLE = """
QWidget#VaultScreen {
    background: #1a1a2e;
}
QLabel#header_title {
    color: #e0e0ff;
    font-size: 20px;
    font-weight: bold;
}
QLabel#file_count {
    color: #7070b0;
    font-size: 13px;
}
QTableWidget {
    background: #16213e;
    color: #d0d0f0;
    border: 1px solid #2a2a60;
    border-radius: 8px;
    gridline-color: #2a2a60;
    font-size: 13px;
}
QTableWidget::item:selected {
    background: #2a2a80;
    color: #ffffff;
}
QHeaderView::section {
    background: #0f0f25;
    color: #8888cc;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #2a2a60;
    font-size: 12px;
    font-weight: bold;
    text-transform: uppercase;
}
QPushButton.action_btn {
    background: #252560;
    color: #c0c0ff;
    border: 1px solid #3535a0;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    min-width: 110px;
}
QPushButton.action_btn:hover {
    background: #3535a0;
    color: #ffffff;
}
QPushButton.action_btn:disabled {
    background: #1e1e40;
    color: #444480;
    border-color: #252550;
}
QPushButton#add_btn {
    background: #1a5c1a;
    color: #80ff80;
    border: 1px solid #2a8c2a;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    min-width: 110px;
}
QPushButton#add_btn:hover {
    background: #2a7c2a;
    color: #ffffff;
}
QPushButton#lock_btn {
    background: #5c1a1a;
    color: #ff8080;
    border: 1px solid #8c2a2a;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    min-width: 80px;
    font-weight: bold;
}
QPushButton#lock_btn:hover {
    background: #7c2a2a;
    color: #ffffff;
}
QLabel#status_bar {
    color: #6060a0;
    font-size: 12px;
    padding: 4px 8px;
}
QLabel.usb_ok {
    color: #00e676;
    font-size: 12px;
}
QLabel.usb_warn {
    color: #ff9800;
    font-size: 12px;
}
"""

BYTES_UNITS = [(1 << 30, "GB"), (1 << 20, "MB"), (1 << 10, "KB"), (1, "B")]

def fmt_size(n: int) -> str:
    for div, unit in BYTES_UNITS:
        if n >= div:
            return f"{n/div:.1f} {unit}"
    return f"{n} B"


def fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


class VaultScreen(QWidget):
    """
    Signals:
        lock_requested()   – user clicked Lock
        add_file_requested(source_path: Path)
        extract_file_requested(vault_id: str, dest_dir: Path)
        delete_file_requested(vault_id: str)
    """

    lock_requested = pyqtSignal()
    add_file_requested = pyqtSignal(Path)
    extract_file_requested = pyqtSignal(str, Path)
    delete_file_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("VaultScreen")
        self._vault_ids: list[str] = []
        self._build_ui()
        self.setStyleSheet(VAULT_STYLE)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────
        header = QHBoxLayout()

        left = QVBoxLayout()
        title = QLabel("🔐 Privexi")
        title.setObjectName("header_title")
        self.file_count_lbl = QLabel("0 files stored")
        self.file_count_lbl.setObjectName("file_count")
        left.addWidget(title)
        left.addWidget(self.file_count_lbl)

        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.usb_indicator = QLabel("✅ USB Connected")
        self.usb_indicator.setProperty("class", "usb_ok")
        self.usb_indicator.setStyleSheet("color: #00e676; font-size: 12px;")
        self.lock_btn = QPushButton("🔒 Lock")
        self.lock_btn.setObjectName("lock_btn")
        self.lock_btn.clicked.connect(self.lock_requested.emit)
        right.addWidget(self.usb_indicator)
        right.addWidget(self.lock_btn)

        header.addLayout(left)
        header.addStretch()
        header.addLayout(right)
        layout.addLayout(header)

        # ── Separator ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2a2a50;")
        layout.addWidget(sep)

        # ── File Table ────────────────────────────────────────────
        self.table = QTableWidget(0, 3)
        self.table.setObjectName("file_table")
        self.table.setHorizontalHeaderLabels(["File Name", "Size", "Added"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(True)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_change)
        layout.addWidget(self.table)

        # ── Action Buttons ────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.add_btn = QPushButton("➕ Add File")
        self.add_btn.setObjectName("add_btn")
        self.add_btn.clicked.connect(self._on_add)

        self.extract_btn = QPushButton("📤 Extract")
        self.extract_btn.setProperty("class", "action_btn")
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self._on_extract)

        self.delete_btn = QPushButton("🗑 Delete")
        self.delete_btn.setProperty("class", "action_btn")
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self._on_delete)

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.extract_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addStretch()

        layout.addLayout(btn_row)

        # ── Status Bar ────────────────────────────────────────────
        self.status_bar = QLabel("Vault unlocked.")
        self.status_bar.setObjectName("status_bar")
        layout.addWidget(self.status_bar)

    # ─── Public API ───────────────────────────────────────────────────────────

    def populate_files(self, entries: list[dict]):
        """Fill the table from a list of vault entries."""
        self._vault_ids = []
        self.table.setRowCount(0)

        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._vault_ids.append(entry["vault_id"])

            name_item = QTableWidgetItem(entry["original_name"])
            size_item = QTableWidgetItem(fmt_size(entry["size_bytes"]))
            date_item = QTableWidgetItem(fmt_time(entry["added_at"]))

            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, size_item)
            self.table.setItem(row, 2, date_item)

        count = len(entries)
        self.file_count_lbl.setText(f"{count} file{'s' if count != 1 else ''} stored")

    def set_usb_status(self, connected: bool):
        if connected:
            self.usb_indicator.setText("✅ USB Connected")
            self.usb_indicator.setStyleSheet("color: #00e676; font-size: 12px;")
        else:
            self.usb_indicator.setText("⚠ USB Removed!")
            self.usb_indicator.setStyleSheet("color: #ff5252; font-size: 12px;")

    def set_status(self, msg: str, color: str = "#6060a0"):
        self.status_bar.setText(msg)
        self.status_bar.setStyleSheet(f"color: {color}; font-size: 12px; padding: 4px 8px;")

    # ─── Slots ────────────────────────────────────────────────────────────────

    def _on_selection_change(self):
        has_selection = bool(self.table.selectedItems())
        self.extract_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _selected_vault_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._vault_ids):
            return None
        return self._vault_ids[row]

    def _on_add(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file to add to vault")
        if path:
            self.add_file_requested.emit(Path(path))

    def _on_extract(self):
        vault_id = self._selected_vault_id()
        if not vault_id:
            return
        dest = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if dest:
            self.extract_file_requested.emit(vault_id, Path(dest))

    def _on_delete(self):
        vault_id = self._selected_vault_id()
        if not vault_id:
            return
        row = self.table.currentRow()
        fname = self.table.item(row, 0).text() if row >= 0 else vault_id

        reply = QMessageBox.question(
            self,
            "Delete File",
            f"Permanently delete '{fname}' from the vault?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.delete_file_requested.emit(vault_id)
