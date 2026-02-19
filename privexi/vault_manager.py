"""
modules/vault_manager.py
Manages the encrypted file vault: add, list, extract, delete vault entries.
Each file is stored as:  <vault_dir>/<sha256_of_original_name>.enc
An encrypted index maps original filenames -> vault filenames.
"""

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Optional

from privexi.encryption import (
    VaultCrypto,
    VAULT_DIR,
    VAULT_INDEX,
    secure_delete,
    ensure_vault_dir,
    get_file_integrity_hash,
)


# ─── Index Format ──────────────────────────────────────────────────────────────
# The index is an encrypted JSON dict:
# {
#   "vault_id": {
#     "original_name": "document.pdf",
#     "vault_file": "a3f2c1....enc",
#     "added_at": 1700000000.0,
#     "size_bytes": 12345,
#     "sha256": "abc123..."
#   },
#   ...
# }


class VaultManager:
    """High-level API for interacting with the encrypted vault."""

    def __init__(self, crypto: VaultCrypto):
        self._crypto = crypto
        ensure_vault_dir()
        self._index: dict = self._load_index()

    # ─── Index ─────────────────────────────────────────────────────────────────

    def _index_path(self) -> Path:
        return VAULT_INDEX

    def _load_index(self) -> dict:
        """Load and decrypt the vault index. Returns empty dict if missing."""
        idx_path = self._index_path()
        if not idx_path.exists():
            return {}
        try:
            ciphertext = idx_path.read_bytes()
            plaintext = self._crypto.decrypt_file(ciphertext)
            if plaintext is None:
                print("[VAULT] Warning: Could not decrypt index (wrong key?)")
                return {}
            return json.loads(plaintext.decode("utf-8"))
        except Exception as e:
            print(f"[VAULT] Index load error: {e}")
            return {}

    def _save_index(self):
        """Encrypt and write the vault index."""
        plaintext = json.dumps(self._index, indent=2).encode("utf-8")
        ciphertext = self._crypto.encrypt_file(plaintext)
        self._index_path().write_bytes(ciphertext)

    # ─── Core Operations ───────────────────────────────────────────────────────

    def add_file(
        self,
        source_path: Path,
        secure_wipe_original: bool = True,
    ) -> bool:
        """
        Encrypt and add a file to the vault.
        Optionally securely delete the original.
        Returns True on success.
        """
        try:
            plaintext = source_path.read_bytes()
            sha256 = get_file_integrity_hash(plaintext)
            ciphertext = self._crypto.encrypt_file(plaintext)

            # Generate vault filename from hash of original name + timestamp
            vault_stem = hashlib.sha256(
                f"{source_path.name}{time.time()}".encode()
            ).hexdigest()
            vault_file = VAULT_DIR / f"{vault_stem}.enc"
            vault_file.write_bytes(ciphertext)

            # Record in index
            vault_id = vault_stem[:16]
            self._index[vault_id] = {
                "original_name": source_path.name,
                "vault_file": vault_file.name,
                "added_at": time.time(),
                "size_bytes": len(plaintext),
                "sha256": sha256,
            }
            self._save_index()

            if secure_wipe_original:
                secure_delete(source_path)

            return True

        except Exception as e:
            print(f"[VAULT] Add error: {e}")
            return False

    def list_files(self) -> list[dict]:
        """
        Return a list of vault entries with metadata.
        Each entry: { vault_id, original_name, added_at, size_bytes }
        """
        results = []
        for vault_id, meta in self._index.items():
            # Verify vault file still exists
            vault_file = VAULT_DIR / meta["vault_file"]
            if vault_file.exists():
                results.append({
                    "vault_id": vault_id,
                    "original_name": meta["original_name"],
                    "added_at": meta["added_at"],
                    "size_bytes": meta["size_bytes"],
                    "sha256": meta.get("sha256", ""),
                })
        # Sort by most recently added
        results.sort(key=lambda x: x["added_at"], reverse=True)
        return results

    def extract_file(self, vault_id: str, destination_dir: Path) -> Optional[Path]:
        """
        Decrypt and extract a vault file to destination_dir.
        Returns the output Path on success, None on failure.
        Also verifies SHA-256 integrity before writing.
        """
        meta = self._index.get(vault_id)
        if not meta:
            print(f"[VAULT] Entry {vault_id} not found in index")
            return None

        vault_file = VAULT_DIR / meta["vault_file"]
        if not vault_file.exists():
            print(f"[VAULT] Vault file missing: {vault_file}")
            return None

        try:
            ciphertext = vault_file.read_bytes()
            plaintext = self._crypto.decrypt_file(ciphertext)
            if plaintext is None:
                print("[VAULT] Decryption failed — file may be corrupted")
                return None

            # Integrity check
            actual_hash = get_file_integrity_hash(plaintext)
            expected_hash = meta.get("sha256", "")
            if expected_hash and actual_hash != expected_hash:
                print("[VAULT] INTEGRITY CHECK FAILED — file tampered!")
                return None

            out_path = destination_dir / meta["original_name"]
            # Avoid overwrite collision
            counter = 1
            stem = out_path.stem
            suffix = out_path.suffix
            while out_path.exists():
                out_path = destination_dir / f"{stem}_{counter}{suffix}"
                counter += 1

            out_path.write_bytes(plaintext)
            return out_path

        except Exception as e:
            print(f"[VAULT] Extract error: {e}")
            return None

    def delete_file(self, vault_id: str) -> bool:
        """Permanently delete a file from the vault."""
        meta = self._index.get(vault_id)
        if not meta:
            return False

        vault_file = VAULT_DIR / meta["vault_file"]
        if vault_file.exists():
            secure_delete(vault_file)

        del self._index[vault_id]
        self._save_index()
        return True

    def lock(self):
        """Lock the vault by wiping the crypto engine."""
        self._crypto.wipe()
        self._index = {}

    def file_count(self) -> int:
        return len(self._index)
