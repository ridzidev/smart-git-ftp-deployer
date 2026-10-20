"""Transport FTP/FTPS: koneksi, unggah, dan penghapusan berkas di server."""
import ftplib
import os
import threading
from pathlib import Path

from .config import log_queue, resolve_remote_path

class FTPDeployer:

    # ---------- __init__ ----------
    def __init__(self, config, abort_event=None):
        self.host = config["FTP_HOST"]
        self.user = config["FTP_USER"]
        self.password = config["FTP_PASS"]
        self.tls = bool(config.get("FTP_TLS", False))
        self.local_dir = Path(config["LOCAL_DIR"]).resolve()
        self.remote_dir_base = config["REMOTE_DIR"]
        self.mappings = config.get("PATH_MAPPINGS", [])
        self.abort_event = abort_event or threading.Event()
        self.ftp = None

    # ---------- _log ----------
    def _log(self, message):
        log_queue.put(message)

    # ---------- connect ----------
    def connect(self):
        try:
            proto = "FTPS (TLS)" if self.tls else "FTP"
            self._log(f"[INFO] Menghubungkan ke {self.host} ({proto})...")
            if self.tls:
                self.ftp = ftplib.FTP_TLS(self.host, timeout=30)
                self.ftp.login(self.user, self.password)
                self.ftp.prot_p()
            else:
                self.ftp = ftplib.FTP(self.host, timeout=30)
                self.ftp.login(self.user, self.password)
            self.ftp.set_pasv(True)
            self._log("[OK] Terhubung (Passive Mode).")
            try:
                self.ftp.cwd(self.remote_dir_base)
            except Exception:
                self._log(f"[WARN] Direktori {self.remote_dir_base} tidak ditemukan, tetap di root.")
            return True
        except Exception as e:
            self._log(f"[ERROR] Koneksi FTP gagal: {e}")
            return False

    # ---------- disconnect ----------
    def disconnect(self):
        if self.ftp:
            try:
                self.ftp.quit()
            except Exception:
                pass
            self.ftp = None

    # ---------- ensure_remote_dir ----------
    def ensure_remote_dir(self, remote_file_path):
        parent_dir = Path(remote_file_path).parent.as_posix()
        if parent_dir in [".", "/", ""]:
            return
        parts = parent_dir.split("/")
        current = ""
        for part in parts:
            if not part:
                continue
            current += "/" + part
            try:
                self.ftp.mkd(current)
            except Exception:
                pass

    # ---------- upload_file ----------
    def upload_file(self, local_rel_path):
        if self.abort_event.is_set():
            return False

        local_abs = self.local_dir / local_rel_path
        if not local_abs.is_file():
            self._log(f"[WARN] Berkas lokal tidak ditemukan: {local_rel_path}")
            return False

        final_remote_path = resolve_remote_path(local_rel_path, self.mappings)
        filesize = os.path.getsize(local_abs)
        uploaded_bytes = 0
        last_percent = -1

        def chunk_callback(data):
            nonlocal uploaded_bytes, last_percent
            if self.abort_event.is_set():
                raise InterruptedError("Dibatalkan pengguna.")
            uploaded_bytes += len(data)
            percent = int((uploaded_bytes / filesize) * 100) if filesize > 0 else 100
            if percent % 25 == 0 and percent != last_percent:
                self._log(f"[PROGRESS] {percent}%: {local_rel_path}")
                last_percent = percent

        self._log(f"[UPLOAD] Mengunggah: {local_rel_path} ({filesize / 1024 / 1024:.2f} MB)")
        try:
            self.ensure_remote_dir(final_remote_path)
            with open(local_abs, "rb") as f:
                self.ftp.storbinary(f"STOR {final_remote_path}", f, callback=chunk_callback)
            return True
        except InterruptedError:
            self._log(f"[WARN] Unggah berkas dibatalkan: {local_rel_path}")
            return False
        except Exception as e:
            self._log(f"[ERROR] Gagal mengunggah {final_remote_path}: {e}")
            return False

    # ---------- delete_file ----------
    def delete_file(self, local_rel_path):
        if self.abort_event.is_set():
            return False
        final_remote_path = resolve_remote_path(local_rel_path, self.mappings)
        self._log(f"[DELETE] Menghapus: {final_remote_path}")
        try:
            self.ftp.delete(final_remote_path)
            return True
        except Exception as e:
            self._log(f"[WARN] Gagal menghapus {final_remote_path}: {e}")
            return False
