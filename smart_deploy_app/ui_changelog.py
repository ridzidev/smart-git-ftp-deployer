"""Tab Perubahan: riwayat versi aplikasi dengan tampilan yang rapi."""
import webbrowser
import tkinter as tk
from tkinter import ttk, scrolledtext

from .theme import (CLR_BG, CLR_BORDER, CLR_PRIMARY, CLR_SURFACE, CLR_TEXT, CLR_TEXT_MUTED,
                    FONT_JUDUL_BESAR, FONT_LABEL, NAMA_FONT)

URL_PROYEK = "https://github.com/ridzidev/smart-git-ftp-deployer"
FON_VERSI = (NAMA_FONT, 12, "bold")
FON_TAUTAN = (NAMA_FONT, 9, "underline")

RIWAYAT_VERSI = [
    ("v3.0.1", "26 Oktober 2026", [
        "Perbaikan: berkas yang diganti nama atau dipindah kini diperlakukan sebagai hapus path lama "
        "lalu unggah path baru. Sebelumnya path baru terunggah tetapi berkas lama tertinggal di server.",
        "Perhitungan perubahan memakai git diff tanpa deteksi rename, sehingga hasilnya sama di semua "
        "pengaturan Git dan tidak bergantung pada kebijakan rename server FTP.",
    ]),
    ("v3.0", "25 Oktober 2026", [
        "Editor teks bawaan di tab Peramban Berkas: memilih satu berkas di panel server membuka "
        "editor di samping daftar berkas, lalu isinya bisa disunting langsung.",
        "Editor dibuat sendiri dengan Tkinter tanpa dependensi baru: nomor baris, sorot sintaks "
        "(Python, PHP, JavaScript, HTML, CSS, JSON, SQL, shell, konfigurasi), cari dan ganti, "
        "indentasi otomatis, Tab dan Shift+Tab untuk blok, serta undo dan redo.",
        "Simpan dengan Ctrl atau Cmd+S langsung mengunggah ke server. Penanda belum tersimpan tampil "
        "di bilah editor, dan ada konfirmasi sebelum perubahan dibuang.",
        "Sandi berkas dan akhir baris dipertahankan (UTF-8 dengan atau tanpa BOM, LF atau CRLF). "
        "Berkas biner dan berkas di atas 2 MB tidak dibuka di editor.",
        "Penyimpanan ditolak bila profil server sudah berganti sejak berkas dibuka, supaya tidak "
        "menimpa server yang salah.",
    ]),
    ("v2.7", "21 Oktober 2026", [
        "Tab Peramban Berkas dibangun ulang menyerupai pengelola berkas FTP: daftar datar berkolom "
        "Nama, Ukuran, dan Diubah dengan ikon, bilah alamat per panel, tombol Naik dan Root, baris "
        "naik folder, serta sortir lewat klik kepala kolom.",
        "Operasi berkas langsung dari peramban: unggah dan unduh untuk banyak pilihan sekaligus, "
        "buat folder, ubah nama, dan hapus berlapis. Menu klik kanan dan dobel klik tersedia, "
        "lengkap bar progres serta konfirmasi sebelum hapus atau timpa.",
        "Panel lokal mewarnai status Git: hijau berkas baru, kuning berkas berubah, dan coret merah "
        "untuk berkas yang akan dilewati saat deploy.",
        "Saklar sinkron navigasi membuka folder padanan di server, dan opsi tampilkan berkas "
        "tersembunyi berlaku untuk kedua panel.",
        "Deployment Engine dan Ekspor SQL diperapai: aksen warna pada tajuk dan status, baris "
        "antrean diwarnai menurut aksi, serta penyorotan sintaks pada pratinjau SQL.",
    ]),
    ("v2.6", "21 Oktober 2026", [
        "Layar pembuka singkat dengan identitas aplikasi, ditambah tab Panduan dan tab Perubahan.",
        "Tab Deployment Engine dan Ekspor SQL disusun ulang: seluruh kendali dipindah ke satu sidebar di kiri, daftar komit menempati area utama, dan area hasil melebar di bawahnya.",
        "Tampilan menyeluruh: jenis huruf menyesuaikan sistem operasi, kolom isian gelap, baris tabel "
        "bertukar warna, tekanan tombol lebih halus, dan bilah status pada bagian bawah jendela.",
    ]),
    ("v2.5", "21 Oktober 2026", [
        "Konfigurasi disimpan terenkripsi; password tidak ditulis sebagai teks biasa. Kunci tersimpan "
        "di berkas kunci pribadi atau variabel lingkungan, tidak pernah berada di dalam data konfigurasi.",
        "Penyimpanan diblokir saat kunci tidak cocok, sehingga data lama tidak tertimpa konfigurasi kosong.",
        "Dropdown pilihan digambar sendiri karena daftar bawaan Tk 9 pada macOS tidak memunculkan pilihan.",
        "Perbaikan: berkas konfigurasi kembali terbaca di sebelah app.py sejak penataan ulang v2.3.",
        "Pesan dan dialog ditulis ulang agar ringan dipahami pengguna.",
    ]),
    ("v2.4", "21 Oktober 2026", [
        "Saring rentang tanggal di tab Deployment Engine dan Ekspor SQL: preset cepat, isian tanggal "
        "bebas, pemilih tanggal kalender, plus hitungan hasil saringan secara langsung.",
    ]),
    ("v2.3", "21 Oktober 2026", [
        "Kode dipecah per pekerjaan ke dalam paket smart_deploy_app: konfigurasi, tema, Git, FTP, "
        "dan satu modul per tab antarmuka. Perilaku aplikasi tidak berubah.",
    ]),
    ("v2.2", "21 Oktober 2026", [
        "Pembaruan besar dikemas sepanjang hari:",
        "Tab Ekspor SQL baru. Riwayat komit tersaji penuh secara kronologis, generator pernyataan INSERT dengan preset Semua dan 50 Terakhir, salin query ke clipboard, serta simpan berkas .sql.",
        "Deployment Engine: pilih beberapa komit sekaligus, tumpukan berkas dihitung ulang langsung, mode eksekusi Bertahap per komit atau Akumulatif sekaligus, tombol Batalkan di tengah proses, dan bar progres per berkas.",
        "Dukungan FTP over TLS (FTPS) mengenkripsi kanal kontrol dan data.",
        "Berkas konfigurasi dipaksa berizin ketat saat disimpan, .env ikut diabaikan, dan tangkapan layar dokumentasi disensor dari kredensial server.",
        "Pola pengecualian bawaan diperluas dan README ditulis ulang seluruhnya.",
    ]),
    ("Pembaruan pembantu", "April & Agustus 2026", [
        "April: klik baris komit pada tabel untuk menyalin detail komit ke clipboard.",
        "Agustus: dukungan banyak profil, satu aplikasi mengelola beberapa proyek dan server dengan konfigurasi terpisah.",
    ]),
    ("v2.1", "5 Januari 2026", [
        "Tombol Bersihkan Log untuk membersihkan konsol eksekusi tanpa menutup aplikasi.",
    ]),
    ("v2.0", "5 Januari 2026", [
        "Tampilan dibangun ulang menyeluruh: tema gelap bernuansa GitHub Dark dengan kartu bagian dan panel geser antar area.",
        "Satu jendela menjadi tiga tab: Deployment, Peramban Berkas, dan Konfigurasi.",
        "Tombol Quick Deploy satu klik: mendeteksi komit terbaru lalu langsung menjalankan deployment.",
    ]),
    ("v1.0", "18 Oktober 2025", [
        "Rilis perdana. Proyek dipublikasikan di GitHub bersama README perdana.",
        "Satu berkas smart_deploy.py dengan jendela Tkinter.",
        "Deployment sadar struktur: membandingkan dua komit, mengunggah berkas baru dan berubah, menghapus berkas yang hilang di server.",
        "Folder tujuan di server dibuat rekursif, folder kosong bekas penghapusan dibersihkan berantai.",
        "Tombol uji koneksi FTP plus konsol pesan latar yang aman lintas utas.",
        "Pengecualian berkas dan konfigurasi aplikasi tersimpan ke berkas lokal.",
    ]),
]


class ChangelogTabMixin:

    # ---------- setup_changelog_tab ----------
    def setup_changelog_tab(self):
        wadah = ttk.Frame(self.tab_changelog, padding=(24, 18))
        wadah.pack(fill=tk.BOTH, expand=True)

        kepala = tk.Frame(wadah, bg=CLR_BG)
        kepala.pack(fill=tk.X)
        tk.Label(kepala, text="Riwayat Perubahan", bg=CLR_BG, fg=CLR_TEXT,
                 font=FONT_JUDUL_BESAR).pack(side=tk.LEFT)
        tk.Label(kepala, text="Versi aplikasi sejak tanggal rilis", bg=CLR_BG, fg=CLR_TEXT_MUTED,
                 font=FONT_LABEL).pack(side=tk.LEFT, padx=(14, 0), pady=(6, 0))

        kotak = tk.Frame(wadah, bg=CLR_BORDER)
        kotak.pack(fill=tk.BOTH, expand=True, pady=(14, 0))
        panel = tk.Frame(kotak, bg=CLR_SURFACE)
        panel.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.teks_changelog = scrolledtext.ScrolledText(
            panel,
            bg=CLR_SURFACE,
            fg=CLR_TEXT,
            insertbackground=CLR_TEXT,
            font=FONT_LABEL,
            relief="flat",
            borderwidth=0,
            wrap="word",
            padx=22,
            pady=18,
            state="disabled"
        )
        self.teks_changelog.pack(fill=tk.BOTH, expand=True)

        self.teks_changelog.tag_config("versi", foreground=CLR_TEXT, font=FON_VERSI)
        self.teks_changelog.tag_config("tanggal", foreground=CLR_TEXT_MUTED, font=FONT_LABEL)
        self.teks_changelog.tag_config("poin", foreground=CLR_TEXT, font=FONT_LABEL,
                                       lmargin1=22, lmargin2=40, spacing3=4)
        self.teks_changelog.tag_config("tautan", foreground=CLR_PRIMARY, font=FON_TAUTAN)
        self.teks_changelog.tag_bind("tautan", "<Button-1>", self._buka_proyek)
        self.teks_changelog.tag_bind("tautan", "<Enter>", lambda e: self.teks_changelog.config(cursor="hand2"))
        self.teks_changelog.tag_bind("tautan", "<Leave>", lambda e: self.teks_changelog.config(cursor=""))

        segmen = []
        for atur, (versi, tanggal, daftar_poin) in enumerate(RIWAYAT_VERSI):
            if atur:
                segmen.extend(("\n\n", "poin"))
            segmen.extend((versi, "versi", f"    {tanggal}\n", "tanggal"))
            for poin in daftar_poin:
                segmen.extend(("  •  ", "tanggal", f"{poin}\n", "poin"))
        segmen.extend(("\n", "poin", "Halaman proyek:  ", "tanggal", URL_PROYEK, "tautan"))

        self.teks_changelog.config(state="normal")
        self.teks_changelog.delete("1.0", tk.END)
        self.teks_changelog.insert(tk.END, *segmen)
        self.teks_changelog.config(state="disabled")

    # ---------- _buka_proyek ----------
    def _buka_proyek(self, event=None):
        webbrowser.open(URL_PROYEK)
