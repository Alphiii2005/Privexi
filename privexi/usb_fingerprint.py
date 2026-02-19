"""
usb_fingerprint.py
Cross-platform USB device fingerprinting for secure vault authentication.
Linux: pyudev
Windows: pywin32 / WMI
"""

import sys
import hashlib
from pathlib import Path

IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform == "win32"


def get_usb_fingerprint(usb_path: Path) -> str:
    """
    Derive a stable fingerprint hash for the given USB device.
    Uses serial number, vendor ID, product ID, and UUID (if available).
    Returns a hex string fingerprint.
    """
    if IS_LINUX:
        return _linux_usb_fingerprint(usb_path)
    elif IS_WINDOWS:
        return _windows_usb_fingerprint(usb_path)
    else:
        raise NotImplementedError("Unsupported platform for USB fingerprinting.")


def _linux_usb_fingerprint(usb_path: Path) -> str:
    import pyudev, os
    context = pyudev.Context()
    # Find the device node for the mount point
    mount_path = os.path.realpath(str(usb_path))
    device_node = None
    with open('/proc/mounts', 'r') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and os.path.realpath(parts[1]) == mount_path:
                device_node = parts[0]
                break
    if not device_node:
        raise RuntimeError(f"Could not find device node for mount point: {usb_path}")
    # Remove partition number (e.g., /dev/sdb1 -> /dev/sdb)
    base_node = device_node
    if base_node[-1].isdigit():
        base_node = base_node.rstrip('0123456789')
    # Find the block device in pyudev
    device = None
    for dev in context.list_devices(subsystem='block'):
        if dev.device_node and dev.device_node.startswith(base_node):
            device = dev
            break
    if not device:
        raise RuntimeError("USB device not found for fingerprinting.")
    serial = device.get('ID_SERIAL_SHORT', '')
    vendor = device.get('ID_VENDOR_ID', '')
    product = device.get('ID_MODEL_ID', '')
    uuid = device.get('ID_FS_UUID', '')
    fingerprint_data = f"{serial}|{vendor}|{product}|{uuid}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()


def _windows_usb_fingerprint(usb_path: Path) -> str:
    try:
        import win32com.client
        wmi = win32com.client.Dispatch("WbemScripting.SWbemLocator")
        svc = wmi.ConnectServer('.', r'root\\cimv2')
        query = "SELECT * FROM Win32_DiskDrive WHERE InterfaceType='USB'"
        for disk in svc.ExecQuery(query):
            if usb_path.drive in disk.DeviceID:
                serial = getattr(disk, 'SerialNumber', '')
                vendor = getattr(disk, 'Manufacturer', '')
                product = getattr(disk, 'Model', '')
                uuid = getattr(disk, 'PNPDeviceID', '')
                fingerprint_data = f"{serial}|{vendor}|{product}|{uuid}"
                return hashlib.sha256(fingerprint_data.encode()).hexdigest()
    except Exception:
        pass
    raise RuntimeError("USB device not found for fingerprinting.")

