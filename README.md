# 🔐 Privexi – Secure USB Desktop Vault

Privexi is a secure desktop vault application that unlocks only when a trusted **USB key** is inserted *and* the correct **password or recovery key** is provided. Your files remain encrypted on disk and are automatically locked the moment the USB is removed.

---

## ✨ Features

- 🔑 **2-Factor Unlock** – USB key + password or recovery key
- 🔐 **Strong encryption** – Fernet (AES-128 + HMAC-SHA256)
- 🧠 **Password-based key derivation** – PBKDF2-HMAC-SHA256 (480,000 iterations)
- 🔌 **USB removal auto-lock** – vault locks instantly when USB is removed
- ⏱ **Auto-lock timer** – locks after configurable inactivity period
- 🛡 **Brute-force protection** – lockout after repeated failed attempts
- 🧹 **Secure delete** – original files overwritten before removal
- 📁 **Encrypted index** – filenames stored encrypted
- 🧾 **Security event logging** – audit trail with no secrets recorded
- 🖥 **Cross-platform** – Linux & Windows

---

## 📦 Installation

```bash
# Clone the project
git clone https://github.com/YOUR_USERNAME/privexi.git
cd privexi

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
.venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

**Platform extras:**

```bash
# Linux
pip install pyudev

# Windows
pip install pywin32
```

---

## 🚀 First-Time Setup

### Step 1 – Initialize Your USB Key

1. Insert a USB drive
2. Run the application:
   ```bash
   python -m privexi.main
   ```
3. Click **"First time? Initialize USB key"**
4. Select your USB root path (e.g. `/media/user/MyUSB` or `E:\`)
5. Create a **password** and a **recovery key**
6. Click **Initialize**

This writes an encrypted key file to the USB drive.

> ⚠️ **Warning:** If you lose both your USB drive *and* your password + recovery key, your vault is **permanently unrecoverable**. Store your recovery key somewhere safe.

---

## 🔓 Unlocking the Vault

1. Insert the USB drive
2. Launch the application
3. Wait for the USB status indicator to turn **green ✅**
4. Enter either your **password** or your **recovery key**
5. Click **Unlock Vault**

---

## 🗂 Usage

| Action | How |
|--------|-----|
| Add a file | Click **➕ Add File** and choose a file |
| Extract a file | Click **📤 Extract** and choose a destination |
| Delete a file | Click **🗑 Delete** |
| Lock the vault | Click **🔒 Lock**, remove the USB, or wait for auto-lock |

---

## 🧠 How It Works

```
Password / Recovery Key
        │
        ▼
PBKDF2-HMAC-SHA256 (480,000 iterations)
        │
        ▼
Encrypted USB key file ──► Decrypts master key
                                   │
                                   ▼
                       Fernet (AES-128 + HMAC-SHA256)
                        Encrypts each file separately
```

- The master key is **never stored in plaintext**
- The USB alone is **useless** without your password or recovery key
- **Filenames are encrypted**
- Wrong credentials produce no exploitable oracle

---

## 📁 File Locations

| Location | Purpose |
|----------|---------|
| User vault directory | Encrypted vault files |
| USB drive — `.vault.key` | Encrypted master key |
| Security log | Audit trail (no secrets stored) |

---

## ⚙️ Configuration

Edit `privexi/ui/main_window.py` to adjust behaviour:

```python
MAX_FAILED_ATTEMPTS = 5
AUTO_LOCK_SECONDS   = 300   # 0 = disabled
LOCKOUT_SECONDS     = 30
```

---

## 🪟 Building a Windows EXE

> ℹ️ The EXE must be built on a Windows machine or VM.

```bash
pip install pyinstaller
pyinstaller --onefile --windowed -n privexi privexi/main.py
```

The compiled binary will be located at `dist/privexi.exe`.

---

## ⚠️ Security Warnings

- **Secure deletion is best-effort.** SSDs and copy-on-write filesystems (e.g. Btrfs, APFS) may ignore overwrite attempts.
- **Python cannot guarantee memory wiping.** Sensitive values may persist in RAM briefly.
- Privexi protects against **casual access**, not live-memory forensic attacks.
- **Always keep backups outside of Privexi.** The vault is not a backup solution.

---

## 📄 License

See [LICENSE](LICENSE) for details.