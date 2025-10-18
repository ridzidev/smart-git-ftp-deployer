# Smart Git-FTP Deployer

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A smart, structure-aware, Git-based FTP deployer with a GUI. It automatically detects changed files from your commits to upload or delete, making deployments to shared hosting a breeze.

![App Screenshot](https://raw.githubusercontent.com/ridzidev/smart-git-ftp-deployer/main/screenshot.png) 
*(Pastikan Anda mengganti link di atas dengan URL screenshot aplikasi Anda setelah Anda mengunggahnya ke repo)*

---

## 😩 Masalah: Deployment Manual via FTP yang Melelahkan

Deploy ke *shared hosting* seringkali berarti kita harus kembali ke metode upload FTP manual, yang lambat, membosankan, dan sangat rentan terhadap kesalahan. Pernahkah Anda:

-   Lupa file mana saja yang baru Anda ubah?
-   Lupa menghapus file lama di server yang seharusnya sudah tidak ada?
-   Menghabiskan waktu berharga untuk meng-upload ulang **seluruh proyek** hanya untuk perubahan kecil pada satu file CSS?
-   Berharap ada cara seperti CI/CD di server yang hanya memberikan akses FTP?

Jika ya, alat ini dibuat untuk Anda.

## ✨ Solusi: Cara Deploy yang Lebih Cerdas

**Smart Git-FTP Deployer** menjembatani kekuatan **Git** dengan keterbatasan **FTP**. Aplikasi ini menggunakan riwayat *commit* di repositori Anda sebagai "sumber kebenaran" untuk menentukan dengan tepat apa saja yang perlu diubah di server Anda.

Tidak ada lagi tebak-tebakan, tidak ada lagi upload penuh yang membuang waktu.

### Fitur Unggulan

-   ✅ **Deploy Berbasis Commit:** Cukup pilih satu atau beberapa commit, dan aplikasi akan secara otomatis menghitung perbedaannya.
-   ✅ **Sinkronisasi Cerdas:** Tidak hanya meng-upload, aplikasi ini juga akan **menghapus** file di server yang telah Anda hapus di repositori lokal.
-   ✅ **Antarmuka Grafis (GUI):** Tampilan yang bersih dan sederhana untuk melihat commit terbaru, meninjau daftar file yang akan diproses, dan memantau log deployment secara *real-time*.
-   ✅ **Pola Pengecualian (Exclude):** Konfigurasikan dengan mudah file dan folder yang ingin diabaikan saat deployment (misalnya: `.git`, `node_modules`, `.env`, `storage`).
-   ✅ **File Konfigurasi:** Semua pengaturan (kredensial FTP, path, daftar pengecualian) disimpan dalam satu file `deploy_config.json` yang mudah dikelola.
-   ✅ **Tinjauan Pra-Deployment:** Lihat dengan jelas file mana yang akan diunggah dan mana yang akan dihapus **sebelum** Anda menekan tombol deploy.

## 🎯 Siapa yang Seharusnya Menggunakan Ini?

-   **Web developer** yang melakukan deployment ke **shared hosting** atau server lain yang hanya menyediakan akses FTP.
-   Developer yang menggunakan **Git** sebagai sistem kontrol versi utama.
-   Siapa saja yang ingin mengotomatiskan alur kerja deployment mereka dan mengurangi risiko kesalahan manual.

## 🚀 Panduan Memulai

### Prasyarat

-   **Python 3.x** terpasang di sistem Anda.
-   **Git** terpasang dan dapat diakses dari command line/terminal.

### Instalasi & Penggunaan

1.  **Clone Repositori Ini**
    ```bash
    git clone https://github.com/ridzidev/smart-git-ftp-deployer.git
    cd smart-git-ftp-deployer
    ```

2.  **Konfigurasi Proyek Anda**
    Aplikasi ini menggunakan file `deploy_config.json` untuk semua pengaturan. Anda dapat:
    -   **Menjalankan skrip terlebih dahulu:** `python smart_deploy.py`. File konfigurasi default akan dibuat.
    -   **Mengedit via aplikasi:** Buka tab "Configuration" di dalam aplikasi untuk mengisi detail Anda.

3.  **Jalankan Aplikasi**
    ```bash
    python smart_deploy.py
    ```

4.  **Deploy!**
    -   Aplikasi akan memuat commit terbaru dari direktori proyek Anda (yang diatur di `LOCAL_DIR`).
    -   Pilih satu atau beberapa commit yang ingin Anda deploy. Daftar file yang berubah akan muncul secara otomatis.
    -   Tinjau daftar file yang akan diunggah atau dihapus.
    -   Klik tombol **"Deploy Selected Commits"**. Selesai!

## ⚙️ Detail Konfigurasi (`deploy_config.json`)

Berikut adalah penjelasan untuk setiap field di file konfigurasi:

-   `FTP_HOST`: Hostname server FTP Anda (contoh: `ftp.domainanda.com`).
-   `FTP_USER`: Username FTP Anda.
-   `FTP_PASS`: Password FTP Anda.
-   `LOCAL_DIR`: Path ke direktori proyek lokal Anda (folder yang berisi `.git`). Gunakan `.` jika skrip berada di root proyek.
-   `REMOTE_DIR`: Direktori tujuan di server FTP (contoh: `/public_html/`).
-   `EXCLUDE_PATTERNS`: Daftar file dan direktori yang ingin diabaikan. Skrip akan memeriksa apakah path file *dimulai dengan* salah satu pola ini.

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
