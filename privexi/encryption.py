import os
import secrets
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet, InvalidToken
import base64

PBKDF2_ITERATIONS = 480_000
SALT_SIZE = 32
KEY_FILE_NAME = ".vault.key"
VAULT_DIR = Path.home() / ".secure_vault"
VAULT_INDEX = VAULT_DIR / ".vault_index"



def derive_key(secret: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(secret.encode("utf-8"))


def generate_fernet_key(raw_key: bytes) -> bytes:
    return base64.urlsafe_b64encode(raw_key)


def generate_recovery_code() -> str:
    raw = secrets.token_bytes(16)
    return base64.b32encode(raw).decode("utf-8").replace("=", "")



# ─── Rest of your file stays unchanged ─────────────────────────────────────────

def get_file_integrity_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VaultCrypto:
    def __init__(self, master_key: bytes):
        fernet_key = generate_fernet_key(master_key)
        self._fernet = Fernet(fernet_key)

    def encrypt_file(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt_file(self, ciphertext: bytes) -> bytes | None:
        try:
            return self._fernet.decrypt(ciphertext)
        except (InvalidToken, Exception):
            return None

    def wipe(self):
        self._fernet = None


def secure_delete(path: Path, passes: int = 3):
    try:
        size = path.stat().st_size
        with open(path, "r+b") as f:
            for _ in range(passes):
                f.seek(0)
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())
        path.unlink()
    except Exception as e:
        print(f"[SECURE DELETE WARNING] {e}")
        try:
            path.unlink()
        except Exception:
            pass


def ensure_vault_dir():
    VAULT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
