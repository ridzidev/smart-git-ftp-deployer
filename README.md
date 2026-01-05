# Smart Git-FTP Deployer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A smart, structure-aware, Git-based FTP deployer with a GUI. It automatically detects changed files from your commits to upload or delete, making deployments to shared hosting a breeze.

**v2.1 (Quick Deploy & Browser Edition)**

![alt text](https://raw.githubusercontent.com/ridzidev/smart-git-ftp-deployer/refs/heads/main/screenshoot1.png)

v.1

![alt text](https://raw.githubusercontent.com/ridzidev/smart-git-ftp-deployer/refs/heads/main/screenshoot.png)
---

## 😩 Masalah: Deployment Manual via FTP yang Melelahkan

Deploy ke *shared hosting* seringkali berarti kita harus kembali ke metode upload FTP manual, yang lambat, membosankan, dan sangat rentan terhadap kesalahan. Pernahkah Anda:

-   Lupa file mana saja yang baru Anda ubah?
-   Lupa menghapus file lama di server yang seharusnya sudah tidak ada?
-   Menghabiskan waktu berharga untuk meng-upload ulang **seluruh proyek** hanya untuk perubahan kecil pada satu file CSS?
-   Berharap ada cara seperti CI/CD di server yang hanya memberikan akses FTP?

Jika ya, alat ini dibuat untuk Anda.

## ✨ Solusi: Cara Deploy yang Lebih Cerdas (Update v2.1)

**Smart Git-FTP Deployer** menjembatani kekuatan **Git** dengan keterbatasan **FTP**. Aplikasi ini menggunakan riwayat *commit* di repositori Anda sebagai "sumber kebenaran" untuk menentukan dengan tepat apa saja yang perlu diubah di server Anda.

### Fitur Unggulan v2.1

-   ✅ **⚡ Quick Deploy (Latest):** Fitur paling canggih. Satu klik untuk otomatis Refresh, mengambil commit paling baru, dan langsung melakukan deployment tanpa perlu memilih manual.
-   ✅ **📂 Integrated FTP Browser:** Telusuri file di server FTP Anda secara langsung di dalam aplikasi (Explore & View remote structure).
-   ✅ **🗺️ Path Mapping Logic:** Mendukung pemetaan folder. Anda bisa memetakan folder lokal (misal: `dist/` atau `build/`) ke folder remote yang berbeda secara spesifik.
-   ✅ **Deploy Berbasis Commit:** Pilih satu atau rentang beberapa commit sekaligus untuk menghitung perbedaan file.
-   ✅ **Sinkronisasi Cerdas:** Otomatis mendeteksi file yang harus di-upload (**Added/Modified**) dan file yang harus dihapus (**Deleted**) di server.
-   ✅ **Antarmuka Grafis (GUI) Modern:** UI gelap (Cyberpunk 2026 style) yang nyaman di mata untuk memantau log secara real-time.
-   ✅ **🧹 Clear Log:** Bersihkan terminal log deployment dengan satu tombol untuk menjaga tampilan tetap rapi.
-   ✅ **Pola Pengecualian (Exclude):** Abaikan file/folder sensitif atau sampah seperti `.git`, `node_modules`, atau `.env`.

## 🎯 Siapa yang Seharusnya Menggunakan Ini?

-   **Web developer** yang melakukan deployment ke **shared hosting** (cPanel/DirectAdmin) yang hanya menyediakan akses FTP.
-   Developer yang ingin kecepatan CI/CD tanpa setup server yang rumit.
-   Siapa saja yang ingin meminimalisir kesalahan "salah upload file" saat rilis fitur baru.

## 🚀 Panduan Memulai

### Prasyarat

-   **Python 3.x** terpasang di sistem Anda.
-   **Git** terpasang dan repositori lokal sudah di-init (`git init`).

### Instalasi & Penggunaan

1.  **Clone Repositori Ini**
    ```bash
    git clone https://github.com/ridzidev/smart-git-ftp-deployer.git
    cd smart-git-ftp-deployer
    ```

2.  **Konfigurasi Proyek Anda**
    - Jalankan aplikasi: `python smart_deploy.py`.
    - Pergi ke tab **"Configuration"**.
    - Isi Host, User, Password FTP, serta direktori lokal dan remote.
    - (Opsional) Tambahkan **Path Mapping** jika folder lokal dan remote Anda tidak simetris.
    - Klik **Save Configuration**.

3.  **Cara Deploy Cepat (Quick Mode)**
    - Klik tombol **"⚡ QUICK DEPLOY (LATEST)"**.
    - Aplikasi akan mengambil perubahan terbaru dari commit terakhir dan langsung mengirimnya ke server.

4.  **Cara Deploy Manual (Selection Mode)**
    - Pilih commit-commit tertentu di tabel Git History.
    - Tinjau file di tabel "Staged for Deploy".
    - Klik **"🚀 START DEPLOY"**.

## ⚙️ Detail Konfigurasi (`deploy_config.json`)

-   `FTP_HOST`: Hostname server FTP (contoh: `ftp.domainanda.com`).
-   `FTP_USER`: Username FTP.
-   `FTP_PASS`: Password FTP.
-   `LOCAL_DIR`: Path folder proyek lokal (yang ada folder `.git`).
-   `REMOTE_DIR`: Folder tujuan di server (contoh: `/public_html/`).
-   `PATH_MAPPINGS`: List pemetaan folder lokal ke remote.
-   `EXCLUDE_PATTERNS`: Daftar file yang dilarang di-upload.

## 🤝 Berkontribusi

Kontribusi, isu, dan permintaan fitur sangat diterima! Jangan ragu untuk memeriksa [halaman isu](https://github.com/ridzidev/smart-git-ftp-deployer/issues).

1.  Fork Proyek ini.
2.  Buat Branch Fitur Anda (`git checkout -b feature/FiturKeren`).
3.  Commit Perubahan Anda (`git commit -m 'Menambahkan FiturKeren'`).
4.  Push ke Branch (`git push origin feature/FiturKeren`).
5.  Buka sebuah Pull Request.

## 📜 Lisensi

Didistribusikan di bawah Lisensi MIT. Lihat file `LICENSE` untuk informasi lebih lanjut.

---
Dibuat dengan ❤️ oleh [ridzidev](https://github.com/ridzidev)
