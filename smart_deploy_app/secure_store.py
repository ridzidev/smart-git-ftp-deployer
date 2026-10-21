"""Brankas konfigurasi: menyusun berkas bawaan aplikasi menjadi sandi AES-256-GCM.

Semua isi profil (termasuk host, username, dan password FTP) disimpan dalam satu
segmen sandi, sehingga berkas `deploy_config.json` tidak memuat data mentah.
Kunci tidak pernah disimpan di dalam berkas konfigurasi: ia diambil dari
variabel lingkungan `SMART_DEPLOY_KEY`, atau dari berkas kunci pribadi
(~/.smart_git_ftp_deployer.key) yang dibuat otomatis saat pertama kali dibutuhkan.
"""
import base64
import hashlib
import json
import os
from pathlib import Path

MAGIS_APP = "smart-git-ftp-deployer"
FORMAT_BRAKAS = "AESGCM-256/v1"
JUMLAH_ITERASI_KDF = 100_000
PANJANG_GARAM = 16
PANJANG_NONCE = 12
PANJANG_KUNCI = 32
NAMA_ENV_KUNCI = "SMART_DEPLOY_KEY"


NAMA_BERKAS_KUNCI = ".smart_git_ftp_deployer.key"


class GagalBrankas(Exception):
    """Dilempar saat brankas tidak dapat dibangun, dibuka, atau dibuka tanpa kunci cocok."""


try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    TERSIDIA = True
    _GALAT_IMPORT = ""
except Exception as kesalahan:
    AESGCM = None
    TERSIDIA = False
    _GALAT_IMPORT = str(kesalahan)


# ---------- jalur_berkas_kunci ----------
def jalur_berkas_kunci():
    """Lokasi berkas kunci pribadi pengguna (di luar folder aplikasi)."""
    return Path.home() / NAMA_BERKAS_KUNCI


# ---------- ambil_kunci ----------
def ambil_kunci(log=None):
    """Kunci master 32 byta dari variabel lingkungan, berkas kunci, atau dibuat baru."""
    def catat(teks):
        if log:
            log(teks)

    dari_env = os.environ.get(NAMA_ENV_KUNCI, "").strip()
    if dari_env:
        try:
            kunci = base64.b64decode(dari_env)
        except Exception:
            raise GagalBrankas(
                f"Encryption key in {NAMA_ENV_KUNCI} is not legible. Check the format of the variable.")
        if len(kunci) != PANJANG_KUNCI:
            raise GagalBrankas(
                f"Encryption key in {NAMA_ENV_KUNCI} is not the right size.")
        return kunci

    berkas_kunci = jalur_berkas_kunci()
    if berkas_kunci.is_file():
        try:
            kunci = base64.b64decode(berkas_kunci.read_text(encoding="ascii").strip())
        except Exception:
            raise GagalBrankas(
                "Configuration key file (in home folder) is damaged or unreadable.")
        if len(kunci) != PANJANG_KUNCI:
            raise GagalBrankas("Configuration key file (in home folder) is not valid.")
        return kunci

    kunci = os.urandom(PANJANG_KUNCI)
    try:
        berkas_kunci.write_text(base64.b64encode(kunci).decode("ascii"), encoding="ascii")
        os.chmod(berkas_kunci, 0o600)
    except OSError:
        raise GagalBrankas(
            "Configuration key cannot be stored in home folder. Please check folder write availability, "
            f"or set the {NAMA_ENV_KUNCI} variable manually.")

    catat(f"[CONFIG] A new configuration key has been created in {berkas_kunci}. "
          "Please save it as backup \u2014 if lost, the server configuration will be inaccessible.")
    return kunci


# ---------- _turunkan_kunci ----------
def _turunkan_kunci(master, garam):
    """Kunci per-berkas dari kunci master; garam baru di setiap penyimpanan."""
    return hashlib.pbkdf2_hmac(
        "sha256", master, garam, JUMLAH_ITERASI_KDF, dklen=32)


# ---------- dokumen_brankas ----------
def dokumen_brankas(peta, log=None):
    """Kembalikan dokumen JSON siap simpan berisi brankas terenkripsi dari `peta`."""
    if not TERSIDIA:
        raise GagalBrankas(
            "Penyimpanan konfigurasi membutuhkan paket 'cryptography'. "
            "Jalankan 'pip install cryptography' lalu coba simpan lagi.")

    master = ambil_kunci(log)
    garam = os.urandom(PANJANG_GARAM)
    nonce = os.urandom(PANJANG_NONCE)
    kunci_data = _turunkan_kunci(master, garam)
    aad = f"{MAGIS_APP}|{FORMAT_BRAKAS}".encode("utf-8")

    try:
        sandi = AESGCM(kunci_data).encrypt(
            nonce, json.dumps(peta, ensure_ascii=False).encode("utf-8"), aad)
    except Exception:
        raise GagalBrankas("Gagal melindungi data konfigurasi sebelum disimpan.")

    segmen = garam + nonce + sandi
    return {
        "app": MAGIS_APP,
        "format": FORMAT_BRAKAS,
        "vault": base64.b64encode(segmen).decode("ascii"),
    }


# ---------- buka_brankas ----------
def buka_brankas(dokumen, log=None):
    """Balikkan peta asli dari dokumen brankas. Gagal apa pun melempar GagalBrankas."""
    if not TERSIDIA:
        raise GagalBrankas(
            "Pembacaan konfigurasi membutuhkan paket 'cryptography'. "
            "Jalankan 'pip install cryptography' lalu coba lagi.")

    try:
        master = ambil_kunci(log)
    except GagalBrankas as e:
        raise GagalBrankas(f"{e} Tanpa kunci ini, data konfigurasi Anda tidak dapat dibuka.")

    try:
        segmen = base64.b64decode(dokumen["vault"])
    except Exception:
        raise GagalBrankas("Data konfigurasi berbentuk tidak sah (file kemungkinan rusak).")

    minimal = PANJANG_GARAM + PANJANG_NONCE + 16  # + tetik autentikasi GCM
    if len(segmen) < minimal:
        raise GagalBrankas("Data konfigurasi terlalu pendek (file kemungkinan rusak).")

    garam = segmen[:PANJANG_GARAM]
    nonce = segmen[PANJANG_GARAM:PANJANG_GARAM + PANJANG_NONCE]
    sandi = segmen[PANJANG_GARAM + PANJANG_NONCE:]

    kunci_data = _turunkan_kunci(master, garam)
    aad = f"{MAGIS_APP}|{FORMAT_BRAKAS}".encode("utf-8")
    try:
        terbuka = AESGCM(kunci_data).decrypt(nonce, sandi, aad)
    except Exception:
        # autentikasi GCM gagal biasanya karena kunci master bukan milik brankas ini
        raise GagalBrankas(
            "Kunci Anda tidak cocok dengan data konfigurasi yang tersimpan. "
            "Pastikan berkas kunci di home folder adalah yang dibuat bersama "
            "konfigurasinya, atau pulihkan kunci dari cadangan.")

    try:
        peta = json.loads(terbuka.decode("utf-8"))
    except Exception:
        raise GagalBrankas("Isi data konfigurasi tidak dapat diurai.")

    if not isinstance(peta, dict):
        raise GagalBrankas("Data konfigurasi tidak berbentuk profil yang dapat dibaca.")
    return peta
