"""Konfigurasi aplikasi: nilai bawaan, penyimpanan profil terenkripsi, utilitas jalur."""
import json
import os
from pathlib import Path
from queue import Queue

from .secure_store import FORMAT_BRAKAS, buka_brankas, dokumen_brankas, GagalBrankas

APP_VERSION = "2.7"


CONFIG_FILENAME = "deploy_config.json"


DEFAULT_CONFIG = {
    "FTP_HOST": "",
    "FTP_USER": "",
    "FTP_PASS": "",
    "FTP_TLS": False,
    "LOCAL_DIR": ".",
    "REMOTE_DIR": "/",
    "EXCLUDE_PATTERNS": [
        "*.git*", ".env", "node_modules", "vendor", ".idea", ".vscode", "deploy_config.json"
    ],
    "PATH_MAPPINGS": []
}


log_queue = Queue()


# ---------- _kandidat_folder ----------
def _kandidat_folder():
    """Folder yang diperiksa berurutan: direktori kerja, root repositori, folder paket.

    Sejak aplikasi dipisah menjadi paket `smart_deploy_app`, berkas konfigurasi
    tetap berada di sebelah `app.py` (root repositori). Perpencarian ini membuat
    aplikasi tetap jalan walau dipanggil dari folder berbeda, dan tetap mendukung
    susunan lama ketika `deploy_config.json` sekelas dengan modul.
    """
    folder_modul = Path(__file__).resolve().parent
    folder_induk = folder_modul.parent
    return [Path.cwd().resolve(), folder_induk, folder_modul]


# ---------- folder_konfigurasi ----------
def folder_konfigurasi():
    """Folder tempat `deploy_config.json` berada (atau yang menjadi tujuan simpan baru)."""
    kandidat = _kandidat_folder()
    for folder in kandidat:
        if (folder / CONFIG_FILENAME).is_file():
            return folder
    return kandidat[1]


# ---------- jalur_konfigurasi ----------
def jalur_konfigurasi():
    return folder_konfigurasi() / CONFIG_FILENAME


# ---------- store_bawaan ----------
def store_bawaan():
    return {
        "active_profile": "Default",
        "profiles": {
            "Default": DEFAULT_CONFIG.copy()
        }
    }


# ---------- _normalisasi_isi ----------
def _normalisasi_isi(isi):
    """Samakan bentuk data konfigurasi (format familia atau sesi tunggal) menjadi store."""
    if "profiles" in isi and isinstance(isi.get("profiles"), dict) and isi["profiles"]:
        for p_name, p_cfg in isi["profiles"].items():
            isi["profiles"][p_name] = _satu_profil(p_cfg)

        if isi.get("active_profile") not in isi["profiles"]:
            isi["active_profile"] = list(isi["profiles"].keys())[0]
        return isi

    # Format tunggal (tanpa kunci 'profiles'): perlakukan seluruh data sebagai satu profil
    return {
        "active_profile": "Default",
        "profiles": {"Default": _satu_profil(isi)}
    }


# ---------- _satu_profil ----------
def _satu_profil(p_cfg):
    merged = DEFAULT_CONFIG.copy()
    if isinstance(p_cfg, dict):
        merged.update(p_cfg)
    if not merged.get("EXCLUDE_PATTERNS"):
        merged["EXCLUDE_PATTERNS"] = list(DEFAULT_CONFIG["EXCLUDE_PATTERNS"])
    if isinstance(merged.get("EXCLUDE_PATTERNS"), str):
        merged["EXCLUDE_PATTERNS"] = [
            l.strip() for l in merged["EXCLUDE_PATTERNS"].splitlines() if l.strip()
        ]
    if merged.get("PATH_MAPPINGS") is None:
        merged["PATH_MAPPINGS"] = []
    return merged


# ---------- load_config_store ----------
def load_config_store():
    config_path = jalur_konfigurasi()
    if not config_path.is_file():
        return store_bawaan()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("isi berkas bukan objek JSON yang diharapkan")
    except Exception:
        log_queue.put("[CONFIG] Berkas konfigurasi tidak dapat dibaca di folder aplikasi.")
        return store_bawaan()

    if data.get("format") == FORMAT_BRAKAS and "vault" in data:
        try:
            isi = buka_brankas(data, log=log_queue.put)
        except GagalBrankas as e:
            log_queue.put(f"[WARN] {e}")
            log_queue.put("[CONFIG] Aplikasi dijalankan tanpa konfigurasi tersimpan. "
                          "Pulihkan berkas kunci dari cadangan, atau isi ulang data profil di tab Konfigurasi.")
            hasil = store_bawaan()
            hasil["vault_galat"] = str(e)
            return hasil
    else:
        isi = data  # format lama tanpa enkripsi; dimigrasi otomatis saat berikutnya disimpan

    return _normalisasi_isi(isi)


# ---------- save_config_store ----------
def save_config_store(store_dict):
    if store_dict.get("vault_galat"):
        log_queue.put("[CONFIG] Penyimpanan diblokir supaya data konfigurasi lama tidak tertimpa. "
                      "Pulihkan dulu berkas kunci di home folder, lalu coba lagi.")
        return False

    isi = {
        "active_profile": store_dict.get("active_profile", "Default"),
        "profiles": store_dict.get("profiles", {"Default": DEFAULT_CONFIG.copy()})
    }

    config_path = jalur_konfigurasi()
    try:
        dokumen = dokumen_brankas(isi, log=log_queue.put)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(dokumen, f, ensure_ascii=False, indent=2)
        os.chmod(config_path, 0o600)  # Lindungi berkas dari akses user lain
    except GagalBrankas as e:
        log_queue.put(f"[ERROR] {e}")
        return False
    except Exception as e:
        log_queue.put(f"[CONFIG] Gagal menyimpan berkas konfigurasi: {e}")
        return False

    log_queue.put("[CONFIG] Konfigurasi tersimpan.")
    return True


# ---------- should_exclude ----------
def should_exclude(file_path, exclude_patterns):
    path_str = Path(file_path).as_posix()
    for pattern in exclude_patterns:
        if not pattern:
            continue
        if path_str.startswith(pattern) or f"/{pattern}" in path_str:
            return True
    return False


# ---------- resolve_remote_path ----------
def resolve_remote_path(local_rel_path, mappings):
    posix_path = Path(local_rel_path).as_posix()
    for mapping in mappings:
        local_prefix = mapping.get("local", "").strip()
        remote_prefix = mapping.get("remote", "").strip()
        if not local_prefix:
            continue
        if not local_prefix.endswith("/"):
            local_prefix += "/"
        if posix_path.startswith(local_prefix):
            stripped = posix_path[len(local_prefix):]
            final_path = str(Path(remote_prefix) / stripped)
            return Path(final_path).as_posix()
    return posix_path
