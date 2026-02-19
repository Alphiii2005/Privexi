"""
modules/usb_monitor.py
Cross-platform USB detection and monitoring.
Linux:   pyudev
Windows: win32api / wmic fallback
"""

import os
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional


# Support detection of .vault.key inside .SystemCache
from privexi.usb_key_manager import KEY_FILE_NAME



# ─── Platform Detection ────────────────────────────────────────────────────────

IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform == "win32"


def find_usb_with_key() -> Optional[Path]:
    """
    Scan all removable drives/USB mounts for a drive containing the vault key file.
    Returns the Path to the USB root, or None if not found.
    """
    candidates = _get_removable_drives()
    for drive in candidates:
        # Check for .vault.key at root (legacy) or inside .SystemCache (current)
        key_path_legacy = drive / KEY_FILE_NAME
        key_path_hidden = drive / KEY_FILE_NAME
        if key_path_hidden.exists() or key_path_legacy.exists():
            return drive
    return None


# ─── Drive Enumeration ─────────────────────────────────────────────────────────

def _get_removable_drives() -> list[Path]:
    """Return list of mounted removable drive root paths."""
    if IS_LINUX:
        return _linux_removable_drives()
    elif IS_WINDOWS:
        return _windows_removable_drives()
    else:
        return _fallback_drives()


def _linux_removable_drives() -> list[Path]:
    """
    On Linux, check /proc/mounts for removable block devices.
    Also checks common USB mount points.
    """
    drives = []
    common_mount_dirs = [Path("/media"), Path("/run/media"), Path("/mnt")]

    # Parse /proc/mounts for mounted partitions
    try:
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                device, mount_point = parts[0], parts[1]
                mount = Path(mount_point)

                # Check if this mount looks like a USB/removable device
                if _is_linux_removable(device, mount):
                    drives.append(mount)
    except Exception:
        pass

    # Also scan common user-mount directories
    for base in common_mount_dirs:
        if base.exists():
            for sub in base.iterdir():
                if sub.is_dir() and sub not in drives:
                    drives.append(sub)

    return drives


def _is_linux_removable(device: str, mount_point: Path) -> bool:
    """Heuristic: check if a Linux device is removable."""
    if not device.startswith("/dev/"):
        return False
    # Strip partition number to get base device (sdb1 -> sdb)
    base = device.replace("/dev/", "")
    base = base.rstrip("0123456789")
    removable_path = Path(f"/sys/block/{base}/removable")
    try:
        return removable_path.read_text().strip() == "1"
    except Exception:
        return False


def _windows_removable_drives() -> list[Path]:
    """Enumerate removable drives on Windows using win32api."""
    drives = []
    try:
        import win32api
        import win32con
        all_drives = win32api.GetLogicalDriveStrings().split("\x00")
        for drive in all_drives:
            if not drive:
                continue
            try:
                drive_type = win32api.GetDriveType(drive)
                # DRIVE_REMOVABLE = 2
                if drive_type == 2:
                    drives.append(Path(drive))
            except Exception:
                pass
    except ImportError:
        # Fallback: try wmic
        drives = _windows_wmic_drives()
    return drives


def _windows_wmic_drives() -> list[Path]:
    """Fallback Windows drive detection using wmic."""
    import subprocess
    drives = []
    try:
        result = subprocess.run(
            ["wmic", "logicaldisk", "where", "drivetype=2", "get", "deviceid"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if len(line) == 2 and line[1] == ":":
                drives.append(Path(line + "\\"))
    except Exception:
        pass
    return drives


def _fallback_drives() -> list[Path]:
    """Generic fallback: just check /media and /mnt."""
    drives = []
    for base in [Path("/media"), Path("/mnt")]:
        if base.exists():
            for sub in base.iterdir():
                if sub.is_dir():
                    drives.append(sub)
    return drives


# ─── USB Monitor Thread ────────────────────────────────────────────────────────

class USBMonitor(threading.Thread):
    """
    Background thread that polls for USB key presence every second.
    Calls on_connected(path) and on_disconnected() callbacks.
    """

    POLL_INTERVAL = 1.0  # seconds

    def __init__(
        self,
        on_connected: Callable[[Path], None],
        on_disconnected: Callable[[], None],
    ):
        super().__init__(daemon=True, name="USBMonitor")
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._stop_event = threading.Event()
        self._current_usb: Optional[Path] = None

    def run(self):
        while not self._stop_event.is_set():
            usb = find_usb_with_key()
            if usb and usb != self._current_usb:
                self._current_usb = usb
                self._on_connected(usb)
            elif not usb and self._current_usb is not None:
                self._current_usb = None
                self._on_disconnected()
            time.sleep(self.POLL_INTERVAL)

    def stop(self):
        self._stop_event.set()

    @property
    def usb_path(self) -> Optional[Path]:
        return self._current_usb
