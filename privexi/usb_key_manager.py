import os
import secrets
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

KEY_FILE_NAME = ".vault.key"

VERSION = b"\x03"
VERSION_SIZE = 1

SALT_SIZE = 32
AES_KEY_SIZE = 32
TAG_SIZE = 32
NONCE_SIZE = 12
PBKDF2_ITERATIONS = 480_000


def derive_key(secret: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend(),
    ).derive(secret.encode())


def create_usb_key(usb_path: Path, password: str) -> str | None:
    try:
        print("[DEBUG] Creating key on USB:", usb_path)

        salt_pw = secrets.token_bytes(SALT_SIZE)
        salt_recovery = secrets.token_bytes(SALT_SIZE)
        nonce = secrets.token_bytes(NONCE_SIZE)

        master_key = secrets.token_bytes(AES_KEY_SIZE)
        recovery_code = secrets.token_urlsafe(12)[:16].upper()

        key_pw = derive_key(password, salt_pw)
        key_recovery = derive_key(recovery_code, salt_recovery)

        aes_pw = AESGCM(key_pw)
        aes_recovery = AESGCM(key_recovery)

        payload = VERSION + master_key
        ct_pw = aes_pw.encrypt(nonce, payload, salt_pw)
        ct_recovery = aes_recovery.encrypt(nonce, payload, salt_recovery)

        blob = (
            VERSION +
            salt_pw +
            salt_recovery +
            nonce +
            len(ct_pw).to_bytes(2, "big") +
            ct_pw +
            ct_recovery
        )

        key_file = usb_path / KEY_FILE_NAME
        key_file.write_bytes(blob)
        print("[DEBUG] Key file written:", key_file)

        if os.name == "nt":
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(key_file), 0x02)

        return recovery_code

    except Exception as e:
        print("[DEBUG] ❌ create_usb_key error:", repr(e))
        return None


def load_usb_key(usb_path: Path, secret: str, is_recovery: bool) -> bytearray | None:
    key_file = usb_path / KEY_FILE_NAME
    print("[DEBUG] USB path:", usb_path)
    print("[DEBUG] Looking for key file:", key_file)

    if not key_file.exists():
        print("[DEBUG] ❌ Key file not found")
        return None

    try:
        data = key_file.read_bytes()
        version = data[0:1]

        if version != VERSION:
            print("[DEBUG] ❌ Version mismatch")
            return None

        off = 1
        salt_pw = data[off:off + SALT_SIZE]
        off += SALT_SIZE
        salt_recovery = data[off:off + SALT_SIZE]
        off += SALT_SIZE
        nonce = data[off:off + NONCE_SIZE]
        off += NONCE_SIZE

        ct_len = int.from_bytes(data[off:off + 2], "big")
        off += 2
        ct_pw = data[off:off + ct_len]
        ct_recovery = data[off + ct_len:]

        salt = salt_recovery if is_recovery else salt_pw
        ciphertext = ct_recovery if is_recovery else ct_pw

        key = derive_key(secret, salt)
        aesgcm = AESGCM(key)

        payload = aesgcm.decrypt(nonce, ciphertext, salt)
        if not payload.startswith(VERSION):
            print("[DEBUG] ❌ Payload version mismatch")
            return None

        master_key = payload[1:1 + AES_KEY_SIZE]
        print("[DEBUG] ✅ Vault unlocked")
        return bytearray(master_key)

    except Exception as e:
        print("[DEBUG] ❌ load_usb_key error:", repr(e))
        return None
